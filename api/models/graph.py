from typing import List

from pydantic import BaseModel

class AffectedNode(BaseModel):
    node_id: str
    node_type: str
    name: str | None = None   # not every node label is guaranteed a name
    depth: int

class FaultImpactResponse(BaseModel):
    origin_id: str
    affected_nodes: List[AffectedNode]
    total_affected: int
