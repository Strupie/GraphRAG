# GraphRAG concept

A small farm-monitoring knowledge graph with local and global search. The graph is dummy data. Answers come from an OpenAI-compatible language model, using only the retrieved context.

Local search matches entity names in the question, walks one hop, and sends those relationships plus the linked source text. Global search sends every community summary in one call. A larger GraphRAG global search map-reduces over many community reports.

## Setup

```powershell
uv sync
Copy-Item .env.example .env
```

Edit `.env` and set `LLM_API_KEY`. `LLM_BASE_URL` and `LLM_MODEL` default to OpenAI `gpt-4o-mini`. The same client works with any OpenAI-compatible server, including Ollama:

```
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2
```

The app refuses to start when `LLM_API_KEY` is empty.

## Run

```powershell
uv run python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Example questions

- Local: Why did the Riverside vat alarm last Tuesday?
- Global: What are the main operational risks across the monitored farms?

## Microsoft GraphRAG alternative

`microsoft-graphrag/` indexes the same farm notes with Microsoft GraphRAG and serves local and global search on http://127.0.0.1:8001. See `microsoft-graphrag/README.md`.
