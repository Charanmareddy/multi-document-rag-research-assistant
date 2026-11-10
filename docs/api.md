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

Uploads validate PDF readability, preserve basic PDF metadata, and deduplicate by SHA-256 within a collection. ZIP paths are checked before safe basename staging; per-file and archive expansion limits apply. Indexing and research endpoints are not available yet.
