# Multi-Document RAG Research Assistant

Research smarter — ask questions across entire libraries of documents.

An extensible local-first research application for managing PDF collections, indexing page-grounded evidence, and answering questions with citations. The repository is being built milestone by milestone; see [docs/architecture.md](docs/architecture.md) for the initial architecture and current scope.

## Current milestone

Milestones 1–11 are implemented in code: collection and document APIs, safe PDF/ZIP uploads, page-preserving extraction, hierarchical chunks, embedding adapters, Qdrant indexing jobs, dense/BM25/hybrid retrieval, reranking, grounded Gemini/OpenAI synthesis, validated citations, comparison, report history and DOCX export, overview analytics, TF-IDF topic candidates, Streamlit workflows, and reproducible evaluation utilities. Live service integration and the realistic 50+ PDF benchmark still need to be run with a configured environment and representative corpus.

## Requirements

- Python 3.10 or newer. The initial development environment reports Python 3.14.2; confirm third-party package availability for that interpreter before installation.
- SQLite (included with Python).
- Optional API keys and local services are documented in `.env.example` as integrations are added.

## Run locally

Create a Python 3.10+ virtual environment, install `requirements.txt`, copy `.env.example` to `.env`, and set `GOOGLE_API_KEY` for the default Gemini embedding and answer providers. Qdrant uses persistent local storage under `data/qdrant`. Start the API with `uvicorn backend.app.main:app --reload` and the UI with `streamlit run frontend/app.py`. Use the app for collection management, PDF/ZIP uploads, indexing, research questions, comparisons, reports, and analytics. API docs are at `/docs`; `/api/v1/health` checks the backend. Run `python -m pytest -q` for the automated suite (currently 20 tests).

## Project layout

- `backend/app`: API, configuration, database, and service modules.
- `frontend`: Streamlit user interface.
- `docs`: architecture and API notes.
- `evaluation`: reproducible evaluation utilities and datasets.
- `tests`: automated tests.

## Evaluation

No retrieval or answer quality results are claimed without a populated ground-truth dataset. See `evaluation/README.md` for the methodology. Run retrieval evaluation with `python -m evaluation.retrieval_evaluation evaluation/datasets/your_queries.jsonl --collection-id <id> --mode hybrid --top-k 10`; save reviewed outputs under the ignored `evaluation/results/` directory. Human answer-quality review uses the template in `evaluation/datasets/human_review_template.json`.

To measure the end-to-end 50+ PDF target, run `python scripts/benchmark_50plus.py C:\path\to\test-pdfs --queries evaluation\datasets\your_queries.jsonl --mode hybrid --run-llm`. This uploads and indexes at least 50 unique PDFs in a new collection and records actual timings. `--run-llm` requires a working LLM configuration. The script does not infer accuracy scores.

## Screenshots

Screenshots are not included yet.
