"""Turn Microsoft GraphRAG query context into the graph view."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from app.runtime import IndexedGraph

_SKIP_COLUMNS = {
    "in_context",
    "embedding",
    "description_embedding",
    "full_content_embedding",
    "vector",
}

_KIND_NAMES = {
    "entities": "entity",
    "relationships": "relationship",
    "reports": "community",
    "sources": "chunk",
    "text_units": "chunk",
    "claims": "claim",
}


def graph_payload(index: IndexedGraph) -> dict:
    nodes = []
    titles: dict[str, str] = {}
    for row in index.entities.itertuples(index=False):
        entity_id = _text(_field(row, "id"))
        title = _text(_field(row, "title")) or entity_id
        titles[entity_id] = title
        nodes.append(
            {
                "id": entity_id,
                "name": title,
                "type": _text(_field(row, "type")) or "entity",
                "description": _text(_field(row, "description")),
            }
        )

    by_title = {title.casefold(): entity_id for entity_id, title in titles.items()}
    edges = []
    for row in index.relationships.itertuples(index=False):
        source = _endpoint(_field(row, "source"), titles, by_title)
        target = _endpoint(_field(row, "target"), titles, by_title)
        edges.append(
            {
                "id": _text(_field(row, "id")),
                "source": source,
                "target": target,
                "description": _text(_field(row, "description")),
            }
        )
    return {"nodes": nodes, "edges": edges}


def present_context(index: IndexedGraph, context) -> tuple[list[dict], list[str], list[str]]:
    """Return context rows plus the entity and relationship ids to highlight."""
    frames = list(_frames(context))
    items: list[dict] = []
    node_ids: list[str] = []
    edge_ids: list[str] = []
    payload = graph_payload(index)
    title_to_id = {node["name"].casefold(): node["id"] for node in payload["nodes"]}
    edges_by_pair: dict[tuple[str, str], list[str]] = {}
    for edge in payload["edges"]:
        edges_by_pair.setdefault((edge["source"], edge["target"]), []).append(edge["id"])

    for kind, frame in frames:
        view = _included(frame)
        label = _KIND_NAMES.get(kind, kind)
        for offset, row in enumerate(view.to_dict(orient="records")):
            items.append(
                {
                    "kind": label,
                    "id": _row_id(row, f"{kind}-{offset}"),
                    "text": _row_text(row),
                }
            )
        if kind == "entities":
            node_ids.extend(_entity_ids(view, title_to_id))
        elif kind == "relationships":
            edge_ids.extend(_relationship_ids(view, title_to_id, edges_by_pair))
        elif kind == "reports":
            node_ids.extend(_community_entity_ids(index, view))

    return items, _unique(node_ids), _unique(edge_ids)


def _frames(context) -> Iterable[tuple[str, pd.DataFrame]]:
    if isinstance(context, dict):
        pairs = context.items()
    elif isinstance(context, list):
        pairs = ((f"context-{index}", item) for index, item in enumerate(context))
    else:
        return
    for kind, value in pairs:
        if isinstance(value, pd.DataFrame):
            yield str(kind).lower(), value


def _included(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "in_context" not in frame.columns:
        return frame
    return frame[frame["in_context"].fillna(False).astype(bool)]


def _entity_ids(frame: pd.DataFrame, title_to_id: dict[str, str]) -> list[str]:
    column = "entity" if "entity" in frame.columns else "title" if "title" in frame.columns else None
    if column is None:
        return []
    found = []
    for value in frame[column].tolist():
        entity_id = title_to_id.get(_text(value).casefold())
        if entity_id:
            found.append(entity_id)
    return found


def _relationship_ids(
    frame: pd.DataFrame,
    title_to_id: dict[str, str],
    edges_by_pair: dict[tuple[str, str], list[str]],
) -> list[str]:
    if "source" not in frame.columns or "target" not in frame.columns:
        return []
    found = []
    for row in frame.to_dict(orient="records"):
        source = title_to_id.get(_text(row.get("source")).casefold())
        target = title_to_id.get(_text(row.get("target")).casefold())
        if source and target:
            found.extend(edges_by_pair.get((source, target), []))
    return found


def _community_entity_ids(index: IndexedGraph, frame: pd.DataFrame) -> list[str]:
    if frame.empty or "id" not in frame.columns or "community" not in index.communities.columns:
        return []
    selected = {_text(value) for value in frame["id"].tolist()}
    found = []
    for row in index.communities.itertuples(index=False):
        if _text(_field(row, "community")) not in selected:
            continue
        for entity_id in _as_list(_field(row, "entity_ids")):
            found.append(_text(entity_id))
    return found


def _row_text(row: dict) -> str:
    parts = []
    for name, value in row.items():
        if name in _SKIP_COLUMNS:
            continue
        text = _text(value)
        if text:
            parts.append(text)
    text = " — ".join(parts)
    if len(text) > 700:
        return text[:697] + "..."
    return text or "Empty context row."


def _row_id(row: dict, fallback: str) -> str:
    value = _text(row.get("id"))
    return value or fallback


def _endpoint(value, titles: dict[str, str], by_title: dict[str, str]) -> str:
    text = _text(value)
    if text in titles:
        return text
    return by_title.get(text.casefold(), text)


def _field(row, name: str):
    if name not in row._fields:
        return ""
    return getattr(row, name)


def _as_list(value) -> list:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_text(item) for item in value if _text(item))
    return str(value).strip()


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered
