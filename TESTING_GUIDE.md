# Tester Guide

This guide is for a tester cloning the repository on a clean machine. It covers the current implementation and distinguishes mocked tests from live integration checks.

## 1. Set up a clean checkout

Install Python 3.10+ and Git. Clone the repository and enter its folder:

```bash
git clone https://github.com/Charanmareddy/multi-document-rag-research-assistant.git
cd multi-document-rag-research-assistant
```

Create and activate a virtual environment, then install dependencies.

**Windows PowerShell:**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If dependency resolution or installation fails, record the Python version, operating system, full failing package name, and error. Python 3.14 package installation has not been validated from a clean environment; try Python 3.12 and report whether that changes the outcome.

If Python 3.12 is installed, explicitly select it with `py -3.12 -m venv .venv` on Windows or `python3.12 -m venv .venv` on macOS/Linux.

## 2. Configure external providers

Copy `.env.example` to `.env` and provide a Gemini API key for the default setup:

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Edit `.env` locally and set `GOOGLE_API_KEY`. The key is needed for Gemini embeddings and answer generation. Do not commit `.env`, paste the key into a bug report, or send it in chat. The project has no sample key. Alternatively, configure OpenAI credentials/models or local Sentence Transformers embeddings as described in the README; local model weights may be downloaded on first use. Local embeddings do not remove the need for Gemini or OpenAI credentials for answer generation.

Qdrant runs in local persistent mode by default at `data/qdrant`; no server is required. This directory and the SQLite database are generated locally and ignored by Git.

## 3. Start the application

In terminal 1, from the repository root:

```bash
uvicorn backend.app.main:app --reload
```

In terminal 2, activate the same virtual environment, then:

```bash
streamlit run frontend/app.py
```

Open the Streamlit URL printed in terminal 2 (normally `http://localhost:8501`). Use `http://127.0.0.1:8000/docs` to exercise the FastAPI endpoints directly. Keep both processes running during UI testing.

## 4. Run automated checks

From the repository root with the virtual environment active:

```bash
python -m compileall -q backend frontend evaluation scripts tests
python -m pytest -q
```

The current suite has 21 tests. Indexing, reranking fallback, and language-model synthesis tests use fakes/mocks. These tests do not need API credentials, but they also do not prove real Qdrant or model API integration.

## 5. Manual feature checklist

Use non-sensitive, text-based PDFs. For a useful smoke test, choose at least two short PDFs that discuss related topics and have visibly different page content.

- [ ] In **Collections**, create a named collection.
- [ ] Upload one PDF, then upload the same file again. The second upload should be reported as a duplicate.
- [ ] Upload a ZIP containing PDFs. Invalid files should produce per-file errors instead of crashing the app.
- [ ] Upload a corrupt PDF and confirm it is rejected with an understandable error.
- [ ] Start indexing. Refresh the job status and confirm it reaches `completed`, with documents marked `indexed`, page counts, and retrieval chunks.
- [ ] Open **Settings** and confirm the configured provider status appears without revealing any secret value.
- [ ] Ask a question answerable from the PDFs with **BM25** first. Confirm the answer includes a citation whose document and page match the displayed excerpt.
- [ ] If Gemini/OpenAI credentials and Qdrant are configured, repeat with **dense** and **hybrid** retrieval.
- [ ] Compare two indexed documents. Confirm citations come from both selected documents; the API should reject a comparison when fewer than two documents contribute evidence.
- [ ] Generate a DOCX report, download it, open it, and inspect the question, answer, limitations, citations, and supporting excerpts.
- [ ] Review Analytics and verify collection, page, chunk, citation-frequency, and indexing status counts match the test collection.
- [ ] Delete a test document and verify it disappears. Delete the test collection when finished.

Scanned PDFs without selectable text are not currently supported; the indexer reports that OCR is needed.

## 6. Optional real reranker checks

- **Cohere:** set `RERANKER=cohere`, `COHERE_API_KEY`, and optionally `COHERE_RERANK_MODEL`; restart the API. Ask a question and confirm the response reports whether reranking was applied. If the key or provider is unavailable, the system should report the reranking fallback and preserve the original retrieval results.
- **Local cross-encoder:** set `RERANKER=local`; restart the API. The configured model may need to download. Check logs if the request falls back.

## 7. 50+ PDF performance run

Only run this with a representative directory containing at least 50 unique, readable PDFs and enough disk space. The script creates a new collection and retains the uploaded collection in the local database. Use a dedicated test environment, not a production or private-document collection.

```powershell
python scripts/benchmark_50plus.py C:\path\to\test-pdfs --mode hybrid --output evaluation\results\friend-run.json
```

Add `--queries path\to\queries.jsonl` to measure retrieval latency. Add `--run-llm` to measure answer latency too; that requires a working model key. The output reports actual counts and timings; it does not assess answer accuracy. If upload, indexing, or queries fail, keep the report and logs (after removing sensitive data) and note the failing stage.

## 8. Report results

Please include:

- OS and Python version.
- Whether a clean `pip install -r requirements.txt` succeeded.
- Whether health check and Streamlit startup succeeded.
- Which manual checklist items passed or failed.
- Provider choices (names/models only; never keys).
- Error messages with API keys, local usernames, and private document text removed.
- For the benchmark, PDF/page/chunk counts, indexing status, elapsed timings, CPU/RAM if available, and the output JSON.

Do not expose the development API to the public internet; this local app currently has no authentication.
