-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Core tables
CREATE TABLE IF NOT EXISTS findings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  program TEXT NOT NULL,
  asset TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  severity TEXT CHECK (severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')) NOT NULL,
  status TEXT CHECK (status IN ('NEW','IN_REVIEW','HIL_APPROVED','SUBMITTED','RESOLVED','REJECTED','DUPLICATE')) NOT NULL DEFAULT 'NEW',
  scope_json JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,                                -- http_trace, poc, screenshot, video, log, etc.
  uri TEXT NOT NULL,                                 -- path or object storage URL
  sha256 BYTEA NOT NULL,                             -- content hash
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hil_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  approved_by TEXT NOT NULL,                         -- human approver identity
  approved_at TIMESTAMPTZ,
  status TEXT CHECK (status IN ('PENDING','APPROVED','DENIED')) NOT NULL DEFAULT 'PENDING',
  checklist JSONB NOT NULL DEFAULT '{}'::jsonb,      -- evidence checklist statuses
  notes TEXT,
  UNIQUE (finding_id)
);

CREATE TABLE IF NOT EXISTS reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
  content_hash BYTEA NOT NULL,
  manifest_hash BYTEA NOT NULL,                      -- hash of artifact manifest
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Vector embeddings (pgvector)
-- Adjust dimension according to model (e.g., 384/512/768)
CREATE TABLE IF NOT EXISTS embeddings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scope TEXT NOT NULL,                               -- e.g., 'finding','http_body','report','cti'
  ref_type TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  model TEXT NOT NULL,
  dim INT NOT NULL,
  vec VECTOR(768) NOT NULL,
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_embeddings_scope ON embeddings(scope);
CREATE INDEX IF NOT EXISTS idx_embeddings_ref ON embeddings(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_vec ON embeddings USING ivfflat (vec vector_cosine_ops) WITH (lists = 100);

-- Provider registry metadata (no secrets)
CREATE TABLE IF NOT EXISTS providers (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  market TEXT NOT NULL,                              -- healthcare, finance, ecommerce, gov, supply_chain
  category TEXT NOT NULL,                            -- osint, cti, certs, code, etc.
  docs_url TEXT,
  signup_url TEXT,
  auth_type TEXT,                                    -- api_key, oauth, none
  quota TEXT,
  rate_limit TEXT,
  pii_flags TEXT,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Immutable audit (Merkle roots + entries summary)
CREATE TABLE IF NOT EXISTS audit_merkle_roots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id TEXT NOT NULL,
  root_hash BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Program scope policies
CREATE TABLE IF NOT EXISTS program_scopes (
  program TEXT PRIMARY KEY,
  allowed_assets TEXT[] DEFAULT NULL,
  excluded_assets TEXT[] DEFAULT NULL,
  allowed_domains TEXT[] DEFAULT NULL,
  excluded_domains TEXT[] DEFAULT NULL,
  min_severity TEXT CHECK (min_severity IN ('INFO','LOW','MEDIUM','HIGH','CRITICAL')) DEFAULT 'LOW',
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
