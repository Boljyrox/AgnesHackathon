-- Migration 005 — expenses (Mode C: Expense Tracker)
-- Apply with:  psql "$DATABASE_URL" -f app/database/migrations/005_expenses.sql

CREATE TABLE IF NOT EXISTS expenses (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id              UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    payer_name              VARCHAR(100) NOT NULL,
    payer_telegram_user_id  BIGINT,
    amount                  NUMERIC(10,2) NOT NULL,
    description             VARCHAR(300),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_expenses_project_id ON expenses (project_id);
