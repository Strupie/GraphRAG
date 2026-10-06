"""Farm-monitoring GraphRAG concept."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.llm import complete, load_settings
from app.models import (
    ContextItem,
    GraphEdge,
    GraphNode,
    GraphResponse,
    QueryRequest,
    QueryResponse,
)
from app.retrieve import load_graph, search

STATIC = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = load_settings()
    app.state.graph = load_graph()
    yield


app = FastAPI(title="GraphRAG concept", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/graph")
def graph() -> GraphResponse:
    loaded = app.state.graph
    return GraphResponse(
        nodes=[
            GraphNode(
                id=entity["id"],
                name=entity["name"],
                type=entity["type"],
                description=entity["description"],
            )
            for entity in loaded.entities.values()
        ],
        edges=[
            GraphEdge(
                id=rel["id"],
                source=rel["source"],
                target=rel["target"],
                description=rel["description"],
            )
            for rel in loaded.relationships
        ],
    )


@app.post("/api/query")
async def query(body: QueryRequest) -> QueryResponse:
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Enter a question.")
    try:
        retrieved = search(app.state.graph, question, body.mode)
        answer = await complete(app.state.settings, retrieved.messages)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return QueryResponse(
        answer=answer,
        mode=body.mode,
        highlight_node_ids=retrieved.highlight_node_ids,
        highlight_edge_ids=retrieved.highlight_edge_ids,
        context=[ContextItem(**item) for item in retrieved.context],
        note=retrieved.note,
    )
