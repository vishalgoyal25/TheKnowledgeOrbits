# DATABASE_SCHEMA.md

## TheKnowledgeOrbits — Database Schema

**PKB File #6 | Version: 1.0 | Date: Feb 2026**

---

## 1. SCHEMA OVERVIEW

- All PKs: UUID (gen_random_uuid())
- All tables: `created_at` + `updated_at` timestamps
- Naming: `enginename_modelname`
- FKs: always indexed
- Embeddings: pgvector (384-dim, sentence-transformers)

---

## 2. CORE ENGINE TABLES

### 2.1 CONTENT ENGINE

```sql
CREATE TABLE content_document (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    file_path TEXT NOT NULL,
    source_type VARCHAR(50) NOT NULL,       -- 'static' | 'dynamic'
    source_edition VARCHAR(50),
    isbn VARCHAR(20),
    publication_year INTEGER,
    subject_id UUID REFERENCES knowledge_subject(id),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE content_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER,
    source_type VARCHAR(50) NOT NULL,       -- 'static' | 'dynamic'
    document_id UUID REFERENCES content_document(id) ON DELETE CASCADE,
    chapter_name VARCHAR(200),
    quality_flag VARCHAR(20),
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0.0 AND 1.0),
    embedding_id UUID REFERENCES content_embedding(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE content_embedding (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50) NOT NULL,      -- 'chunk' | 'article' | 'question'
    content_id UUID NOT NULL,
    vector VECTOR(384),
    model_name VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE content_asset (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES content_chunk(id) ON DELETE CASCADE,
    asset_type VARCHAR(50) NOT NULL,        -- 'table' | 'diagram' | 'formula'
    asset_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE content_ingestion_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES content_document(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending'|'processing'|'done'|'failed'
    error_log TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**

```sql
CREATE INDEX idx_chunk_document ON content_chunk(document_id);
CREATE INDEX idx_chunk_source_type ON content_chunk(source_type);
CREATE INDEX idx_embedding_vector ON content_embedding USING ivfflat (vector vector_cosine_ops);
CREATE INDEX idx_asset_chunk ON content_asset(chunk_id);
CREATE INDEX idx_job_document ON content_ingestion_job(document_id);
CREATE INDEX idx_job_status ON content_ingestion_job(status);
```

---

### 2.2 KNOWLEDGE ENGINE

```sql
CREATE TABLE knowledge_program (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,      -- 'UPSC CSE'
    description TEXT,
    exam_pattern JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_subject (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,             -- 'Polity'
    program_id UUID REFERENCES knowledge_program(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_module (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,             -- 'Fundamental Rights'
    subject_id UUID REFERENCES knowledge_subject(id) ON DELETE CASCADE,
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_topic (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,             -- 'Right to Equality'
    module_id UUID REFERENCES knowledge_module(id) ON DELETE CASCADE,
    subject_id UUID REFERENCES knowledge_subject(id),
    parent_topic_id UUID REFERENCES knowledge_topic(id),
    order_index INTEGER DEFAULT 0,
    difficulty_level VARCHAR(20),           -- 'easy'|'medium'|'hard'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE knowledge_chunk_topic_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES content_chunk(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES knowledge_topic(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(chunk_id, topic_id)
);
```

**Indexes:**

```sql
CREATE INDEX idx_subject_program ON knowledge_subject(program_id);
CREATE INDEX idx_module_subject ON knowledge_module(subject_id);
CREATE INDEX idx_topic_module ON knowledge_topic(module_id);
CREATE INDEX idx_topic_parent ON knowledge_topic(parent_topic_id);
CREATE INDEX idx_ctmap_chunk ON knowledge_chunk_topic_map(chunk_id);
CREATE INDEX idx_ctmap_topic ON knowledge_chunk_topic_map(topic_id);
```

---

### 2.3 ASSESSMENT ENGINE

```sql
CREATE TABLE assessment_quiz (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    topic_id UUID REFERENCES knowledge_topic(id),
    difficulty_level VARCHAR(20),
    question_count INTEGER NOT NULL,
    time_limit INTEGER,                     -- seconds
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_question (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL,     -- 'mcq' | 'descriptive'
    options JSONB,                          -- MCQ options array
    correct_answer VARCHAR(10),
    difficulty_level VARCHAR(20),
    topic_id UUID REFERENCES knowledge_topic(id),
    source_chunk_id UUID REFERENCES content_chunk(id),
    explanation TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_quiz_attempt (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID REFERENCES assessment_quiz(id),
    user_id UUID REFERENCES auth_user(id),
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    score FLOAT,
    status VARCHAR(20) DEFAULT 'pending',   -- 'pending'|'active'|'submitted'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE assessment_question_response (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID REFERENCES assessment_quiz_attempt(id) ON DELETE CASCADE,
    question_id UUID REFERENCES assessment_question(id),
    user_answer TEXT,
    is_correct BOOLEAN,
    time_spent INTEGER,                     -- seconds
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**

```sql
CREATE INDEX idx_quiz_topic ON assessment_quiz(topic_id);
CREATE INDEX idx_question_topic ON assessment_question(topic_id);
CREATE INDEX idx_question_chunk ON assessment_question(source_chunk_id);
CREATE INDEX idx_attempt_quiz ON assessment_quiz_attempt(quiz_id);
CREATE INDEX idx_attempt_user ON assessment_quiz_attempt(user_id);
CREATE INDEX idx_response_attempt ON assessment_question_response(attempt_id);
```

---

### 2.4 USER STATE ENGINE

```sql
CREATE TABLE userstate_event (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    event_type VARCHAR(50) NOT NULL,        -- 'article_read'|'quiz_started'|'quiz_completed'
    event_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE userstate_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id) UNIQUE,
    total_articles_read INTEGER DEFAULT 0,
    total_quizzes_taken INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    syllabus_coverage_percent FLOAT DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE userstate_topic_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    topic_id UUID REFERENCES knowledge_topic(id),
    mastery_score FLOAT DEFAULT 0.0,        -- 0-100
    questions_attempted INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, topic_id)
);

CREATE TABLE userstate_bookmark (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    content_type VARCHAR(50) NOT NULL,      -- 'article'|'quiz'|'chunk'
    content_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, content_type, content_id)
);

CREATE TABLE userstate_reading_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    article_id UUID NOT NULL,
    percent_read FLOAT DEFAULT 0.0,
    last_position INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, article_id)
);
```

**Indexes:**

```sql
CREATE INDEX idx_event_user ON userstate_event(user_id);
CREATE INDEX idx_event_created ON userstate_event(created_at DESC);
CREATE INDEX idx_event_type ON userstate_event(event_type);
CREATE INDEX idx_mastery_user ON userstate_topic_mastery(user_id);
CREATE INDEX idx_mastery_topic ON userstate_topic_mastery(topic_id);
CREATE INDEX idx_bookmark_user ON userstate_bookmark(user_id);
```

---

### 2.5 ANALYTICS ENGINE

```sql
CREATE TABLE analytics_daily_aggregate (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    date DATE NOT NULL,
    articles_read INTEGER DEFAULT 0,
    quizzes_taken INTEGER DEFAULT 0,
    total_score FLOAT DEFAULT 0.0,
    time_spent_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, date)
);

CREATE TABLE analytics_insight (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id),
    insight_type VARCHAR(50) NOT NULL,      -- 'weak_topic'|'streak_risk'|'improvement'
    insight_data JSONB DEFAULT '{}',
    generated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);
```

**Indexes:**

```sql
CREATE INDEX idx_aggregate_user ON analytics_daily_aggregate(user_id);
CREATE INDEX idx_aggregate_date ON analytics_daily_aggregate(date);
CREATE INDEX idx_insight_user ON analytics_insight(user_id);
CREATE INDEX idx_insight_type ON analytics_insight(insight_type);
```

---

### 2.6 AUTH ENGINE

```sql
CREATE TABLE auth_user (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,    -- Argon2 only
    full_name VARCHAR(200),
    is_verified BOOLEAN DEFAULT FALSE,
    subscription_tier VARCHAR(20) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE auth_role (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,       -- 'admin'|'content_manager'|'student'|'free_user'
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE auth_role_assignment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth_user(id) ON DELETE CASCADE,
    role_id UUID REFERENCES auth_role(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, role_id)
);
```

**Indexes:**

```sql
CREATE INDEX idx_role_assignment_user ON auth_role_assignment(user_id);
CREATE INDEX idx_role_assignment_role ON auth_role_assignment(role_id);
```

---

### 2.7 ARTICLE GENERATION ENGINE (Phase 2)

```sql
CREATE TABLE article_article (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE,
    content TEXT NOT NULL,
    summary TEXT,
    topic_id UUID REFERENCES knowledge_topic(id),
    word_count INTEGER,
    read_time INTEGER,                      -- minutes
    generation_type VARCHAR(50),            -- 'ai_generated'|'human_curated'
    quality_score FLOAT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE article_source_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES article_article(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES content_chunk(id),
    relevance_weight FLOAT DEFAULT 1.0,
    sequence_order INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, chunk_id)
);
```

**Indexes:**

```sql
CREATE INDEX idx_article_topic ON article_article(topic_id);
CREATE INDEX idx_article_slug ON article_article(slug);
CREATE INDEX idx_sourcemap_article ON article_source_map(article_id);
CREATE INDEX idx_sourcemap_chunk ON article_source_map(chunk_id);
```

---

### 2.8 CURRENT AFFAIRS ENGINE (Phase 2)

```sql
CREATE TABLE ca_source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    source_type VARCHAR(50) DEFAULT 'rss',
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_article (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES ca_source(id),
    title VARCHAR(500) NOT NULL,
    url TEXT,
    content TEXT,
    published_at TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_chunk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_article_id UUID REFERENCES ca_article(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    source_type VARCHAR(50) DEFAULT 'dynamic',
    published_at TIMESTAMP,
    expiry_date TIMESTAMP,
    embedding_id UUID REFERENCES content_embedding(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_topic_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_chunk_id UUID REFERENCES ca_chunk(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES knowledge_topic(id),
    relevance_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ca_chunk_id, topic_id)
);
```

**Indexes:**

```sql
CREATE INDEX idx_ca_article_source ON ca_article(source_id);
CREATE INDEX idx_ca_chunk_article ON ca_chunk(ca_article_id);
CREATE INDEX idx_ca_topiclink_chunk ON ca_topic_link(ca_chunk_id);
CREATE INDEX idx_ca_topiclink_topic ON ca_topic_link(topic_id);
```

---

## 3. RELATIONSHIP SUMMARY

```
auth_user ←────── auth_role_assignment ──→ auth_role
    |
    ├── userstate_event
    ├── userstate_progress
    ├── userstate_topic_mastery ──→ knowledge_topic
    ├── userstate_bookmark
    ├── userstate_reading_progress
    ├── assessment_quiz_attempt ──→ assessment_quiz ──→ knowledge_topic
    └── analytics_daily_aggregate

content_document ──→ content_chunk ──→ content_embedding
                          |
                          ├── content_asset
                          ├── knowledge_chunk_topic_map ──→ knowledge_topic
                          ├── assessment_question
                          └── article_source_map ──→ article_article

knowledge_program → knowledge_subject → knowledge_module → knowledge_topic

ca_source → ca_article → ca_chunk → ca_topic_link → knowledge_topic
```

---

## 4. INDEX STRATEGY

- All ForeignKeys: indexed (mandatory)
- Vector columns: ivfflat index (cosine similarity)
- Frequently queried: user_id, topic_id, created_at, status
- Composite: unique constraints act as indexes automatically

---

## 5. PERFORMANCE NOTES

- userstate_event: append-only, partition by date if grows > 10M rows
- content_embedding: ivfflat tuned for 384-dim vectors
- analytics_daily_aggregate: one row per user per day (bounded growth)
- ca_chunk: expiry_date enables soft-delete cleanup via cron

---

## 6. RESEARCH AGENT ENGINE TABLES (Current Active Build)

All 5 tables are fully isolated — no FK references to any existing engine tables.

```sql
CREATE TABLE research_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    user_id UUID NULL,                    -- NULL = guest user
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                                          -- pending|running|completed|failed
    langfuse_trace_id VARCHAR(200) DEFAULT '',
    retry_count SMALLINT DEFAULT 0,
    search_cache_hit BOOLEAN DEFAULT FALSE,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE research_report (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES research_session(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    summary TEXT DEFAULT '',
    body_md TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    domain VARCHAR(100) DEFAULT '',
    confidence_score FLOAT DEFAULT 0.0,   -- derived from DeepEval (0.0-100.0)
    word_count INTEGER DEFAULT 0,
    is_public BOOLEAN DEFAULT TRUE,
    public_share_token VARCHAR(64) UNIQUE NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE agent_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES research_session(id) ON DELETE CASCADE,
    agent_name VARCHAR(50) NOT NULL,      -- supervisor|planner|search|research|verification|report_generator|reflection
    status VARCHAR(20) NOT NULL,          -- running|completed|failed|retrying
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP NULL,
    duration_ms INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    model_used VARCHAR(100) DEFAULT '',
    provider VARCHAR(20) DEFAULT '',      -- groq|cerebras
    output_summary TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE evaluation_result (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES research_report(id) ON DELETE CASCADE,
    hallucination_score FLOAT DEFAULT 0.0,
    faithfulness_score FLOAT DEFAULT 0.0,
    relevance_score FLOAT DEFAULT 0.0,
    completeness_score FLOAT DEFAULT 0.0,
    overall_score FLOAT DEFAULT 0.0,
    evaluated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE agent_state_snapshot (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES research_session(id) ON DELETE CASCADE,
    node_name VARCHAR(50) NOT NULL,
    sequence_order SMALLINT NOT NULL,     -- 1=supervisor, 2=planner, etc.
    state_json JSONB NOT NULL,            -- full LangGraph state at this node transition
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes:**

```sql
CREATE INDEX idx_research_session_user ON research_session(user_id);
CREATE INDEX idx_research_session_status ON research_session(status);
CREATE INDEX idx_research_report_session ON research_report(session_id);
CREATE INDEX idx_research_report_token ON research_report(public_share_token);
CREATE INDEX idx_agent_log_session ON agent_execution_log(session_id);
CREATE INDEX idx_agent_log_agent ON agent_execution_log(agent_name);
CREATE INDEX idx_eval_report ON evaluation_result(report_id);
CREATE INDEX idx_snapshot_session ON agent_state_snapshot(session_id);
CREATE INDEX idx_snapshot_node ON agent_state_snapshot(node_name);
```
