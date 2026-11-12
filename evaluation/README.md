# Evaluation methodology

## Retrieval

Use a versioned JSONL dataset containing research queries and ground-truth relevant chunk IDs/pages. Run the same collection, provider/model settings, retrieval mode, and top-K. The script reports Precision@K, Recall@K, MRR, and NDCG@K per query and as an arithmetic mean. Include dataset version, configuration, timestamp, and corpus identity with every saved run.

## Answer quality

Citation precision/recall can be compared with human-annotated expected document/page IDs. Review faithfulness, answer relevance, context relevance, agreement/contradiction quality, and source attribution with a consistent human rubric: score each 1–5 and require a short evidence-based note. Do not replace these judgments with unsupported automated scores.

## Performance and 50+ PDF acceptance

Use a representative collection of at least 50 PDFs and record PDF count, pages, extracted chunks, successful/failed document counts, indexing wall time, embedding time where available, retrieval latency, rerank latency, and end-to-end latency. Repeat runs with the same hardware and model settings. The project does not claim 50+ PDF performance until this is measured on a real collection.
