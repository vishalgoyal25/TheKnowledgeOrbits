# CONTENT ENGINE - IMPLEMENTATION GUIDE

**Complements:** ENGINE_BASED_EDTECH_COMPLETE_ARCHITECTURE.md
**Purpose:** Detailed chunking & ingestion implementation
**Principle:** Text-only, simple, scalable

---

## CORE PRINCIPLE

**Focus: TEXT EXTRACTION ONLY (No assets for MVP)**

Reason: Previous 38-service approach over-engineered. Text chunking alone generates quality articles.

---

## CHUNKING STRATEGY

### Fixed Parameters

```python
CHUNK_SIZE = 1200  # characters
CHUNK_OVERLAP = 200  # characters for context continuity
MIN_CHUNK_SIZE = 300  # discard smaller chunks
```

### Algorithm

```
1. Extract full text from PDF (native or OCR)
2. Split by chunk size with overlap
3. Preserve metadata per chunk:
   - document_id
   - page_number
   - chapter_name (detect from headers)
   - chunk_index (sequential)
   - source_type ('static' or 'dynamic')
4. Generate embedding per chunk (384-dim)
5. Store: chunks table + embeddings table
```

### Chapter Detection (Simple)

```python
# Heuristic: First 100 chars of page, look for "Chapter N" pattern
import re

def detect_chapter(text: str) -> str:
    first_100 = text[:100]
    match = re.search(r'Chapter\s+\d+', first_100, re.IGNORECASE)
    if match:
        return match.group()
    return "Unknown"
```

---

## STATIC CONTENT INGESTION (NCERT/Books)

### Input

- PDF file path
- Subject name
- Source edition/version

### Process

```
1. Check if native or scanned PDF
   - Native: Use pdfplumber.extract_text()
   - Scanned: Use Tesseract OCR (page-by-page)

2. Extract text per page

3. For each page:
   - Detect chapter (first occurrence on page)
   - Split text into chunks (1200 chars)
   - Store metadata:
     * page_number
     * chapter_name
     * book_name (from filename)
     * source_edition
     * source_version

4. Generate embeddings (batch all chunks)

5. Store to database
```

### What NOT to Do

❌ Don't extract tables/diagrams (over-engineering)
❌ Don't create 38 services (single ingestion service)
❌ Don't try perfect layout detection (simple text extraction)
❌ Don't process images (text-only for MVP)

---

## CURRENT AFFAIRS INGESTION

### Input

- RSS feed URLs (The Hindu, Indian Express)

### Process

```
1. Daily cron (6 AM): Fetch RSS feeds

2. For each article:
   - Extract: title, URL, content, published_at
   - Store: ca_articles table

3. Chunk CA content:
   - Same chunking logic (1200 chars)
   - Metadata:
     * ca_article_id
     * published_at
     * source_type = 'dynamic'
     * expiry_date = published_at + 180 days

4. Generate embeddings (same model)

5. Auto-link to topics:
   - Vector similarity search
   - Link CA chunks to static topics (threshold > 0.7)
   - Store: ca_topic_links table
```

### What NOT to Do

❌ Don't do NER/entity extraction (over-engineering)
❌ Don't scrape images from news (text-only)
❌ Don't classify sentiment (unnecessary)
❌ Don't process videos (text-only)

---

## EMBEDDING GENERATION

### Model

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
# Dimension: 384
# Fast, good quality for semantic search
```

### Batch Processing

```python
# Generate embeddings in batches (100 chunks at a time)
def generate_embeddings(chunks: List[Chunk]):
    texts = [chunk.chunk_text for chunk in chunks]

    for i in range(0, len(texts), 100):
        batch = texts[i:i+100]
        vectors = model.encode(batch)

        for j, vector in enumerate(vectors):
            Embedding.objects.create(
                content_type='chunk',
                content_id=str(chunks[i+j].id),
                vector=vector.tolist(),
                model_name='all-MiniLM-L6-v2'
            )
```

---

## DATABASE TABLES

### chunks

```sql
CREATE TABLE chunks (
    id UUID PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    page_number INTEGER,
    source_type VARCHAR(50), -- 'static' or 'dynamic'

    document_id UUID REFERENCES documents(id),
    chapter_name VARCHAR(200),
    book_name VARCHAR(200),

    quality_flag VARCHAR(20),
    confidence_score FLOAT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_chunks_source_type ON chunks(source_type);
CREATE INDEX idx_chunks_chapter ON chunks(chapter_name);
```

### embeddings

```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    content_type VARCHAR(50), -- 'chunk'
    content_id UUID NOT NULL,
    vector VECTOR(384), -- pgvector
    model_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_embeddings_vector ON embeddings
USING ivfflat (vector vector_cosine_ops);
```

### ca_chunks (same structure as chunks)

```sql
CREATE TABLE ca_chunks (
    id UUID PRIMARY KEY,
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER,
    source_type VARCHAR(50) DEFAULT 'dynamic',

    ca_article_id UUID REFERENCES ca_articles(id),
    published_at TIMESTAMP,
    expiry_date TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## VERSIONING (CRITICAL)

### Why Important

NCERT updates editions every 2-3 years. Need to ingest multiple editions side-by-side.

### Implementation

```python
# documents table
source_edition = models.CharField(max_length=50)  # 'NCERT 2024'
source_version = models.CharField(max_length=20)  # '1.0'
isbn = models.CharField(max_length=20, blank=True)
publication_year = models.IntegerField()
```

### Usage

```bash
python manage.py ingest_pdf \
    --file="ncert_polity_2024.pdf" \
    --edition="NCERT 2024" \
    --version="1.0" \
    --year=2024
```

---

## LESSONS FROM PREVIOUS FAILURE

### What Went Wrong

1. ❌ 38 services for single engine (over-engineering)
2. ❌ Asset extraction with 90 false positives (wasted effort)
3. ❌ Complex OCR pipeline with multiple detection layers (slow, buggy)
4. ❌ Page-level vs document-level confusion (logic errors)
5. ❌ Migration conflicts from constant model changes (DB hell)

### What to Do Instead

1. ✅ Single ingestion service (simple pipeline)
2. ✅ Text-only extraction (no assets)
3. ✅ Simple OCR: Tesseract for scanned pages only
4. ✅ Clear page-by-page processing (no confusion)
5. ✅ Freeze schema early, minimal migrations

---

## IMPLEMENTATION CHECKLIST

**Phase 1 (Week 2):**

- [ ] PDF text extraction (native + OCR)
- [ ] Chunking service (1200 chars)
- [ ] Chapter detection (simple regex)
- [ ] Store chunks with metadata
- [ ] Generate embeddings (batch)

**Phase 2 (Week 6):**

- [ ] RSS scraping (2 feeds)
- [ ] CA chunking (same logic)
- [ ] Auto-topic linking (vector similarity)
- [ ] Expiry management

**Quality Checks:**

- [ ] Test: 12-page PDF → 200+ chunks
- [ ] Verify: All chunks have embeddings
- [ ] Validate: chapter_detected = true for most chunks
- [ ] Confirm: No NULL bboxes (text-only, no assets)

---

## API ENDPOINTS

```
POST /api/v1/content/upload
GET /api/v1/content/chunks?document_id=xxx&page=1
GET /api/v1/content/chunks/:id

POST /api/v1/ca/scrape (Admin, manual trigger)
GET /api/v1/ca/chunks?date_from=2025-01-01
```

---

## KEY PRINCIPLE

**Simple text extraction → Quality chunks → Good articles**

Don't over-engineer. Text alone is sufficient for UPSC content.

---

**END OF CONTENT ENGINE IMPLEMENTATION**
