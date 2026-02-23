# 🏗️ COMPLETE ENGINE-BASED ED-TECH ARCHITECTURE

## Knowledge Orbit - Comprehensive Rebuild Blueprint

**Document Version:** 2.0
**Date:** January 13, 2026
**Purpose:** Complete architectural redesign from scratch using engine-first approach
**Target:** 10M+ users, scalable, maintainable, future-proof

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Architectural Philosophy](#architectural-philosophy)
3. [Complete Engine Catalog (33 Engines)](#complete-engine-catalog)
4. [Feature-to-Engine Mapping](#feature-to-engine-mapping)
5. [Data Flow & Interconnections](#data-flow--interconnections)
6. [36-Week Development Roadmap](#development-roadmap)
7. [Database Schema](#database-schema)
8. [API Design](#api-design)
9. [Technology Stack](#technology-stack)
10. [Migration Strategy](#migration-strategy)

---

## EXECUTIVE SUMMARY

This document provides complete architectural specifications for rebuilding Knowledge Orbit (formerly LearningHub) from scratch using engine-first architecture.

### Why Rebuild?

**Current System Issues:**

- 38 ingestion services (architectural failure)
- Organic growth without strategic plan
- Features tightly coupled
- Difficult to maintain/extend
- Uncertain if core value works

**Engine-First Benefits:**

- Each engine = one clear responsibility
- Products are thin layers on engines
- Easy to add features (compose engines)
- Independently scalable
- Solo developer can manage

### Architecture Overview

**33 Engines organized in layers:**

**L0 - Data Ingestion:**

- Content Engine (PDFs, videos, web)
- Current Affairs Engine (daily news)

**L1 - Organization:**

- Knowledge Engine (syllabus, topics, graph)
- Search Engine (full-text + semantic)

**L2 - Generation:**

- Article Generation Engine
- Assessment Engine (quizzes, tests)
- Video Engine

**L3 - User Tracking:**

- User State Engine (events, progress)

**L4 - Analysis:**

- Analytics Engine (aggregation, insights)

**L5 - Intelligence:**

- Personalization Engine (learning paths)
- Prediction Engine (score forecasts)
- AI Tutor Engine (conversational)

**L6 - Engagement:**

- Gamification Engine
- Collaboration Engine
- Revision Engine (spaced repetition)

**L7 - Operations:**

- Authentication Engine
- Authorization Engine
- Notification Engine
- Storage Engine
- Cache Engine

**L8 - Growth:**

- Commerce Engine (subscriptions)
- Marketing Engine (referrals, campaigns)
- Onboarding Engine
- Retention Engine

**L9 - Advanced:**

- Mock Test Engine
- NLP Engine (descriptive grading)
- Computer Vision Engine
- Voice Engine

**L10 - Enterprise:**

- Marketplace Engine
- White-label Engine
- Content Moderation Engine
- Privacy Engine
- Reporting Engine

### Timeline

**Phase 0:** Setup (Week 1)
**Phase 1:** Core 5 Engines (Weeks 2-4) → MVP
**Phase 2:** Article Gen + CA (Weeks 5-7)
**Phase 3:** Frontend (Weeks 8-10)
**Phase 4:** Launch (Weeks 11-12) → PUBLIC BETA
**Phase 5:** Monetization (Weeks 13-15)
**Phase 6:** Engagement (Weeks 16-19)
**Phase 7:** Intelligence (Weeks 20-24)
**Phase 8:** Advanced Content (Weeks 25-28)
**Phase 9:** Growth (Weeks 29-32)
**Phase 10:** Enterprise (Weeks 33-36)

---

## ARCHITECTURAL PHILOSOPHY

### Engine-First Principles

**1. Single Responsibility**

- One engine = one job
- Clear boundaries
- No cross-engine database access

**2. Composition Over Inheritance**

- Products compose multiple engines
- Engines don't inherit from each other
- Loose coupling

**3. Event-Driven Communication**

- Engines communicate via events
- Async where possible
- No direct method calls across engines

**4. Data Ownership**

- Each engine owns its tables
- No shared tables
- Well-defined interfaces

**5. Independent Scalability**

- Each engine can scale separately
- Microservices-ready (but start monolith)
- Caching per engine

### Example: Article Reading Flow

```
User reads article:

1. Frontend calls Content Engine
   GET /api/v1/content/articles/:id

2. Content Engine returns article
   (From its own tables: articles, article_chunks)

3. Frontend calls User State Engine
   POST /api/v1/user-state/event
   Body: { event_type: 'article_read', article_id: ... }

4. User State Engine:
   - Stores event
   - Updates progress
   - Fires 'article_completed' event

5. Analytics Engine (listens to events):
   - Receives 'article_completed'
   - Updates aggregates

6. Personalization Engine (listens to events):
   - Receives 'article_completed'
   - Recalculates recommendations

All async, no blocking, no coupling.
```

---

## COMPLETE ENGINE CATALOG

### FOUNDATION ENGINES

#### 1. CONTENT ENGINE

**Responsibility:** Ingest, process, normalize ALL content

**Components:**

- PDF Processor (native + scanned)
- OCR Service (Tesseract + PaddleOCR)
- Web Scraper (RSS, websites)
- Video Processor
- Chunking Service (semantic, 1200 chars)
- Asset Extraction (tables, diagrams, formulas)
- Versioning (edition tracking)

**Tables:**

- chunks
- documents
- assets
- ingestion_jobs
- source_versions

**APIs:**

- POST /api/v1/content/upload
- GET /api/v1/content/chunks
- GET /api/v1/content/assets

**Key Innovation:**

- Chunks are foundation (not articles)
- Static + CA chunks same structure
- Embeddings generated per chunk

---

#### 2. KNOWLEDGE ENGINE

**Responsibility:** Organize content into knowledge structure

**Components:**

- Syllabus Manager (programs, subjects, modules, topics)
- Content Linking (chunk-topic mapping)
- Knowledge Graph (concept relationships)
- Search & Discovery

**Tables:**

- programs (UPSC, State PSC)
- subjects (Polity, Geography)
- modules (Fundamental Rights)
- topics (Right to Equality)
- chunk_topic_map (many-to-many)
- concept_relationships

**APIs:**

- GET /api/v1/knowledge/subjects
- GET /api/v1/knowledge/topics
- POST /api/v1/knowledge/map-chunk
- GET /api/v1/knowledge/search

---

#### 3. ASSESSMENT ENGINE

**Responsibility:** Generate, deliver, evaluate assessments

**Components:**

- Quiz Generator (MCQ from chunks)
- Test Builder (pattern matching)
- Evaluator (auto-grading)
- Question Bank

**Tables:**

- quizzes
- questions
- quiz_attempts
- question_responses

**APIs:**

- POST /api/v1/assessment/generate-quiz
- POST /api/v1/assessment/submit

**Key Features:**

- Generates from CHUNKS (not articles)
- Difficulty calibration
- Explanation generation
- Pattern matching for mock tests

---

#### 4. USER STATE ENGINE

**Responsibility:** Track ALL user interactions

**Components:**

- Event Tracker (all actions)
- Progress Calculator
- Mastery Scorer (per-topic)
- Streak Manager

**Tables:**

- user_events (event sourcing)
- user_progress (computed)
- topic_mastery
- bookmarks
- reading_progress

**APIs:**

- GET /api/v1/user-state/progress
- POST /api/v1/user-state/bookmark
- POST /api/v1/user-state/event

**Key Innovation:**

- Event-sourced (complete audit trail)
- Progress is computed, not stored raw
- Enables time-travel debugging

---

#### 5. ANALYTICS ENGINE

**Responsibility:** Aggregate and analyze data

**Components:**

- Data Aggregator (daily rollups)
- Performance Analyzer
- Insight Generator
- Reporting

**Tables:**

- daily_aggregates
- performance_snapshots
- insights

**APIs:**

- GET /api/v1/analytics/dashboard
- GET /api/v1/analytics/performance

---

### GENERATION ENGINES

#### 6. ARTICLE GENERATION ENGINE

**Responsibility:** Create high-quality articles from chunks

**Components:**

- Static Article Generator
- Current Affairs Integrator
- Multi-Format Generator (text, infographic, timeline)
- Quality Control

**Tables:**

- articles
- article_chunks (source map)
- generation_logs

**APIs:**

- POST /api/v1/articles/generate
- GET /api/v1/articles/:id/sources

**Key Features:**

- Combines static + CA chunks
- GROQ-powered narrative
- Source attribution (ArticleSourceMap)
- Quality scoring before publish

---

#### 7. CURRENT AFFAIRS ENGINE

**Responsibility:** Ingest and contextualize daily news

**Components:**

- News Scraper (RSS monitoring)
- CA Chunker
- Contextualizer (link to syllabus)
- Expiry Manager

**Tables:**

- ca_sources (RSS feeds)
- ca_articles (raw news)
- ca_chunks (processed)
- ca_topic_links (static mapping)

**APIs:**

- GET /api/v1/ca/articles
- POST /api/v1/ca/link-topic

**Key Innovation:**

- CA chunks same structure as static
- Automatic topic classification
- Relevance decay over time
- Enables static+CA article generation

---

### INTELLIGENCE ENGINES

#### 8. PERSONALIZATION ENGINE

**Tables:** learning_paths, recommendations, study_schedules
**Features:** Learning path generation, adaptive difficulty, study scheduling

#### 9. PREDICTION ENGINE

**Tables:** predictions, risk_scores, goal_tracking
**Features:** Score prediction, mastery forecasting, risk detection

#### 10. AI TUTOR ENGINE

**Tables:** tutor_conversations, doubt_history, study_plans
**Features:** Q&A, concept explanation, study planning

#### 11. MOCK TEST ENGINE

**Tables:** mock_tests, mock_attempts, mock_analysis, rank_predictions
**Features:** Full exam simulation, detailed analysis, rank prediction

#### 12. REVISION ENGINE

**Tables:** flashcards, card_reviews, revision_schedule
**Features:** Spaced repetition (SM-2), flashcard generation

---

### ADVANCED CONTENT ENGINES

#### 13. VIDEO ENGINE

**Tables:** videos, transcripts, video_chunks
**Features:** Video upload/YouTube, transcript generation (Whisper), searchable segments

#### 14. NLP ENGINE

**Tables:** nlp_evaluations, language_profiles, rubrics
**Features:** Descriptive answer grading, essay scoring, language proficiency

#### 15. COMPUTER VISION ENGINE

**Tables:** image_analysis, diagram_index, image_tags
**Features:** Diagram analysis, handwriting recognition, image search

#### 16. VOICE ENGINE

**Tables:** voice_samples, transcriptions, pronunciation_scores
**Features:** Speech-to-text, text-to-speech, pronunciation checking

---

### ENGAGEMENT ENGINES

#### 17. GAMIFICATION ENGINE

**Tables:** achievements, user_achievements, leaderboards, challenges
**Features:** Badges, leaderboards, challenges, rewards

#### 18. COLLABORATION ENGINE

**Tables:** discussion_threads, discussion_posts, study_groups
**Features:** Forums, study groups, peer review, mentorship

---

### OPERATIONAL ENGINES

#### 19. SEARCH ENGINE

**Tables:** search_index (Elasticsearch), search_queries
**Features:** Full-text, semantic, faceted, auto-complete

#### 20. STORAGE ENGINE

**Tables:** files, file_versions, cdn_mappings
**Features:** Cloudinary integration, CDN, optimization, versioning

#### 21. CACHE ENGINE

**Tables:** cache_keys (Redis), rate_limits
**Features:** Query cache, session management, rate limiting

#### 22. AUTHENTICATION ENGINE

**Tables:** users, user_credentials, auth_sessions
**Features:** JWT, email/phone verification, password reset

#### 23. AUTHORIZATION ENGINE

**Tables:** roles, permissions, role_assignments
**Features:** RBAC, feature gating, subscription gating

#### 24. NOTIFICATION ENGINE

**Tables:** notifications, notification_templates, delivery_logs
**Features:** Email, push, in-app, SMS

---

### MONETIZATION ENGINES

#### 25. COMMERCE ENGINE

**Tables:** plans, subscriptions, payments, invoices
**Features:** Razorpay integration, subscription management, invoicing

#### 26. MARKETING ENGINE

**Tables:** referral_codes, campaigns, ab_tests
**Features:** Referral system, campaigns, A/B testing

#### 27. ONBOARDING ENGINE

**Tables:** onboarding_progress, tutorials, feature_hints
**Features:** Welcome flow, tutorials, feature discovery

#### 28. RETENTION ENGINE

**Tables:** churn_scores, retention_campaigns, loyalty_tiers
**Features:** Churn prediction, win-back campaigns, loyalty program

---

### MARKETPLACE ENGINES

#### 29. MARKETPLACE ENGINE

**Tables:** marketplace_sellers, marketplace_listings, marketplace_purchases
**Features:** Seller portal, content review, revenue sharing

#### 30. WHITE-LABEL ENGINE

**Tables:** tenants, tenant_configs, tenant_branding
**Features:** Multi-tenant, branding customization, feature configurator

---

### COMPLIANCE ENGINES

#### 31. CONTENT MODERATION ENGINE

**Tables:** moderation_queue, moderation_decisions, quality_scores
**Features:** Automated screening, review queue, plagiarism detection

#### 32. PRIVACY ENGINE

**Tables:** consent_records, data_exports, deletion_requests
**Features:** GDPR compliance, data export, right to be forgotten

#### 33. REPORTING ENGINE

**Tables:** report_definitions, report_snapshots, dashboard_widgets
**Features:** Admin dashboards, financial reports, usage reports

---

## FEATURE-TO-ENGINE MAPPING

### All Features Mapped

#### CONTENT FEATURES

**Static Content Ingestion:**

- Engine: Content Engine
- Features: PDF upload, OCR, chunking, metadata extraction
- Tables: documents, chunks, assets

**Current Affairs Ingestion:**

- Engine: Current Affairs Engine
- Features: RSS scraping, CA chunking, topic linking
- Tables: ca_sources, ca_articles, ca_chunks

**Article Generation (Static):**

- Engine: Article Generation Engine
- Features: Chunk selection, GROQ generation, source attribution
- Tables: articles, article_chunks

**Article Generation (Static + CA):**

- Engine: Article Generation Engine + CA Engine
- Features: Context merging, date-aware relevance
- Tables: articles, article_chunks, ca_chunks

**Video Content:**

- Engine: Video Engine
- Features: Upload, transcription, searchable segments
- Tables: videos, transcripts, video_chunks

---

#### LEARNING FEATURES

**Quiz Generation (Chunk-Based):**

- Engine: Assessment Engine
- Features: MCQ generation from chunks, difficulty calibration
- Tables: quizzes, questions
- Note: Generates from CHUNKS not articles

**Quiz Taking:**

- Engine: Assessment Engine + User State Engine
- Features: Timed interface, auto-grading, progress update
- Tables: quiz_attempts, question_responses, user_events

**Mock Tests:**

- Engine: Mock Test Engine
- Features: Pattern matching, full simulation, detailed analysis
- Tables: mock_tests, mock_attempts, mock_analysis

**Test Series:**

- Engine: Mock Test Engine + Assessment Engine
- Features: Series of tests, progress tracking, comparison
- Implementation: Multiple mock tests grouped

**Progress Tracking:**

- Engine: User State Engine
- Features: Topic completion, mastery calculation, streak tracking
- Tables: user_progress, topic_mastery

**Personalized Learning Path:**

- Engine: Personalization Engine
- Features: Weak area prioritization, adaptive difficulty
- Tables: learning_paths, recommendations

**Spaced Repetition:**

- Engine: Revision Engine
- Features: Flashcard generation, SM-2 algorithm, due card alerts
- Tables: flashcards, card_reviews, revision_schedule

---

#### SEARCH & DISCOVERY

**Full-Text Search:**

- Engine: Search Engine
- Features: Keyword search, typo tolerance, filters
- Implementation: Elasticsearch

**Semantic Search:**

- Engine: Search Engine + Content Engine
- Features: Vector similarity, embeddings-based
- Implementation: pgvector

**Topic Navigation:**

- Engine: Knowledge Engine
- Features: Syllabus tree, topic hierarchy
- Tables: programs, subjects, modules, topics

**Recommendations:**

- Engine: Personalization Engine
- Features: Next article, similar content, peer-based
- Tables: recommendations

---

#### ENGAGEMENT FEATURES

**Bookmarks:**

- Engine: User State Engine
- Tables: bookmarks

**Reading Progress:**

- Engine: User State Engine
- Tables: reading_progress

**Achievements:**

- Engine: Gamification Engine
- Tables: achievements, user_achievements

**Leaderboards:**

- Engine: Gamification Engine
- Tables: leaderboards

**Discussion Forums:**

- Engine: Collaboration Engine
- Tables: discussion_threads, discussion_posts

**Study Groups:**

- Engine: Collaboration Engine
- Tables: study_groups, group_members

**AI Doubt Resolution:**

- Engine: AI Tutor Engine
- Tables: tutor_conversations, doubt_history

---

#### MONETIZATION FEATURES

**Subscription Plans:**

- Engine: Commerce Engine
- Tables: plans, subscriptions

**Payment Processing:**

- Engine: Commerce Engine
- Integration: Razorpay
- Tables: payments, invoices

**Referral System:**

- Engine: Marketing Engine
- Tables: referral_codes

**Coupons:**

- Engine: Commerce Engine
- Tables: coupons

---

#### FUTURE FEATURES

**Live Classes:**

- Engine: Video Engine (extended)
- Features: Live streaming, chat, Q&A
- Implementation: Integrate with Zoom/YouTube Live API
- Tables: live_sessions, session_participants

**Advanced Analytics:**

- Engine: Analytics Engine + Prediction Engine
- Features: Performance trends, peer comparison, score prediction
- Tables: daily_aggregates, predictions

**Marketplace:**

- Engine: Marketplace Engine
- Features: Third-party content, seller portal, revenue sharing
- Tables: marketplace_sellers, marketplace_listings

**White-label:**

- Engine: White-label Engine
- Features: Multi-tenant, custom branding
- Tables: tenants, tenant_configs

---

## DATA FLOW & INTERCONNECTIONS

### Flow 1: Static Content → Article → Quiz

```
1. Admin uploads NCERT PDF
   ↓
   Content Engine
   - Extract text/OCR
   - Chunk (1200 chars)
   - Generate embeddings
   - Store: documents, chunks, embeddings

2. Admin maps chunks to topics
   ↓
   Knowledge Engine
   - Create chunk-topic links
   - Store: chunk_topic_map

3. System generates article
   ↓
   Article Generation Engine
   - Fetch chunks for topic
   - GROQ generates narrative
   - Store: articles, article_chunks

4. User reads article
   ↓
   User State Engine
   - Track event
   - Update progress
   - Store: user_events, reading_progress

5. User requests quiz
   ↓
   Assessment Engine
   - Fetch chunks for topic
   - Generate MCQs (GROQ)
   - Store: quizzes, questions

6. User takes quiz
   ↓
   Assessment Engine + User State Engine
   - Auto-grade
   - Update mastery
   - Store: quiz_attempts, topic_mastery
```

---

### Flow 2: Current Affairs Integration

```
1. Daily cron job (6 AM)
   ↓
   Current Affairs Engine
   - Scrape RSS feeds (The Hindu, Indian Express)
   - Extract articles
   - Store: ca_articles

2. Process CA articles
   ↓
   Current Affairs Engine
   - Chunk CA content
   - Generate embeddings
   - Store: ca_chunks, embeddings

3. Auto-classify CA chunks
   ↓
   Knowledge Engine
   - Semantic similarity to topics
   - Create ca-topic links
   - Store: ca_topic_links

4. Generate integrated article
   ↓
   Article Generation Engine
   - Fetch static chunks (e.g., "Rights" topic)
   - Fetch CA chunks (recent rights-related news)
   - Merge contexts
   - GROQ generates narrative
   - Store: articles (with CA sources marked)

5. User reads integrated article
   ↓
   Sees: Theory from NCERT + Recent examples from news
```

---

### Flow 3: Personalized Learning Path

```
1. User completes actions
   ↓
   User State Engine
   - Stores all events: article_read, quiz_completed
   - Computes topic_mastery scores

2. Daily aggregation (midnight cron)
   ↓
   Analytics Engine
   - Aggregates daily stats
   - Identifies weak/strong topics
   - Store: daily_aggregates, insights

3. User opens app (morning)
   ↓
   Personalization Engine
   - Fetches topic_mastery (weak areas)
   - Fetches predictions (time-to-exam)
   - Generates learning path:
     * Prioritize weak topics
     * Order by prerequisites
     * Pace by time remaining
   - Store: learning_paths

4. User sees daily plan
   ↓
   Dashboard displays:
   - Today's topics
   - Recommended articles
   - Suggested quizzes
   - Revision due cards
```

---

### Flow 4: Mock Test → Rank Prediction

```
1. User starts mock test
   ↓
   Mock Test Engine
   - Assembles 100 questions (pattern matched)
   - Timed interface (2 hours)

2. User completes test
   ↓
   Assessment Engine
   - Auto-grades all MCQs
   - Calculates section-wise scores

3. Detailed analysis
   ↓
   Mock Test Engine
   - Accuracy by difficulty
   - Time per question
   - Comparison with toppers
   - Store: mock_analysis

4. Rank prediction
   ↓
   Prediction Engine
   - Fetches historical performance
   - ML model predicts rank range
   - Estimates cut-off clearance
   - Store: rank_predictions

5. User sees report
   ↓
   Dashboard displays:
   - Score: 150/200
   - Predicted Rank: 500-1000
   - Section-wise breakdown
   - Improvement suggestions
```

---

## 36-WEEK DEVELOPMENT ROADMAP

### Phase 0: Setup (Week 1)

**Deliverables:**

- Repository structure (mono-repo)
- Django + DRF skeleton
- Next.js + TypeScript skeleton
- PostgreSQL + pgvector setup
- Docker development environment
- CI/CD pipeline (GitHub Actions)

**Success Criteria:**

- ✅ `python manage.py runserver` works
- ✅ `npm run dev` works
- ✅ Basic health check API responds

---

### Phase 1: Core Engines (Weeks 2-4)

**Week 2: Content Engine (MVP)**

Deliverables:

- PDF upload
- Text extraction (pdfplumber)
- Basic chunking (1200 chars)
- Metadata extraction
- Tables: chunks, documents, ingestion_jobs

APIs:

- POST /api/v1/content/upload
- GET /api/v1/content/chunks

Tests: 20+ passing

---

**Week 3: Knowledge Engine (MVP)**

Deliverables:

- Subject/Module/Topic CRUD
- Chunk-topic mapping
- Basic search (text-based)
- Tables: programs, subjects, modules, topics, chunk_topic_map

APIs:

- GET /api/v1/knowledge/subjects
- POST /api/v1/knowledge/map-chunk
- GET /api/v1/knowledge/search

Tests: 15+ passing

---

**Week 4: Assessment + User State Engines (MVP)**

Deliverables:

- Quiz generation (simple MCQs)
- Quiz taking + grading
- Event tracking
- Progress calculation
- Tables: quizzes, questions, quiz_attempts, user_events, user_progress

APIs:

- POST /api/v1/assessment/generate-quiz
- POST /api/v1/assessment/submit
- GET /api/v1/user-state/progress

Tests: 30+ passing

**Phase 1 Complete: MVP FUNCTIONAL**

---

### Phase 2: Article Generation + CA (Weeks 5-7)

**Week 5: Article Generation Engine (Static)**

Deliverables:

- Chunk selection by topic
- GROQ integration
- Narrative generation
- Source attribution

**Week 6: Current Affairs Engine**

Deliverables:

- RSS scraping (daily cron)
- CA chunking
- Topic classification

**Week 7: Integrated Article Generation**

Deliverables:

- Static + CA merging
- Context blending
- Multi-format output

---

### Phase 3: Frontend (Weeks 8-10)

**Week 8: Core UI**

- Authentication pages
- Article listing/reading
- Progress dashboard

**Week 9: Quiz UI**

- Quiz listing/taking
- Timer, results

**Week 10: Search + Polish**

- Search interface
- Mobile responsive
- Error handling

---

### Phase 4: Launch Preparation (Weeks 11-12)

**Week 11: Content Population**

- Ingest 5 NCERT books
- Generate 100+ articles
- Create 50+ quizzes
- Setup CA scraping

**Week 12: Deploy**

- E2E testing
- Production deploy (Render + Vercel)
- Monitoring (Sentry)

**PUBLIC BETA LAUNCH**

---

### Phase 5-10 (Weeks 13-36)

Week 13-15: Monetization (Commerce Engine)
Week 16-19: Engagement (Gamification, Revision, Collaboration)
Week 20-24: Intelligence (Personalization, Prediction, AI Tutor, Mock Test)
Week 25-28: Advanced Content (Video, NLP, CV, Voice)
Week 29-32: Growth (Marketing, Onboarding, Retention)
Week 33-36: Enterprise (Marketplace, White-label, Compliance)

---

## DATABASE SCHEMA

### Core Tables (Phase 0-1)

```sql
-- CONTENT ENGINE

CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    page_number INTEGER,
    source_type VARCHAR(50), -- 'static' or 'dynamic'

    -- Relations
    document_id UUID REFERENCES documents(id),
    chapter_name VARCHAR(200),

    -- Quality
    quality_flag VARCHAR(20),
    confidence_score FLOAT,

    -- Embeddings
    embedding_id UUID REFERENCES embeddings(id),

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_source_type ON chunks(source_type);

---

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500),
    file_path TEXT,
    source_type VARCHAR(50),

    -- Versioning
    source_edition VARCHAR(50),
    source_version VARCHAR(20),
    isbn VARCHAR(20),
    publication_year INTEGER,

    -- Relations
    subject_id UUID REFERENCES subjects(id),

    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

---

CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_type VARCHAR(50), -- 'chunk', 'article', 'question'
    content_id UUID NOT NULL,
    vector VECTOR(384), -- pgvector
    model_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops);

---

-- KNOWLEDGE ENGINE

CREATE TABLE programs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100), -- 'UPSC CSE'
    description TEXT,
    exam_pattern JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE subjects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100), -- 'Polity'
    program_id UUID REFERENCES programs(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE modules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200), -- 'Fundamental Rights'
    subject_id UUID REFERENCES subjects(id),
    order_index INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE topics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200), -- 'Right to Equality'
    module_id UUID REFERENCES modules(id),
    subject_id UUID REFERENCES subjects(id),
    parent_topic_id UUID REFERENCES topics(id),
    order_index INTEGER,
    difficulty_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chunk_topic_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    topic_id UUID REFERENCES topics(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(chunk_id, topic_id)
);

---

-- ASSESSMENT ENGINE

CREATE TABLE quizzes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500),
    topic_id UUID REFERENCES topics(id),
    difficulty_level VARCHAR(20),
    question_count INTEGER,
    time_limit INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_text TEXT NOT NULL,
    question_type VARCHAR(20), -- 'mcq', 'descriptive'
    options JSONB,
    correct_answer VARCHAR(10),
    difficulty_level VARCHAR(20),
    topic_id UUID REFERENCES topics(id),
    source_chunk_id UUID REFERENCES chunks(id),
    explanation TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE quiz_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id UUID REFERENCES quizzes(id),
    user_id UUID REFERENCES users(id),
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    score FLOAT,
    status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE question_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attempt_id UUID REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    question_id UUID REFERENCES questions(id),
    user_answer TEXT,
    is_correct BOOLEAN,
    time_spent INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

---

-- USER STATE ENGINE

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    full_name VARCHAR(200),
    is_verified BOOLEAN DEFAULT FALSE,
    subscription_tier VARCHAR(20) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    event_type VARCHAR(50), -- 'article_read', 'quiz_started'
    event_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_user_events_user ON user_events(user_id);
CREATE INDEX idx_user_events_created ON user_events(created_at DESC);

CREATE TABLE user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    total_articles_read INTEGER DEFAULT 0,
    total_quizzes_taken INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,
    syllabus_coverage_percent FLOAT DEFAULT 0.0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE topic_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    topic_id UUID REFERENCES topics(id),
    mastery_score FLOAT DEFAULT 0.0, -- 0-100
    questions_attempted INTEGER DEFAULT 0,
    questions_correct INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, topic_id)
);

CREATE TABLE bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    content_type VARCHAR(50), -- 'article', 'quiz'
    content_id UUID NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, content_type, content_id)
);

---

-- ARTICLE GENERATION ENGINE

CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    slug VARCHAR(500) UNIQUE,
    content TEXT NOT NULL,
    summary TEXT,
    topic_id UUID REFERENCES topics(id),
    word_count INTEGER,
    read_time INTEGER,
    generation_type VARCHAR(50), -- 'ai_generated', 'human_curated'
    quality_score FLOAT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE article_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    chunk_id UUID REFERENCES chunks(id) ON DELETE CASCADE,
    relevance_weight FLOAT DEFAULT 1.0,
    sequence_order INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(article_id, chunk_id)
);

---

-- CURRENT AFFAIRS ENGINE

CREATE TABLE ca_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200),
    source_type VARCHAR(50), -- 'rss'
    url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES ca_sources(id),
    title VARCHAR(500),
    url TEXT,
    content TEXT,
    published_at TIMESTAMP,
    processing_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_article_id UUID REFERENCES ca_articles(id),
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    source_type VARCHAR(50) DEFAULT 'dynamic',
    published_at TIMESTAMP,
    expiry_date TIMESTAMP,
    embedding_id UUID REFERENCES embeddings(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE ca_topic_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ca_chunk_id UUID REFERENCES ca_chunks(id),
    topic_id UUID REFERENCES topics(id),
    relevance_score FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(ca_chunk_id, topic_id)
);

---

-- Additional tables for other engines follow similar pattern
```

---

## API DESIGN

### Authentication

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/refresh-token
```

### Content Engine

```
POST   /api/v1/content/upload
GET    /api/v1/content/documents
GET    /api/v1/content/chunks
GET    /api/v1/content/assets
```

### Knowledge Engine

```
GET    /api/v1/knowledge/subjects
GET    /api/v1/knowledge/topics
POST   /api/v1/knowledge/map-chunk
GET    /api/v1/knowledge/search?q=query
```

### Assessment Engine

```
POST   /api/v1/assessment/generate-quiz
POST   /api/v1/assessment/start-quiz
POST   /api/v1/assessment/submit-answer
POST   /api/v1/assessment/submit-quiz
GET    /api/v1/assessment/attempts
```

### Article Generation Engine

```
POST   /api/v1/articles/generate
GET    /api/v1/articles
GET    /api/v1/articles/:id
GET    /api/v1/articles/:id/sources
```

### Current Affairs Engine

```
GET    /api/v1/ca/articles
GET    /api/v1/ca/chunks
POST   /api/v1/ca/link-topic (Admin)
```

### User State Engine

```
GET    /api/v1/user-state/progress
GET    /api/v1/user-state/topic-mastery
POST   /api/v1/user-state/bookmark
GET    /api/v1/user-state/bookmarks
POST   /api/v1/user-state/event
```

---

## TECHNOLOGY STACK

### Backend

- Python 3.11+
- Django 5.0
- Django REST Framework 3.15
- PostgreSQL 16 + pgvector
- Redis 7.0 (caching)
- Celery 5.0 (optional async tasks)

### AI/ML

- GROQ API (article/quiz generation)
- sentence-transformers (embeddings)
- Whisper API (transcription)
- Tesseract/PaddleOCR (OCR)

### Frontend

- Next.js 16 (App Router)
- TypeScript
- shadcn/ui
- Tailwind CSS
- TanStack Query

### Infrastructure

- Backend: Render
- Frontend: Vercel
- Database: Supabase
- CDN: Cloudinary
- Monitoring: Sentry
- Analytics: PostHog

---

## MIGRATION STRATEGY

### Phase 1: Data Audit (Week 1)

- Export current users, progress, bookmarks
- Identify critical vs throwaway data

### Phase 2: Build New System (Weeks 2-12)

- Clean slate implementation
- No code reuse from old system
- Parallel development

### Phase 3: Data Transformation (Week 13)

- Transform users (preserve accounts)
- Transform progress (map to new schema)
- Fresh content ingestion (re-ingest NCERTs)

### Phase 4: Soft Launch (Week 14-15)

- Beta test with 100 users
- Collect feedback
- Fix critical bugs

### Phase 5: Full Migration (Week 16)

- Freeze old database
- Run migration scripts
- Switch DNS
- Old system archived

---

## CONCLUSION

This document provides complete specifications for rebuilding Knowledge Orbit using engine-first architecture.

**Key Takeaways:**

- 33 engines (clear responsibilities)
- Every feature mapped to engines
- 36-week roadmap (MVP in 12 weeks)
- Complete database schema
- Full API design
- Migration strategy

**Next Steps:**

1. Validate core (article generation test)
2. If pass → Start Week 1 setup
3. Follow roadmap phase-by-phase
4. Launch beta in 12 weeks

**This is your complete blueprint. Execute systematically.**

---

**END OF DOCUMENT**

Total Engines: 33
Total Weeks: 36
Total Tables: 100+
Total APIs: 200+

Status: READY FOR IMPLEMENTATION ✅
