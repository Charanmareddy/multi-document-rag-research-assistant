# Multi-Document RAG Research Assistant

Research smarter — ask questions across entire libraries of documents.

A local-first research application for organizing PDF collections, indexing page-attributed evidence, searching across documents, comparing sources, and exporting cited research reports.

## Features

- Create collections and upload individual PDFs, batches, or ZIP archives.
- Validate PDF readability, preserve PDF metadata, detect duplicates, and safely check ZIP paths.
- Extract text by page and build document excerpt, section, and retrieval chunks with page attribution.
- Index chunks in persistent local Qdrant using Gemini, OpenAI, or Sentence Transformers embeddings.
- Search with BM25, dense retrieval, or hybrid Reciprocal Rank Fusion; filter by document and author.
- Optionally rerank with Cohere or a local cross-encoder.
- Ask questions and receive source-grounded answers with document/page citations, agreement findings, and potential contradictions.
- Compare selected documents, save DOCX research reports, and view collection analytics.
- Use a Streamlit interface or the FastAPI REST API.

See [docs/architecture.md](docs/architecture.md) for component design and [docs/api.md](docs/api.md) for endpoints.

## Project status and limitations

The application code covers the planned collection, indexing, retrieval, reranking, QA, comparison, reporting, analytics, and evaluation workflows. The automated tests use mocks for external embedding, vector-store, and LLM calls. A real 50+ PDF benchmark and live provider integration have **not** yet been verified; do not treat the project as performance-validated.

- Scanned PDFs without selectable text need OCR, which is not implemented.
- Gemini and OpenAI are the supported LLM providers. Anthropic is not implemented.
- The API has no user authentication. Keep this development app bound to localhost; do not expose it to the public internet.
- Python 3.14.2 was available in the development environment, but a fresh dependency install has not been verified. If installation fails, try Python 3.12 and report the error.

## Requirements

- Python 3.10 or newer.
- A Google Gemini API key for the default embedding and answer providers, or configure OpenAI/local embeddings as described below.
- Internet access for Gemini/OpenAI API calls. The local Qdrant database itself does not require a separate Qdrant server.
- Disk space for uploaded PDFs, SQLite metadata, the Qdrant index, and any downloaded local embedding/reranker models.

## Quick start — Windows PowerShell

Run these commands from a terminal after cloning the repository:

```powershell
cd multi-document-rag-research-assistant
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` in a text editor and set `GOOGLE_API_KEY` to your own key. Do not commit or send this file. It is excluded by `.gitignore`.

If PowerShell blocks virtual-environment activation, use this for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Start the backend in the first terminal:

```powershell
uvicorn backend.app.main:app --reload
```

Start the Streamlit app in a second terminal from the project folder, with the virtual environment activated:

```powershell
streamlit run frontend/app.py
```

Open the local Streamlit URL printed in the terminal (normally `http://localhost:8501`). The API docs are at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs), and its health check is [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health). The first API startup creates the local SQLite tables and upload folder. Qdrant storage is created when indexing begins.

### macOS / Linux

```bash
cd multi-document-rag-research-assistant
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
uvicorn backend.app.main:app --reload
```

In a second terminal, activate `.venv` again and run `streamlit run frontend/app.py`.

## Provider configuration

Default `.env` values use Gemini for both answer generation and embeddings:

```dotenv
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your-key
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-001
```

For OpenAI, set `LLM_PROVIDER=openai`, choose an available `LLM_MODEL`, and set `OPENAI_API_KEY`. To use OpenAI embeddings too, set `EMBEDDING_PROVIDER=openai` and select an available embeddings model in `EMBEDDING_MODEL`. Local `sentence-transformers` is an embeddings option only; answer generation still needs Gemini or OpenAI credentials. The first local model use may download weights. `RERANKER=none` disables reranking by default. To use Cohere, set `RERANKER=cohere` and `COHERE_API_KEY`; local reranking uses `RERANKER=local` and downloads the configured cross-encoder if needed. Restart the backend after changing `.env`.

The Settings page and `GET /api/v1/settings` show provider names and whether required credentials are configured, never the credential values. If credentials or optional dependencies are unavailable, indexing or generation reports an error; it does not return a fabricated answer.

## First manual test

1. Start both the API and Streamlit processes.
2. In **Collections**, create a collection and upload one or more text-based PDFs.
3. Click **Index** and refresh the job status until it completes. Check the document status, page count, and chunk count.
4. In **Research Assistant**, ask a question answerable from the PDFs. Try `bm25` first, then `hybrid`; check the citation document and page against the source PDF.
5. Select at least two documents in **Comparison** and review each cited excerpt.
6. Generate a report in **Reports**, download the DOCX, and open it to inspect citations and excerpts.
7. Review **Analytics**, then delete the test documents or collection when finished.

For a fuller manual checklist, expected behaviors, and troubleshooting, see [TESTING_GUIDE.md](TESTING_GUIDE.md).

## Automated tests

From the project root with the virtual environment active:

```bash
python -m compileall -q backend frontend evaluation scripts tests
python -m pytest -q
```

The current suite contains 21 tests. Tests for indexing and answer synthesis use fake providers; a passing unit suite does not verify API keys, Qdrant persistence, external model responses, or 50+ PDF capacity.

## Evaluation and 50+ PDF benchmark

No answer-quality or performance scores are claimed without a real corpus and ground truth. See [evaluation/README.md](evaluation/README.md) and the dataset schema in `evaluation/datasets/README.md`. Retrieval evaluation accepts JSONL rows with a question and actual relevant chunk UUIDs:

```bash
python -m evaluation.retrieval_evaluation evaluation/datasets/your_queries.jsonl --collection-id YOUR_COLLECTION_ID --mode hybrid --top-k 10
```

To measure ingest/index/retrieval performance, provide a directory with at least 50 unique, readable PDFs and run:

```powershell
python scripts/benchmark_50plus.py C:\path\to\test-pdfs --mode hybrid --output evaluation\results\run.json
```

Add `--queries evaluation\datasets\your_queries.jsonl` for retrieval timings. Add `--run-llm` to measure answer-generation latency too; that requires working LLM credentials. The script creates a new collection and records observed timing and processing counts. It does not calculate answer accuracy.

## Project layout

- `backend/app`: FastAPI routes, configuration, SQLAlchemy models, processing, retrieval, RAG, reporting, and analytics.
- `frontend`: Streamlit pages and API client.
- `docs`: API and architecture notes.
- `evaluation`: retrieval and citation metrics, datasets, and evaluation guidance.
- `scripts`: real-corpus benchmark tooling.
- `tests`: automated tests.
- `data`: local database, uploads, Qdrant index, and generated reports (ignored by Git).

## Screenshots

Screenshots are not included yet.
