-- Initial Schema Creation
-- Date: 2026-01-21
-- Purpose: Create base tables for session persistence

-- Session states table
CREATE TABLE IF NOT EXISTS session_states (
    session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    session_type TEXT NOT NULL DEFAULT 'agent',
    created_at TEXT NOT NULL,
    last_activity TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    data_json TEXT NOT NULL DEFAULT '{}',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    agent_state_blob BLOB
);

-- Document processing results table
CREATE TABLE IF NOT EXISTS document_processing (
    document_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL,
    document_type TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    result_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
);

-- Session tax returns table
CREATE TABLE IF NOT EXISTS session_tax_returns (
    session_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    tax_year INTEGER NOT NULL DEFAULT 2025,
    return_data_json TEXT NOT NULL DEFAULT '{}',
    calculated_results_json TEXT,
    FOREIGN KEY (session_id) REFERENCES session_states(session_id)
);

-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_session_tenant ON session_states(tenant_id);
CREATE INDEX IF NOT EXISTS idx_session_type ON session_states(session_type);
CREATE INDEX IF NOT EXISTS idx_session_expires ON session_states(expires_at);
CREATE INDEX IF NOT EXISTS idx_doc_session ON document_processing(session_id);
CREATE INDEX IF NOT EXISTS idx_doc_tenant ON document_processing(tenant_id);
CREATE INDEX IF NOT EXISTS idx_return_tenant ON session_tax_returns(tenant_id);
CREATE INDEX IF NOT EXISTS idx_return_year ON session_tax_returns(tax_year);
