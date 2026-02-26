# Vector Memory (pgvector)

- Table: embeddings (scope, ref_type, ref_id, model, dim, vec VECTOR(768), meta)
- API:
  - POST /embeddings/index — batch index texts; 768-dim vectors; uses sentence-transformers if available; deterministic hashing fallback otherwise.
  - GET  /embeddings/search?scope=...&query=...&top_k=...
- Index: ivfflat (cosine) created in schema; run ANALYZE after bulk load for best performance.
- Notes: Fallback embeddings enable offline dev; for production enable sentence-transformers and cache model.
