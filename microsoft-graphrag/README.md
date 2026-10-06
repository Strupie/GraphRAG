# Microsoft GraphRAG farm app

The same farm notes as the concept demo, indexed and queried with [Microsoft GraphRAG](https://github.com/microsoft/graphrag) 3.2.

Indexing extracts entities and relationships, clusters them with hierarchical Leiden, and writes community reports. Local search embeds the question and walks the matching entities. Global search map-reduces over those reports.

Chat uses the Ollama model in `.env`. Embeddings use a local `bge-small` model, because the running Ollama server was started without embedding support.

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

`.env.example` points at Ollama:

```
GRAPHRAG_API_KEY=ollama
GRAPHRAG_API_BASE=http://localhost:11434
GRAPHRAG_CHAT_MODEL=llama3.2
```

`GRAPHRAG_API_BASE` is Ollama's native URL. The concept app uses `http://localhost:11434/v1` because it speaks the OpenAI chat API directly.

To use OpenAI for chat instead, set `GRAPHRAG_API_KEY`, `GRAPHRAG_API_BASE=https://api.openai.com/v1`, and `GRAPHRAG_CHAT_MODEL`, then in `settings.yaml` change `model_provider` to `openai` and remove `num_ctx`.

## Index

Indexing calls the local chat model many times. On `llama3.2` that can take a while.

```powershell
uv run python -m app.index
```

## Run

```powershell
uv run python -m uvicorn app.main:app --port 8001
```

Open http://127.0.0.1:8001

The concept app stays on port 8000.

## Example questions

- Local: Why did the Riverside vat alarm last Tuesday?
- Global: What are the main operational risks across the monitored farms?
