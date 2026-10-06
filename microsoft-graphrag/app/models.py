from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    mode: Literal["local", "global"]


class ContextItem(BaseModel):
    kind: str
    id: str
    text: str


class QueryResponse(BaseModel):
    answer: str
    mode: Literal["local", "global"]
    highlight_node_ids: list[str]
    highlight_edge_ids: list[str]
    context: list[ContextItem]
    note: str


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    description: str


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    description: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class StatusResponse(BaseModel):
    indexed: bool
    entity_count: int = 0
    relationship_count: int = 0
    community_count: int = 0
    detail: str = ""
