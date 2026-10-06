"""Load the dummy knowledge graph and run local or global search."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_STOP = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "and",
    "or",
    "in",
    "on",
    "for",
    "last",
    "did",
    "why",
    "what",
    "how",
    "is",
    "was",
    "were",
    "are",
    "across",
    "main",
    "about",
    "does",
    "do",
    "with",
    "from",
    "by",
    "at",
    "it",
    "its",
    "that",
    "this",
    "which",
    "who",
    "when",
    "where",
    "into",
    "after",
    "before",
    "over",
    "under",
    "all",
    "their",
    "them",
    "they",
    "be",
    "been",
    "have",
    "has",
    "had",
    "not",
    "there",
    "our",
    "your",
}

_LOCAL_SYSTEM = (
    "You answer questions about a farm-monitoring knowledge graph. "
    "Use only the context below. If the context does not support an answer, "
    "say what is missing. Write a short answer in plain sentences and name "
    "the entities you relied on."
)

_GLOBAL_SYSTEM = (
    "You answer questions from community summaries of a farm-monitoring "
    "knowledge graph. This demo sends every community summary in one call. "
    "A full GraphRAG global search map-reduces over many community reports "
    "when the graph is large. Use only these summaries. If they do not "
    "support an answer, say so. Write a short answer in plain sentences."
)


@dataclass
class Graph:
    documents: dict[str, dict]
    chunks: dict[str, dict]
    entities: dict[str, dict]
    relationships: list[dict]
    communities: list[dict]


@dataclass
class Retrieval:
    mode: str
    highlight_node_ids: list[str]
    highlight_edge_ids: list[str]
    context: list[dict]
    messages: list[dict]
    note: str = ""


def load_graph(data_dir: Path | None = None) -> Graph:
    root = data_dir or DATA_DIR
    documents = {item["id"]: item for item in _read(root / "documents.json")}
    chunks = {item["id"]: item for item in _read(root / "chunks.json")}
    entities = {item["id"]: item for item in _read(root / "entities.json")}
    relationships = _read(root / "relationships.json")
    communities = _read(root / "communities.json")
    _validate(documents, chunks, entities, relationships, communities)
    return Graph(documents, chunks, entities, relationships, communities)


def search(graph: Graph, question: str, mode: str) -> Retrieval:
    if mode == "local":
        return local_search(graph, question)
    if mode == "global":
        return global_search(graph, question)
    raise ValueError(f"Unknown search mode: {mode}")


def local_search(graph: Graph, question: str) -> Retrieval:
    seeds = _match_entities(graph, question)
    seed_ids = {entity["id"] for entity in seeds}
    selected_ids = set(seed_ids)
    selected_rels: list[dict] = []

    for rel in graph.relationships:
        if rel["source"] in seed_ids or rel["target"] in seed_ids:
            selected_rels.append(rel)
            selected_ids.add(rel["source"])
            selected_ids.add(rel["target"])

    neighbor_ids = [entity_id for entity_id in selected_ids if entity_id not in seed_ids]
    neighbor_ids.sort(key=lambda entity_id: graph.entities[entity_id]["name"])

    context: list[dict] = []
    for entity in seeds:
        context.append(_entity_item(entity))
    for entity_id in neighbor_ids:
        context.append(_entity_item(graph.entities[entity_id]))
    for rel in selected_rels:
        context.append(_relationship_item(graph, rel))

    chunk_ids: list[str] = []
    for entity in seeds:
        chunk_ids.extend(entity["source_chunk_ids"])
    for rel in selected_rels:
        chunk_ids.extend(rel["source_chunk_ids"])
    for chunk_id in _unique(chunk_ids):
        context.append(_chunk_item(graph, chunk_id))

    if seeds:
        note = "Local search: matched entities, their one-hop neighborhood, and the linked source text."
    else:
        note = "Local search found no entity names in the question."

    ordered_nodes = [entity["id"] for entity in seeds] + neighbor_ids
    return Retrieval(
        mode="local",
        highlight_node_ids=ordered_nodes,
        highlight_edge_ids=[rel["id"] for rel in selected_rels],
        context=context,
        messages=_messages(_LOCAL_SYSTEM, question, context),
        note=note,
    )


def global_search(graph: Graph, question: str) -> Retrieval:
    context = [
        {
            "kind": "community",
            "id": community["id"],
            "text": f"{community['title']}: {community['summary']}",
        }
        for community in graph.communities
    ]
    node_ids = _unique(
        entity_id
        for community in graph.communities
        for entity_id in community["entity_ids"]
    )
    node_set = set(node_ids)
    edge_ids = [
        rel["id"]
        for rel in graph.relationships
        if rel["source"] in node_set and rel["target"] in node_set
    ]
    return Retrieval(
        mode="global",
        highlight_node_ids=node_ids,
        highlight_edge_ids=edge_ids,
        context=context,
        messages=_messages(_GLOBAL_SYSTEM, question, context),
        note=(
            "Global search: every community summary in one call. "
            "A larger graph would map-reduce over those reports."
        ),
    )


def _match_entities(graph: Graph, question: str) -> list[dict]:
    question_tokens = _tokens(question)
    scored: list[tuple[int, dict]] = []
    for entity in graph.entities.values():
        score = _score(entity, question_tokens, question)
        if score > 0:
            scored.append((score, entity))
    if not scored:
        return []
    scored.sort(key=lambda item: (-item[0], item[1]["name"]))
    best = scored[0][0]
    cutoff = max(1, int(best * 0.45))
    return [entity for score, entity in scored if score >= cutoff][:4]


def _score(entity: dict, question_tokens: set[str], question: str) -> int:
    name = entity["name"].lower()
    name_tokens = _tokens(entity["name"])
    description_tokens = _tokens(entity["description"])
    score = 3 * len(question_tokens & name_tokens) + len(question_tokens & description_tokens)
    if name in question.lower():
        score += 5
    return score


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOP and len(token) > 1
    }


def _entity_item(entity: dict) -> dict:
    return {
        "kind": "entity",
        "id": entity["id"],
        "text": f"{entity['name']} ({entity['type']}): {entity['description']}",
    }


def _relationship_item(graph: Graph, rel: dict) -> dict:
    source = graph.entities[rel["source"]]["name"]
    target = graph.entities[rel["target"]]["name"]
    return {
        "kind": "relationship",
        "id": rel["id"],
        "text": f"{source} → {target}: {rel['description']}",
    }


def _chunk_item(graph: Graph, chunk_id: str) -> dict:
    chunk = graph.chunks[chunk_id]
    title = graph.documents[chunk["document_id"]]["title"]
    return {
        "kind": "chunk",
        "id": chunk_id,
        "text": f"{title}: {chunk['text']}",
    }


def _messages(system: str, question: str, context: list[dict]) -> list[dict]:
    if context:
        blocks = "\n".join(f"- {item['text']}" for item in context)
    else:
        blocks = "- No matching graph context."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Question: {question.strip()}\n\nContext:\n{blocks}"},
    ]


def _unique(items) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def _read(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(
    documents: dict[str, dict],
    chunks: dict[str, dict],
    entities: dict[str, dict],
    relationships: list[dict],
    communities: list[dict],
) -> None:
    problems: list[str] = []
    for chunk in chunks.values():
        if chunk["document_id"] not in documents:
            problems.append(f"chunk {chunk['id']} references missing document {chunk['document_id']}")
    for entity in entities.values():
        for chunk_id in entity["source_chunk_ids"]:
            if chunk_id not in chunks:
                problems.append(f"entity {entity['id']} references missing chunk {chunk_id}")
    for rel in relationships:
        for end in (rel["source"], rel["target"]):
            if end not in entities:
                problems.append(f"relationship {rel['id']} references missing entity {end}")
        for chunk_id in rel["source_chunk_ids"]:
            if chunk_id not in chunks:
                problems.append(f"relationship {rel['id']} references missing chunk {chunk_id}")
    for community in communities:
        for entity_id in community["entity_ids"]:
            if entity_id not in entities:
                problems.append(
                    f"community {community['id']} references missing entity {entity_id}"
                )
    if problems:
        raise RuntimeError("Dummy graph is inconsistent:\n" + "\n".join(problems))
