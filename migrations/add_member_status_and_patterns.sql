-- Add active_status column to members table
ALTER TABLE members ADD COLUMN active_status INTEGER DEFAULT 0;

-- Create email_patterns table
CREATE TABLE IF NOT EXISTS email_patterns (
    pattern_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    pattern TEXT NOT NULL,
    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id)
);
