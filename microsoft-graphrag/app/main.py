"""Farm monitoring search using Microsoft GraphRAG."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from graphrag.api import global_search, local_search

from app.context import graph_payload, present_context
from app.models import (
    ContextItem,
    GraphEdge,
    GraphNode,
    GraphResponse,
    QueryRequest,
    QueryResponse,
    StatusResponse,
)
from app.runtime import ROOT, community_level, load_index, prepare

STATIC = ROOT / "static"
INDEX_HINT = (
    "The Microsoft GraphRAG index has not been built. From the microsoft-graphrag "
    "folder, run: uv run python -m app.index"
)
RESPONSE_TYPE = "A few short sentences."


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.config = prepare()
    app.state.index = await load_index(app.state.config)
    yield


app = FastAPI(title="Microsoft GraphRAG farm graph", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
def status() -> StatusResponse:
    indexed = app.state.index
    if indexed is None:
        return StatusResponse(indexed=False, detail=INDEX_HINT)
    return StatusResponse(
        indexed=True,
        entity_count=len(indexed.entities),
        relationship_count=len(indexed.relationships),
        community_count=len(indexed.community_reports),
        detail="Indexed with Microsoft GraphRAG.",
    )


@app.get("/api/graph")
def graph() -> GraphResponse:
    indexed = _require_index()
    payload = graph_payload(indexed)
    return GraphResponse(
        nodes=[GraphNode(**node) for node in payload["nodes"]],
        edges=[GraphEdge(**edge) for edge in payload["edges"]],
    )


@app.post("/api/query")
async def query(body: QueryRequest) -> QueryResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question.")
    indexed = _require_index()
    level = community_level(indexed.communities)
    try:
        if body.mode == "local":
            answer, context = await local_search(
                config=app.state.config,
                entities=indexed.entities,
                communities=indexed.communities,
                community_reports=indexed.community_reports,
                text_units=indexed.text_units,
                relationships=indexed.relationships,
                covariates=indexed.covariates,
                community_level=level,
                response_type=RESPONSE_TYPE,
                query=question,
            )
            note = (
                "Microsoft GraphRAG local search: embed the question, match entities, "
                "then add their relationships, community reports, and source text."
            )
        else:
            answer, context = await global_search(
                config=app.state.config,
                entities=indexed.entities,
                communities=indexed.communities,
                community_reports=indexed.community_reports,
                community_level=level,
                dynamic_community_selection=False,
                response_type=RESPONSE_TYPE,
                query=question,
            )
            note = (
                "Microsoft GraphRAG global search: map each community report to "
                "scored points, then reduce those points into the answer."
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    items, node_ids, edge_ids = present_context(indexed, context)
    return QueryResponse(
        answer=answer if isinstance(answer, str) else str(answer),
        mode=body.mode,
        highlight_node_ids=node_ids,
        highlight_edge_ids=edge_ids,
        context=[ContextItem(**item) for item in items],
        note=note,
    )


def _require_index():
    indexed = app.state.index
    if indexed is None:
        raise HTTPException(status_code=409, detail=INDEX_HINT)
    return indexed
