-- Migration: Add Advisory Reports Tables
-- Date: 2026-01-21
-- Description: Creates tables for storing advisory reports and their sections

-- Create advisory_reports table
CREATE TABLE IF NOT EXISTS advisory_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identifiers
    report_id VARCHAR(100) NOT NULL UNIQUE,
    session_id VARCHAR(100) NOT NULL,

    -- Report metadata
    report_type VARCHAR(50) NOT NULL,
    tax_year INTEGER NOT NULL,

    -- Taxpayer info
    taxpayer_name VARCHAR(200) NOT NULL,
    filing_status VARCHAR(50) NOT NULL,

    -- Financial summary
    current_tax_liability REAL NOT NULL DEFAULT 0.0,
    potential_savings REAL NOT NULL DEFAULT 0.0,
    confidence_score REAL NOT NULL DEFAULT 0.0,
    recommendations_count INTEGER NOT NULL DEFAULT 0,

    -- Report data (JSON)
    report_data TEXT NOT NULL,

    -- PDF info
    pdf_path VARCHAR(500),
    pdf_generated BOOLEAN DEFAULT 0,
    pdf_watermark VARCHAR(50),

    -- Status tracking
    status VARCHAR(20) DEFAULT 'generating',
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    generated_at TIMESTAMP,

    -- Version
    version INTEGER DEFAULT 1
);

-- Create report_sections table
CREATE TABLE IF NOT EXISTS report_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,

    -- Section info
    section_id VARCHAR(100) NOT NULL,
    section_title VARCHAR(200) NOT NULL,
    page_number INTEGER,

    -- Section content (JSON)
    content_data TEXT NOT NULL,

    -- Timestamp
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Foreign key
    FOREIGN KEY (report_id) REFERENCES advisory_reports(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_advisory_reports_report_id ON advisory_reports(report_id);
CREATE INDEX IF NOT EXISTS idx_advisory_reports_session_id ON advisory_reports(session_id);
CREATE INDEX IF NOT EXISTS idx_advisory_reports_status ON advisory_reports(status);
CREATE INDEX IF NOT EXISTS idx_advisory_reports_created_at ON advisory_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_report_sections_report_id ON report_sections(report_id);
CREATE INDEX IF NOT EXISTS idx_report_sections_section_id ON report_sections(section_id);

-- Verify tables created
SELECT 'Advisory Reports tables created successfully!' as message;
SELECT
    name as table_name,
    sql as create_statement
FROM sqlite_master
WHERE type='table'
AND (name='advisory_reports' OR name='report_sections');
