-- Migration: Add user_id and workflow_type columns to session_states
-- Date: 2026-01-21
-- Purpose: Enable session-to-user linking and workflow triage tracking

-- Add user_id column to link sessions to authenticated users
ALTER TABLE session_states ADD COLUMN user_id TEXT;

-- Add is_anonymous flag to track anonymous vs authenticated sessions
ALTER TABLE session_states ADD COLUMN is_anonymous INTEGER NOT NULL DEFAULT 1;

-- Add workflow_type to track which filing path user chose
-- Values: 'express', 'smart', 'chat', 'guided', NULL (not yet triaged)
ALTER TABLE session_states ADD COLUMN workflow_type TEXT;

-- Add return_id to link to TaxReturnRecord when filing is complete
ALTER TABLE session_states ADD COLUMN return_id TEXT;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_session_user ON session_states(user_id);
CREATE INDEX IF NOT EXISTS idx_session_workflow ON session_states(workflow_type);
CREATE INDEX IF NOT EXISTS idx_session_return ON session_states(return_id);
CREATE INDEX IF NOT EXISTS idx_session_user_active
    ON session_states(user_id, expires_at)
    WHERE is_anonymous = 0;

-- Create session_transfers table to track anonymous-to-user session claims
CREATE TABLE IF NOT EXISTS session_transfers (
    transfer_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    from_anonymous INTEGER NOT NULL DEFAULT 1,
    to_user_id TEXT NOT NULL,
    transferred_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
);

CREATE INDEX IF NOT EXISTS idx_transfer_session ON session_transfers(session_id);
CREATE INDEX IF NOT EXISTS idx_transfer_user ON session_transfers(to_user_id);

-- Add version column for optimistic locking (prevent concurrent edit conflicts)
ALTER TABLE session_tax_returns ADD COLUMN version INTEGER NOT NULL DEFAULT 0;
