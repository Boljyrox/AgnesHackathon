-- Migration 003 — extend project_status enum (Requirement 4: /status, /celebrate)
-- Apply with:  psql "$DATABASE_URL" -f app/database/migrations/003_project_status_values.sql
-- Note: ADD VALUE cannot run inside a transaction that then uses the value, so
-- run these statements on their own (psql autocommits each).

ALTER TYPE project_status ADD VALUE IF NOT EXISTS 'upcoming';
ALTER TYPE project_status ADD VALUE IF NOT EXISTS 'completed';
