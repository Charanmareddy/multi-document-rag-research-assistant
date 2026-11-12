# Multi-Document RAG Research Assistant

Research smarter — ask questions across entire libraries of documents.

An extensible local-first research application for managing PDF collections, indexing page-grounded evidence, and answering questions with citations. The repository is being built milestone by milestone; see [docs/architecture.md](docs/architecture.md) for the initial architecture and current scope.

## Current milestone

Milestones 1–6 and the initial UI integration: project structure, configuration, database, FastAPI, Streamlit collection management, PDF/ZIP ingestion, PDF metadata, SHA-256 duplicate detection, safe deletion, page-preserving extraction, hierarchical chunks, Gemini/OpenAI/local embedding adapters, Qdrant indexing jobs, dense and BM25 search, metadata filters, document routing, hybrid RRF, Cohere/local reranking adapters, grounded LLM synthesis, citation validation, agreement/contradiction candidates, and stage latency reporting. The Streamlit app connects to collection, upload, indexing, and research APIs. Full document comparison, report generation, analytics, evaluation, and the 50+ PDF benchmark remain future work.

## Requirements

- Python 3.10 or newer. The initial development environment reports Python 3.14.2; confirm third-party package availability for that interpreter before installation.
- SQLite (included with Python).
- Optional API keys and local services are documented in `.env.example` as integrations are added.

## Run locally

Create an environment with Python 3.10+, install `requirements.txt`, copy `.env.example` to `.env`, and set `GOOGLE_API_KEY` for the default Gemini embedding provider. Qdrant uses persistent local storage under `data/qdrant`. Then run the API with `uvicorn backend.app.main:app --reload` and the UI with `streamlit run frontend/app.py`. The API docs are at `/docs`; `/api/v1/health` reports service readiness. Run `python -m pytest -q` for the implemented foundation and ingestion tests.

## Project layout

- `backend/app`: API, configuration, database, and service modules.
- `frontend`: Streamlit user interface.
- `docs`: architecture and API notes.
- `evaluation`: reproducible evaluation utilities and datasets.
- `tests`: automated tests.

## Evaluation

No retrieval or answer quality results are claimed in this foundation milestone. The planned evaluation methodology is described in `docs/architecture.md` and will be implemented with the retrieval milestones.

## Screenshots

Screenshots will be added after the core interface is implemented.
