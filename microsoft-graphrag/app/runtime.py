"""Load Microsoft GraphRAG config and indexed tables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from graphrag_storage import create_storage
from graphrag_storage.tables.table_provider_factory import create_table_provider

from app.embeddings import register_fastembed

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class IndexedGraph:
    entities: pd.DataFrame
    relationships: pd.DataFrame
    communities: pd.DataFrame
    community_reports: pd.DataFrame
    text_units: pd.DataFrame
    covariates: pd.DataFrame | None


def prepare():
    """Move to the project root, register embeddings, and load settings.yaml."""
    os.chdir(ROOT)
    register_fastembed()
    from graphrag.config.load_config import load_config

    return load_config(ROOT)


async def load_index(config) -> IndexedGraph | None:
    """Read the index tables GraphRAG wrote, or return None when they are absent."""
    storage = create_storage(config.output_storage)
    tables = create_table_provider(config.table_provider, storage=storage)
    if not await tables.has("entities"):
        return None

    from graphrag.data_model.data_reader import DataReader

    reader = DataReader(tables)
    covariates = None
    if await tables.has("covariates"):
        covariates = await reader.covariates()
    return IndexedGraph(
        entities=await reader.entities(),
        relationships=await reader.relationships(),
        communities=await reader.communities(),
        community_reports=await reader.community_reports(),
        text_units=await reader.text_units(),
        covariates=covariates,
    )


def community_level(communities: pd.DataFrame) -> int:
    """Use the deepest Leiden level so search can roll up from the full hierarchy."""
    if communities.empty or "level" not in communities.columns:
        return 0
    levels = pd.to_numeric(communities["level"], errors="coerce").dropna()
    if levels.empty:
        return 0
    return int(levels.max())
