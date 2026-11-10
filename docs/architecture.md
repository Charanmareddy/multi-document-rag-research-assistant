# Architecture and implementation plan

## Architecture

The application uses a modular, local-first design. Streamlit is the presentation layer and calls a FastAPI REST service. FastAPI routes validate inputs and delegate to service modules. SQLAlchemy stores durable collection, document, job, query, and report metadata in SQLite, with PostgreSQL migration kept possible through portable models. PDF extraction and chunking preserve page provenance. Provider interfaces isolate embedding, vector storage, LLM generation, and reranking. Retrieval combines independently ranked dense and BM25 results with reciprocal rank fusion; synthesis only receives retrieved evidence and returns citation metadata.

Qdrant local persistence is the first vector backend. Embedding model identity and dimensions are recorded with index metadata; a model change requires an explicit re-index. The default app must report missing provider credentials instead of fabricating completions. Uploaded text is untrusted evidence and never trusted as instructions.

## Milestones

1. Foundation: configuration, logging, SQLAlchemy, FastAPI health endpoint, Streamlit entry point.
2. Collections and safe PDF/ZIP upload, metadata, hashes, status, deletion.
3. Extraction, page-preserving hierarchical chunks, configurable embeddings, Qdrant indexing.
4. Dense and BM25 retrieval, metadata filters, document routing, RRF.
5. Optional Cohere/local reranking and latency measurement.
6. Evidence-grounded multi-document answers and citation generation.
7. Comparisons, agreement and contradiction candidates with evidence.
8. Structured reports, DOCX export and report history.
9. Collection analytics and topic/research-gap exploration.
10. Streamlit integration and polished workflows.
11. Retrieval, citation, answer, cross-document and performance evaluation.
12. Documentation, compatibility and release review.

Each milestone should add focused tests before claiming the capability is working. The acceptance goal of 50+ PDFs requires a representative end-to-end benchmark including extraction, indexing, retrieval, and query latency; upload success alone is insufficient.

## Initial compatibility notes

The inspected interpreter is Python 3.14.2. This is newer than the broad Python 3.10+ baseline and binary-package support can vary by package. No dependencies were installed during initial inspection. `requirements.txt` uses bounded minimum versions; resolve and install them in a dedicated virtual environment and verify the actual wheel support before relying on Python 3.14. If any dependency lacks support, Python 3.12 is a practical compatibility fallback.

## Evaluation methodology

Keep a versioned JSONL corpus of queries with expected document IDs and page/chunk evidence, plus reference answers where available. Report Precision@K, Recall@K, MRR, and NDCG@K for retrieval; evaluate citation correctness and faithfulness against retrieved evidence with human review and explicit rubrics. Track extraction, embedding, retrieval, reranking, and end-to-end latency separately. Record dataset, configuration, provider/model versions, and run timestamp. Never publish invented scores.
