from dotenv import load_dotenv
from src.database import get_db_connection

load_dotenv()

DDL_SCRIPT = """
-- 1. NODES: Every entity in the knowledge graph
CREATE TABLE IF NOT EXISTS nodes (
    id           SERIAL PRIMARY KEY,
    label        TEXT NOT NULL,
    type         TEXT NOT NULL,           -- 'subject'|'module'|'topic'|'subtopic'
    level        INT  NOT NULL DEFAULT 1, -- 1=subject 2=module 3=topic 4=subtopic 5=sub-subtopic
    content_body TEXT,                    -- Full Markdown article
    source       TEXT DEFAULT 'synthesized', -- 'ncert'|'synthesized'|'system'
    pdf_source   TEXT,                    -- filename of source PDF (if Mode B)
    word_count   INT  DEFAULT 0,          -- word count of content_body
    created_at   TIMESTAMP DEFAULT NOW()
);

-- 2. EDGES: Directed connections between nodes
CREATE TABLE IF NOT EXISTS edges (
    source_id  INT  REFERENCES nodes(id) ON DELETE CASCADE,
    target_id  INT  REFERENCES nodes(id) ON DELETE CASCADE,
    relation   TEXT DEFAULT 'contains',   -- 'contains'|'related_to'
    PRIMARY KEY (source_id, target_id)
);

-- 3. INGESTION LOGS: Every agent run is tracked
CREATE TABLE IF NOT EXISTS ingestion_logs (
    id            SERIAL PRIMARY KEY,
    topic_name    TEXT,
    status        TEXT,                   -- 'success'|'failed'
    nodes_created INT  DEFAULT 0,
    edges_created INT  DEFAULT 0,
    error_msg     TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- LAYER 1: Book Intelligence Tables
CREATE TABLE IF NOT EXISTS book_plans (
    id                SERIAL PRIMARY KEY,
    subject           TEXT NOT NULL,
    toc_json          JSONB NOT NULL DEFAULT '[]',
    concept_registry  JSONB DEFAULT '{}',
    status            TEXT DEFAULT 'planned',
    created_at        TIMESTAMP DEFAULT NOW()
);

-- LAYER 3: Cross-References
CREATE TABLE IF NOT EXISTS cross_references (
    id           SERIAL PRIMARY KEY,
    source_node  INT REFERENCES nodes(id) ON DELETE CASCADE,
    target_node  INT REFERENCES nodes(id) ON DELETE CASCADE,
    ref_text     TEXT,
    ref_type     TEXT DEFAULT 'see_also',
    created_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE(source_node, target_node)
);
"""

# Upgrade script for existing databases (adds new columns if missing)
UPGRADE_SCRIPT = """
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS pdf_source  TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS word_count  INT DEFAULT 0;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS quality_score    FLOAT DEFAULT 0.0;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS critique_log     TEXT;
ALTER TABLE nodes ADD COLUMN IF NOT EXISTS generation_pass  INT DEFAULT 1;
"""


def build_schema():
    print("━" * 55)
    print("🏗️  ARCHITECT — Building / Verifying Database Schema...")
    print("━" * 55)
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(DDL_SCRIPT)
        cur.execute(UPGRADE_SCRIPT)
        conn.commit()
        conn.close()
        print("✅ Schema ready:")
        print("   nodes         (id, label, type, level, content_body,")
        print("                  source, pdf_source, word_count, created_at)")
        print("   edges         (source_id, target_id, relation)")
        print("   ingestion_logs(id, topic_name, status, nodes/edges counts)")
    except Exception as e:
        print(f"❌ Schema build failed: {e}")
        raise


if __name__ == "__main__":
    build_schema()
