"""Local embedding model registered with Microsoft GraphRAG."""

from __future__ import annotations

from typing import Any

from graphrag_llm.embedding.embedding import LLMEmbedding
from graphrag_llm.types import LLMEmbedding as Embedding
from graphrag_llm.types import LLMEmbeddingResponse, LLMEmbeddingUsage

_REGISTERED = False


class FastEmbedEmbedding(LLMEmbedding):
    """Embeddings from fastembed, used when the chat server has none."""

    def __init__(
        self,
        *,
        model_config,
        tokenizer,
        metrics_store,
        **kwargs: Any,
    ):
        self._tokenizer = tokenizer
        self._metrics_store = metrics_store
        self._model_name = model_config.model
        from fastembed import TextEmbedding

        self._model = TextEmbedding(self._model_name)

    def embedding(self, /, **kwargs) -> LLMEmbeddingResponse:
        raw = kwargs.get("input") or []
        texts = [raw] if isinstance(raw, str) else list(raw)
        vectors = [vector.tolist() for vector in self._model.embed(texts)]
        return LLMEmbeddingResponse(
            object="list",
            data=[
                Embedding(object="embedding", embedding=vector, index=index)
                for index, vector in enumerate(vectors)
            ],
            model=self._model_name,
            usage=LLMEmbeddingUsage(prompt_tokens=0, total_tokens=0),
        )

    async def embedding_async(self, /, **kwargs) -> LLMEmbeddingResponse:
        return self.embedding(**kwargs)

    @property
    def metrics_store(self):
        return self._metrics_store

    @property
    def tokenizer(self):
        return self._tokenizer


def register_fastembed() -> None:
    """Register the fastembed provider before GraphRAG creates an embedding model."""
    global _REGISTERED
    if _REGISTERED:
        return
    from graphrag_llm.embedding.embedding_factory import register_embedding

    register_embedding("fastembed", FastEmbedEmbedding, scope="singleton")
    _REGISTERED = True
