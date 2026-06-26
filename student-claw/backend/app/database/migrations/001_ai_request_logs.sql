-- Migration 001 — ai_request_logs (Requirement 1: Observability)
-- Apply to an existing database with:
--   psql "$DATABASE_URL" -f app/database/migrations/001_ai_request_logs.sql
-- (New deployments get this table automatically via `python -m app.database.init_db`.)

CREATE TABLE IF NOT EXISTS ai_request_logs (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    chat_id            BIGINT,
    project_id         UUID REFERENCES projects(id) ON DELETE SET NULL,
    kind               VARCHAR(20) NOT NULL,   -- chat | embedding | vision
    model              VARCHAR(100) NOT NULL,
    status             VARCHAR(20) NOT NULL,   -- success | error
    latency_ms         INTEGER,
    request_summary    TEXT,
    response_summary   TEXT,
    request_payload    JSONB NOT NULL DEFAULT '{}'::jsonb,
    response_payload   JSONB NOT NULL DEFAULT '{}'::jsonb,
    error              TEXT,
    prompt_tokens      INTEGER,
    completion_tokens  INTEGER,
    total_tokens       INTEGER
);

CREATE INDEX IF NOT EXISTS ix_ai_request_logs_created_at ON ai_request_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_ai_request_logs_chat_id    ON ai_request_logs (chat_id);
CREATE INDEX IF NOT EXISTS ix_ai_request_logs_kind       ON ai_request_logs (kind);
