PRAGMA journal_mode=WAL;

-- Files table linked to Chainlit threads via thread_id string
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT, 
    path TEXT NOT NULL,
    type TEXT,
    summary TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_files_thread ON files(thread_id);