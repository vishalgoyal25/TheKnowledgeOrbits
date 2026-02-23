# ARTICLE GENERATION ENGINE - IMPLEMENTATION GUIDE

**Complements:** ENGINE_BASED_EDTECH_COMPLETE_ARCHITECTURE.md
**Purpose:** Theme-based article generation from chunks
**Principle:** Chunks → Context → AI Narrative → Article

---

## CORE CONCEPT

**Articles are GENERATED from chunks, not stored as static content.**

**Theme-based (not topic-based):**

- Topic = Single syllabus node (e.g., "Right to Equality")
- Theme = Broader concept spanning multiple topics (e.g., "Equality in India: Constitutional Framework and Contemporary Challenges")

---

## GENERATION FLOW

```
1. Select chunks (static + CA)
   ↓
2. Assemble context (RAG)
   ↓
3. Generate narrative (GROQ)
   ↓
4. Store article + source map
   ↓
5. Return to user
```

---

## CHUNK SELECTION

### By Topic (Simple)

```python
def select_chunks_by_topic(topic_id: UUID, limit: int = 15) -> List[Chunk]:
    """Fetch chunks linked to topic."""
    chunk_ids = ChunkTopicMap.objects.filter(
        topic_id=topic_id
    ).values_list('chunk_id', flat=True)[:limit]

    return Chunk.objects.filter(id__in=chunk_ids)
```

### By Theme (Advanced - Semantic Search)

```python
def select_chunks_by_theme(theme: str, limit: int = 20) -> List[Chunk]:
    """
    Semantic search across all chunks.

    Example theme: "Gender equality in modern India"
    Fetches chunks about equality, women's rights, recent laws, etc.
    """
    # Generate theme embedding
    theme_embedding = model.encode([theme])[0]

    # Vector similarity search (pgvector)
    results = Embedding.objects.raw('''
        SELECT * FROM embeddings
        WHERE content_type = 'chunk'
        ORDER BY vector <-> %s
        LIMIT %s
    ''', [theme_embedding.tolist(), limit])

    chunk_ids = [e.content_id for e in results]
    return Chunk.objects.filter(id__in=chunk_ids)
```

### Static + CA Integration

```python
def select_mixed_chunks(topic_id: UUID) -> dict:
    """Fetch static + CA chunks for integrated article."""

    # Static chunks (NCERT)
    static_chunks = Chunk.objects.filter(
        chunk_topic_map__topic_id=topic_id,
        source_type='static'
    )[:10]

    # CA chunks (recent news related to topic)
    ca_chunk_ids = CATopicLink.objects.filter(
        topic_id=topic_id,
        ca_chunk__published_at__gte=timezone.now() - timedelta(days=30)
    ).values_list('ca_chunk_id', flat=True)[:5]

    ca_chunks = CAChunk.objects.filter(id__in=ca_chunk_ids)

    return {
        'static': static_chunks,
        'ca': ca_chunks
    }
```

---

## RAG (CONTEXT ASSEMBLY)

### Simple Context

```python
def assemble_context(chunks: List[Chunk]) -> str:
    """Concatenate chunks with source markers."""

    context_parts = []
    for idx, chunk in enumerate(chunks):
        context_parts.append(f"[Source {idx+1}: {chunk.chapter_name}, Page {chunk.page_number}]")
        context_parts.append(chunk.chunk_text)
        context_parts.append("---")

    return "\n".join(context_parts)
```

### Structured Context (Better)

```python
def assemble_structured_context(chunks: dict) -> str:
    """Separate static and CA contexts."""

    context = "=== THEORETICAL FOUNDATION (NCERT) ===\n\n"
    for chunk in chunks['static']:
        context += f"{chunk.chunk_text}\n\n"

    context += "\n=== CURRENT CONTEXT (Recent Developments) ===\n\n"
    for chunk in chunks['ca']:
        context += f"[{chunk.published_at.strftime('%B %Y')}] {chunk.chunk_text}\n\n"

    return context
```

---

## AI GENERATION (GROQ)

### Prompt Template

```python
ARTICLE_PROMPT = """You are an expert UPSC educator writing for IAS aspirants.

Generate a comprehensive article on: {theme}

Source Material:
{context}

Requirements:
1. Structure: Introduction (100 words), Body (600 words), Conclusion (100 words)
2. UPSC Focus: Connect theory to exam patterns
3. Examples: Use current affairs examples where provided
4. Clarity: Clear explanations, no jargon
5. Engagement: Thought-provoking insights

Generate the article now (800-1000 words):
"""
```

### Generation Function

```python
from groq import Groq

def generate_article(theme: str, chunks: List[Chunk]) -> dict:
    """Generate article using GROQ."""

    # Assemble context
    context = assemble_context(chunks)

    # Prepare prompt
    prompt = ARTICLE_PROMPT.format(theme=theme, context=context)

    # Call GROQ
    client = Groq(api_key=settings.GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000
    )

    content = response.choices[0].message.content

    return {
        'title': theme,
        'content': content,
        'word_count': len(content.split()),
        'source_chunks': [str(c.id) for c in chunks]
    }
```

---

## ARTICLE STORAGE

### Create Article + Source Map

```python
def save_article(article_data: dict, chunks: List[Chunk]) -> Article:
    """Store generated article with source attribution."""

    # Create article
    article = Article.objects.create(
        title=article_data['title'],
        slug=slugify(article_data['title']),
        content=article_data['content'],
        word_count=article_data['word_count'],
        read_time=article_data['word_count'] // 200,  # Avg reading speed
        generation_type='ai_generated',
        quality_score=0.0,  # To be reviewed
        published_at=timezone.now()
    )

    # Create source mappings
    for idx, chunk in enumerate(chunks):
        ArticleChunk.objects.create(
            article=article,
            chunk=chunk,
            sequence_order=idx,
            relevance_weight=1.0
        )

    return article
```

---

## THEME VS TOPIC

### Topic-Based (Simple)

**Input:** Topic ID (from syllabus)
**Output:** Article on single topic
**Example:** "Right to Equality" → Article covers only Right to Equality

### Theme-Based (Advanced)

**Input:** Thematic query (text)
**Output:** Article spanning multiple topics
**Example:** "Gender Equality in India" → Covers:

- Right to Equality (Polity)
- Women empowerment schemes (Governance)
- Gender budget (Economy)
- Recent judgments (CA)

**Implementation:**

```python
# Theme-based uses semantic search, not topic mapping
chunks = select_chunks_by_theme("Gender Equality in India", limit=20)
article = generate_article("Gender Equality in India", chunks)
```

---

## STATIC + CA INTEGRATION

### Integrated Article Structure

```
Introduction (Static)
→ Theoretical framework from NCERT

Body Section 1: Constitutional Provisions (Static)
→ Articles, fundamental rights

Body Section 2: Current Implementation (CA)
→ Recent laws, policies, judgments

Body Section 3: Challenges & Analysis (Static + CA)
→ Theory meets practice

Conclusion (Synthesis)
→ UPSC exam perspective
```

### Prompt for Integration

```python
INTEGRATED_PROMPT = """Generate an article connecting theory and current affairs.

THEORETICAL FOUNDATION (NCERT):
{static_context}

RECENT DEVELOPMENTS (News):
{ca_context}

Theme: {theme}

Requirements:
1. Start with theoretical concepts (NCERT)
2. Show current applications (recent examples)
3. Analyze gaps between theory and practice
4. UPSC mains/interview angle

Generate integrated article (1000 words):
"""
```

---

## QUALITY CONTROL

### Post-Generation Checks

```python
def validate_article(article: Article) -> dict:
    """Quality checks before publishing."""

    checks = {
        'word_count': 500 <= article.word_count <= 1500,
        'has_introduction': 'introduction' in article.content.lower()[:200],
        'has_conclusion': 'conclusion' in article.content.lower()[-200:],
        'not_repetitive': len(set(article.content.split())) / len(article.content.split()) > 0.6,
        'proper_structure': article.content.count('\n\n') >= 3
    }

    article.quality_score = sum(checks.values()) / len(checks) * 100
    article.save()

    return checks
```

### Human Review Queue

```python
# Articles with quality_score < 70 go to review queue
if article.quality_score < 70:
    article.review_status = 'pending'
else:
    article.review_status = 'approved'
article.save()
```

---

## API ENDPOINTS

```
POST /api/v1/articles/generate
Body: {
    "topic_id": "uuid",  // Optional
    "theme": "Gender Equality",  // Optional
    "include_ca": true,
    "ca_date_range": 30  // days
}

Response: {
    "article_id": "uuid",
    "title": "...",
    "content": "...",
    "source_chunks": ["uuid1", "uuid2", ...]
}

GET /api/v1/articles/:id
GET /api/v1/articles/:id/sources  // View source chunks
```

---

## LESSONS FROM DISCUSSION

### What We Learned

1. **Chunks are foundation** - Articles generated, not ingested
2. **Theme-based > Topic-based** - More flexible, better articles
3. **Static + CA integration** - Core value proposition
4. **RAG is simple** - Concatenate context + AI generation
5. **Quality control matters** - Human review for published articles

### What NOT to Do

❌ Store articles as static content (generate on demand or cache)
❌ Over-complicate RAG (simple concatenation works)
❌ Skip source attribution (ArticleChunk mapping critical)
❌ Publish without review (quality check first)

---

## IMPLEMENTATION CHECKLIST

**Week 5 (Static Articles):**

- [ ] Topic-based chunk selection
- [ ] Simple context assembly
- [ ] GROQ integration
- [ ] Article storage + source map
- [ ] Quality validation

**Week 6 (CA Integration):**

- [ ] CA chunk fetching (date-based)
- [ ] Static + CA context merging
- [ ] Integrated prompt template
- [ ] Test: Generate 10 integrated articles

**Week 7 (Theme-based):**

- [ ] Semantic search implementation
- [ ] Theme-based chunk selection
- [ ] Test: Generate theme articles
- [ ] Compare with topic-based quality

---

## PERFORMANCE NOTES

**GROQ Generation:**

- Average: 15-30 seconds per article
- Cost: $0 (free tier: 14,400 req/day)
- Quality: Excellent for UPSC content

**Caching Strategy:**

- Cache generated articles (1 week TTL)
- Regenerate if source chunks updated
- Pre-generate popular topics (cron job)

---

## KEY PRINCIPLE

**Chunks are raw material. Articles are crafted products.**

Generate articles dynamically, don't store them statically (except for caching).

---

**END OF ARTICLE GENERATION IMPLEMENTATION**
