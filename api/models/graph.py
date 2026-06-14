from typing import List

from pydantic import BaseModel, Field


class AffectedNode(BaseModel):
    node_id: str
    node_type: str
    name: str | None = None      # not every node label is guaranteed a name
    depth: int


class FaultImpactResponse(BaseModel):
    origin_id: str
    affected_nodes: List[AffectedNode]
    total_affected: int


class RestorePath(BaseModel):
    path: List[str]              # node_ids from supply source → target
    hops: int


class RestorePathsResponse(BaseModel):
    target_id: str
    paths: List[RestorePath]
    total_paths: int


class NodeIn(BaseModel):
    label: str                   # e.g. "Substation" (validated against a whitelist)
    node_id: str
    properties: dict = Field(default_factory=dict)


class RelationshipIn(BaseModel):
    from_node_id: str
    to_node_id: str
    rel_type: str                # FEEDS | SUPPLIES | CONNECTS_TO
    properties: dict = Field(default_factory=dict)
