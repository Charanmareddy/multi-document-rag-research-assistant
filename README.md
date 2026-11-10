# Multi-Document RAG Research Assistant

Research smarter — ask questions across entire libraries of documents.

An extensible local-first research application for managing PDF collections, indexing page-grounded evidence, and answering questions with citations. The repository is being built milestone by milestone; see [docs/architecture.md](docs/architecture.md) for the initial architecture and current scope.

## Current milestone

Milestones 1–2 foundation and collection management: project structure, configuration, database, FastAPI, Streamlit entry point, collection CRUD, PDF/ZIP ingestion, PDF metadata, SHA-256 duplicate detection, document listing/deletion, and upload security checks. Indexing, retrieval, question answering, reporting, analytics, and evaluation remain future milestones.

## Requirements

- Python 3.10 or newer. The initial development environment reports Python 3.14.2; confirm third-party package availability for that interpreter before installation.
- SQLite (included with Python).
- Optional API keys and local services are documented in `.env.example` as integrations are added.

## Run locally

Create an environment with Python 3.10+, install `requirements.txt`, copy `.env.example` to `.env`, then run the API with `uvicorn backend.app.main:app --reload` and the UI with `streamlit run frontend/app.py`. The API docs are at `/docs`; `/api/v1/health` reports service readiness. Run `python -m pytest -q` for the implemented foundation and ingestion tests.

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
