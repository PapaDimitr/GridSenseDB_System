"""/grid endpoints — backed by Neo4j (fault-propagation traversal).

Sync routes (like sensors.py): the neo4j sync driver is blocking, so FastAPI
runs these in its threadpool.
"""
from fastapi import APIRouter, HTTPException

from db.neo4j import get_driver
from models.graph import AffectedNode, FaultImpactResponse

router = APIRouter(prefix="/grid", tags=["Grid Topology"])


@router.get("/fault-impact/{node_id}", response_model=FaultImpactResponse)
def get_fault_impact(node_id: str, max_depth: int = 6):
    """Return every node that loses supply if `node_id` trips (downstream)."""
    if not 1 <= max_depth <= 10:
        raise HTTPException(status_code=400,
                            detail="max_depth must be between 1 and 10")

    # max_depth is a validated int, so it is safe to inline into the pattern.
    # (Cypher does NOT allow a parameter for the *1..N variable-length bound.)
    cypher = f"""
    MATCH path = (origin {{node_id: $node_id}})
                 -[:FEEDS|SUPPLIES|CONNECTS_TO*1..{max_depth}]->(downstream)
    RETURN labels(downstream)[0] AS node_type,
           downstream.node_id    AS node_id,
           downstream.name       AS name,
           length(path)          AS depth
    ORDER BY depth
    """

    driver = get_driver()
    with driver.session() as session:
        records = session.run(cypher, node_id=node_id).data()
        if not records:
            # No downstream nodes — distinguish "leaf node" from "doesn't exist".
            exists = session.run(
                "MATCH (o {node_id: $node_id}) RETURN o LIMIT 1",
                node_id=node_id,
            ).single()
            if exists is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Node '{node_id}' not found in topology graph",
                )

    affected = [AffectedNode(**r) for r in records]
    return FaultImpactResponse(
        origin_id=node_id,
        affected_nodes=affected,
        total_affected=len(affected),
    )
