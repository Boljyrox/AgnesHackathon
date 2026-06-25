-- Migration 002 — projects.goals (Requirement 3: Project Goals)
-- Apply with:  psql "$DATABASE_URL" -f app/database/migrations/002_project_goals.sql
-- (New deployments get it via `python -m app.database.init_db`.)

ALTER TABLE projects ADD COLUMN IF NOT EXISTS goals TEXT;
