# Evaluation datasets

Add one JSON object per line to a `.jsonl` dataset file. Keep private document text out of Git when appropriate. A retrieval example schema is:

```json
{"query":"What result did the intervention produce?","relevant_chunk_ids":["<chunk UUID>"],"document_ids":[]}
```

The chunk IDs must come from the actual indexed corpus. Do not use synthetic expected IDs as a reported benchmark. For answer review, record the output, expected sources, and human scores separately; use the rubric in `../README.md`.
