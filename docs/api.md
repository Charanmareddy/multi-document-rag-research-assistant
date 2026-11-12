# API

Interactive OpenAPI documentation is available at `/docs` while the API is running.

## Foundation and collection management

- `GET /api/v1/health`
- `POST /api/v1/collections` (JSON: `name`, optional `description`)
- `GET /api/v1/collections`
- `GET /api/v1/collections/{collection_id}`
- `DELETE /api/v1/collections/{collection_id}`
- `POST /api/v1/documents/upload` (multipart: `collection_id`, one or more `files`)
- `POST /api/v1/documents/upload-zip` (multipart: `collection_id`, `file`)
- `GET /api/v1/documents` (optional `collection_id` query filter)
- `GET /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/indexing/start` (JSON: `collection_id`, optional `document_ids`)
- `GET /api/v1/indexing/status/{job_id}`
- `POST /api/v1/research/search` (JSON: query, collection, retrieval mode, filters, top-K)
- `POST /api/v1/research/query` (same inputs plus optional reranking; returns answer, citations, agreements, contradictions)
- `GET /api/v1/settings` (non-secret provider/model and credential-presence status)
- `POST /api/v1/reports/generate`
- `GET /api/v1/reports?collection_id=...`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/reports/{report_id}/download`
- `GET /api/v1/analytics/overview?collection_id=...`
- `GET /api/v1/analytics/topics?collection_id=...`
- `GET /api/v1/analytics/document-relevance?collection_id=...`
- `GET /api/v1/analytics/research-gaps?collection_id=...`

Uploads validate PDF readability, preserve basic PDF metadata, and deduplicate by SHA-256 within a collection. ZIP paths are checked before safe basename staging; per-file and archive expansion limits apply.

Indexing is queued in a FastAPI background task and can be polled by job ID. It extracts text by page, stores document/section/retrieval hierarchy with page attribution, batches embeddings, and incrementally upserts vectors to Qdrant. Documents that fail are marked `index_failed` and can be retried by starting indexing again. Embedding credentials are configured in `.env`; the selected provider/model identity is persisted, and changing it requires an explicit fresh index. Scanned PDFs without selectable text currently fail with an OCR-required message.

The evidence search endpoint supports `dense`, `bm25`, and `hybrid` modes, optional document/author filters, configurable top-K, and document-overview routing. Hybrid results use Reciprocal Rank Fusion. Dense/hybrid modes need the configured embedding provider and Qdrant; BM25 works from the locally stored chunk records without either service.

The query endpoint runs the selected retrieval strategy, optional reranking, and configured LLM synthesis. It returns page-level citation mappings, source excerpts, agreement/contradiction candidates, and per-stage timings. Model citations are validated against retrieved source IDs; unknown source labels cause a failed response. Cross-document findings must reference at least two documents. Cohere/local reranking is optional and falls back to the initial retrieval order on error. The LLM and evidence indexing require configured credentials/services; no mock answer is returned when they are missing.

`POST /api/v1/research/compare` accepts at least two document IDs and runs retrieval within each document separately; it returns 422 if fewer than two documents contribute evidence. Report generation reuses the grounded query workflow and saves a DOCX plus report history. Analytics returns indexed counts, cited-document frequency, and exploratory TF-IDF vocabulary candidates. Sparse terms are review prompts rather than claims that a field has a research gap.

Indexing status includes elapsed, extraction, embedding, and vector-store timings. For a representative 50+ PDF run, use `scripts/benchmark_50plus.py`; the script creates a new collection and saves observed throughput/latency data under the ignored evaluation results directory.
