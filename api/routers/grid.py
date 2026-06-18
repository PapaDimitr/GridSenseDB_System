# /grid endpoints — backed by Neo4j

from fastapi import APIRouter, HTTPException

from db.neo4j import get_driver
from models.graph import (
    AffectedNode,
    FaultImpactResponse,
    RestorePath,
    RestorePathsResponse,
    NodeIn,
    RelationshipIn,
)

router = APIRouter(prefix="/grid", tags=["Grid Topology"])

REL_TYPES = "FEEDS|SUPPLIES|CONNECTS_TO"

# Whitelists to validate dynamic labels / rel-types before injecting them into a
# query string

ALLOWED_LABELS = {"GridSupplyPoint", "Substation", "Transformer",
                  "SmartMeter", "Feeder", "Switchgear"}
ALLOWED_RELS = {"FEEDS", "SUPPLIES", "CONNECTS_TO"}


@router.get("/fault-impact/{node_id}", response_model=FaultImpactResponse)
async def get_fault_impact(node_id: str, max_depth: int = 6):
    # Every node that loses supply if `node_id` trips
    if not 1 <= max_depth <= 10:
        raise HTTPException(status_code=400,
                            detail="max_depth must be between 1 and 10")

    cypher = f"""
    MATCH path = (origin {{node_id: $node_id}})
                 -[:{REL_TYPES}*1..{max_depth}]->(downstream)
    RETURN labels(downstream)[0] AS node_type,
           downstream.node_id    AS node_id,
           downstream.name       AS name,
           length(path)          AS depth
    ORDER BY depth
    """
    async with get_driver().session() as session:
        result = await session.run(cypher, node_id=node_id)
        records = await result.data()
        if not records:
            await _ensure_exists(session, node_id)

    affected = [AffectedNode(**r) for r in records]
    return FaultImpactResponse(origin_id=node_id,
                               affected_nodes=affected,
                               total_affected=len(affected))


@router.get("/restore-paths/{node_id}", response_model=RestorePathsResponse)
async def get_restore_paths(node_id: str, max_depth: int = 6):
    """Supply paths that could restore `node_id` — every path from a
    GridSupplyPoint down to the node. Multiple paths = alternative routing."""
    if not 1 <= max_depth <= 10:
        raise HTTPException(status_code=400,
                            detail="max_depth must be between 1 and 10")

    cypher = f"""
    MATCH path = (source:GridSupplyPoint)
                 -[:{REL_TYPES}*1..{max_depth}]->(target {{node_id: $node_id}})
    RETURN [n IN nodes(path) | n.node_id] AS path, length(path) AS hops
    ORDER BY hops
    """
    async with get_driver().session() as session:
        result = await session.run(cypher, node_id=node_id)
        rows = await result.data()
        if not rows:
            await _ensure_exists(session, node_id)

    paths = [RestorePath(path=r["path"], hops=r["hops"]) for r in rows]
    return RestorePathsResponse(target_id=node_id, paths=paths,
                                total_paths=len(paths))


@router.post("/nodes", status_code=201)
async def add_node(node: NodeIn):
    """Add a new node to the topology graph."""
    if node.label not in ALLOWED_LABELS:
        raise HTTPException(status_code=400,
                            detail=f"label must be one of {sorted(ALLOWED_LABELS)}")

    props = {**node.properties, "node_id": node.node_id}
    cypher = f"CREATE (n:{node.label} $props) " \
             f"RETURN n.node_id AS node_id, labels(n)[0] AS label"
    async with get_driver().session() as session:
        result = await session.run(cypher, props=props)
        rec = await result.single()
    return {"status": "created", "node_id": rec["node_id"], "label": rec["label"]}


@router.post("/relationships", status_code=201)
async def add_relationship(rel: RelationshipIn):
    """Add a relationship (feeder / cable / connection) between two nodes."""
    if rel.rel_type not in ALLOWED_RELS:
        raise HTTPException(status_code=400,
                            detail=f"rel_type must be one of {sorted(ALLOWED_RELS)}")

    cypher = f"""
    MATCH (a {{node_id: $from_id}}), (b {{node_id: $to_id}})
    CREATE (a)-[r:{rel.rel_type} $props]->(b)
    RETURN type(r) AS rel_type
    """
    async with get_driver().session() as session:
        result = await session.run(cypher, from_id=rel.from_node_id,
                                   to_id=rel.to_node_id, props=rel.properties)
        rec = await result.single()
        if rec is None:
            raise HTTPException(status_code=404,
                                detail="One or both nodes not found")
    return {"status": "created", "rel_type": rec["rel_type"],
            "from": rel.from_node_id, "to": rel.to_node_id}


async def _ensure_exists(session, node_id: str) -> None:
    """Raise 404 if the node doesn't exist (vs. existing but having no results)."""
    result = await session.run("MATCH (o {node_id: $node_id}) RETURN o LIMIT 1",
                               node_id=node_id)
    found = await result.single()
    if found is None:
        raise HTTPException(status_code=404,
                            detail=f"Node '{node_id}' not found in topology graph")