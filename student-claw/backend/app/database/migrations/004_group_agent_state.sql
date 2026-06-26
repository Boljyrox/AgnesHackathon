-- Migration 004 — Multi-Mode Group Agent state on projects.
-- Apply with:  psql "$DATABASE_URL" -f app/database/migrations/004_group_agent_state.sql

ALTER TABLE projects ADD COLUMN IF NOT EXISTS group_admin_id  BIGINT;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS group_mode      VARCHAR(20) NOT NULL DEFAULT 'uninitialized';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS bot_active      BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS allowed_models  JSONB       NOT NULL DEFAULT '{}'::jsonb;

-- Backward-compat: existing groups are already project-tracking and active,
-- so keep them working (only brand-new groups start 'uninitialized').
UPDATE projects SET group_mode = 'projects'
 WHERE group_mode = 'uninitialized';
