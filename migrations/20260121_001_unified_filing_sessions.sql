-- Unified Filing Platform - Database Migration
-- Date: 2026-01-21
-- Purpose: Add columns for unified session management and fix session orphaning

-- ============================================================================
-- 1. Add user_id and workflow tracking to session_states
-- ============================================================================

-- Add user_id column to link sessions to authenticated users
ALTER TABLE session_states ADD COLUMN user_id TEXT;

-- Track whether session is anonymous or authenticated
ALTER TABLE session_states ADD COLUMN is_anonymous INTEGER NOT NULL DEFAULT 1;

-- Track which workflow type is being used
ALTER TABLE session_states ADD COLUMN workflow_type TEXT; -- 'express'|'smart'|'chat'|'guided'

-- Link to TaxReturnRecord when filing is complete
ALTER TABLE session_states ADD COLUMN return_id TEXT;

-- ============================================================================
-- 2. Create indexes for performance
-- ============================================================================

-- Index for querying user's sessions
CREATE INDEX IF NOT EXISTS idx_session_user ON session_states(user_id);

-- Index for filtering by workflow type
CREATE INDEX IF NOT EXISTS idx_session_workflow ON session_states(workflow_type);

-- Index for linking to tax returns
CREATE INDEX IF NOT EXISTS idx_session_return ON session_states(return_id);

-- Composite index for active user sessions
CREATE INDEX IF NOT EXISTS idx_session_active ON session_states(user_id, expires_at)
WHERE is_anonymous = 0;

-- Index for cleanup of expired sessions
CREATE INDEX IF NOT EXISTS idx_session_expires ON session_states(expires_at);

-- ============================================================================
-- 3. Session transfer tracking (anonymous → authenticated)
-- ============================================================================

CREATE TABLE IF NOT EXISTS session_transfers (
    transfer_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    from_anonymous INTEGER NOT NULL DEFAULT 1,
    to_user_id TEXT NOT NULL,
    transferred_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session_states(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transfer_session ON session_transfers(session_id);
CREATE INDEX IF NOT EXISTS idx_transfer_user ON session_transfers(to_user_id);

-- ============================================================================
-- 4. Add version column for optimistic locking
-- ============================================================================

-- Prevent race conditions when multiple clients update same session
ALTER TABLE session_tax_returns ADD COLUMN version INTEGER NOT NULL DEFAULT 0;

-- ============================================================================
-- 5. Tax return indexes for performance
-- ============================================================================

-- Index for user's returns
CREATE INDEX IF NOT EXISTS idx_return_user ON tax_returns(user_id);

-- Index for filtering by tax year
CREATE INDEX IF NOT EXISTS idx_return_year ON tax_returns(tax_year);

-- Index for status-based queries
CREATE INDEX IF NOT EXISTS idx_return_status ON tax_returns(status);

-- Composite index for user's returns by year
CREATE INDEX IF NOT EXISTS idx_return_user_year ON tax_returns(user_id, tax_year);

-- ============================================================================
-- 6. Backfill existing data
-- ============================================================================

-- Mark all existing sessions as anonymous Express Lane sessions
UPDATE session_states
SET is_anonymous = 1,
    workflow_type = 'express'
WHERE workflow_type IS NULL;

-- ============================================================================
-- ROLLBACK INSTRUCTIONS
-- ============================================================================
-- If needed, run these commands to rollback:
--
-- DROP INDEX IF EXISTS idx_session_user;
-- DROP INDEX IF EXISTS idx_session_workflow;
-- DROP INDEX IF EXISTS idx_session_return;
-- DROP INDEX IF EXISTS idx_session_active;
-- DROP INDEX IF EXISTS idx_session_expires;
-- DROP TABLE IF EXISTS session_transfers;
-- DROP INDEX IF EXISTS idx_return_user;
-- DROP INDEX IF EXISTS idx_return_year;
-- DROP INDEX IF EXISTS idx_return_status;
-- DROP INDEX IF EXISTS idx_return_user_year;
--
-- Note: Column drops require table recreation in SQLite
-- ============================================================================
