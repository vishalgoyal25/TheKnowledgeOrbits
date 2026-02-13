# COMPLETE TESTING GUIDE
## Content Engine + Knowledge Engine (Phase 1)

**Purpose:** End-to-end testing from database reset to chunk-topic mapping  
**Date:** February 9, 2026  
**Location:** D:\AI_Projects\TheKnowledgeOrbits\backend  

---

## PART 1: CLEAN SLATE (Database Reset)

### Step 1.1: Stop Server (if running)
```powershell
# Press Ctrl+C in terminal where server is running
```

### Step 1.2: Reset Database (PostgreSQL)
```powershell
# Open PostgreSQL shell
psql -U postgres

# Inside psql:
DROP DATABASE knowledgeorbit;
CREATE DATABASE knowledgeorbit;
\c knowledgeorbit
CREATE EXTENSION IF NOT EXISTS vector;
\q
```

### Step 1.3: Run Fresh Migrations
```powershell
# Navigate to backend
cd D:\AI_Projects\TheKnowledgeOrbits\backend

# Activate virtual environment
.\myenv\Scripts\Activate

# Run migrations
python manage.py migrate

# Verify migrations
python manage.py showmigrations
```

**Expected Output:**
```
content
 [X] 0001_initial
knowledge
 [X] 0001_initial
```

---

## PART 2: CREATE USERS

### Step 2.1: Create Superuser (Admin)
```powershell
python manage.py createsuperuser

# Enter details:
# Username: admin
# Email: admin@knowledgeorbit.com
# Password: admin123
# Password (again): admin123
```

### Step 2.2: Create Test User via Django Shell
```powershell
python manage.py shell
```

**Inside Python shell:**
```python
from django.contrib.auth.models import User

# Create test user
user = User.objects.create_user(
    username='testuser',
    email='test@knowledgeorbit.com',
    password='test123'
)
print(f"Created user: {user.username} (ID: {user.id})")

# Verify users
print(f"\nTotal users: {User.objects.count()}")
for u in User.objects.all():
    print(f"  - {u.username} (ID: {u.id})")

exit()
```

**Expected Output:**
```
Created user: testuser (ID: 2)

Total users: 2
  - admin (ID: 1)
  - testuser (ID: 2)
```

---

## PART 3: GET JWT TOKENS

### Step 3.1: Start Django Server
```powershell
# In new terminal (keep this running)
cd D:\AI_Projects\TheKnowledgeOrbits\backend
.\myenv\Scripts\Activate
python manage.py runserver
```

**Expected Output:**
```
Starting development server at http://127.0.0.1:8000/


Backend health -> http://127.0.0.1:8000/api/v1/health/
```

### Step 3.2: Get Admin Token (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/token/
```

**Headers:**
```
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "username": "admin",
    "password": "admin123"
}
```

**Expected Response (200 OK):**
```json
{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**📋 SAVE THE ACCESS TOKEN** - You'll use this in all future requests.

---

## PART 4: CONTENT ENGINE - DOCUMENT UPLOAD

### Step 4.1: Prepare Test File

**Option A: Create Text File**
```powershell
# Create test file
New-Item -Path "D:\AI_Projects\test_content.txt" -ItemType File

# Add content (open in notepad)
notepad D:\AI_Projects\test_content.txt
```

**Paste this content:**
```
Chapter 1: Introduction to Rights

Rights are fundamental entitlements that every citizen possesses. These rights ensure equality, freedom, and justice for all individuals in a democratic society.

The concept of rights has evolved over centuries, from ancient civilizations to modern constitutional frameworks. In India, fundamental rights are enshrined in Part III of the Constitution.

Chapter 2: Right to Equality

Article 14 of the Indian Constitution guarantees equality before law and equal protection of laws. This means that the State cannot deny any person equality before the law or equal protection of the laws within the territory of India.

Article 15 prohibits discrimination on grounds of religion, race, caste, sex, or place of birth. The State cannot discriminate against any citizen on these grounds in matters of employment, access to shops, public restaurants, hotels, and places of public entertainment.

Article 16 provides for equality of opportunity in matters of public employment. All citizens shall have equal opportunity in matters relating to employment or appointment to any office under the State.

Chapter 3: Right to Freedom

Article 19 grants six fundamental freedoms to all citizens: freedom of speech and expression, freedom to assemble peacefully, freedom to form associations or unions, freedom to move freely throughout India, freedom to reside and settle in any part of India, and freedom to practice any profession or occupation.

Article 21 provides that no person shall be deprived of his life or personal liberty except according to procedure established by law. This is one of the most important articles in the Constitution.

Chapter 4: Constitutional Remedies

Article 32 is the right to constitutional remedies. Dr. B.R. Ambedkar called this the heart and soul of the Constitution. It gives the right to move the Supreme Court for enforcement of fundamental rights.

The Supreme Court can issue writs like habeas corpus, mandamus, prohibition, quo warranto, and certiorari to protect fundamental rights.
```

**Save and close.**

**Option B: Use Existing PDF**
```powershell
# If you have NCERT Polity PDF
# Place it at: D:\AI_Projects\ncert_polity.pdf
```

### Step 4.2: Upload Document (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/content/documents/upload/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

**Body (form-data):**
```
Key: file        | Type: File  | Value: Select D:\AI_Projects\test_content.txt
Key: title       | Type: Text  | Value: Introduction to Fundamental Rights
Key: source_type | Type: Text  | Value: static
```

**Expected Response (201 Created):**
```json
{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "title": "Introduction to Fundamental Rights",
    "file_path": "uploads/documents/test_content_abc123.txt",
    "source_type": "static",
    "subject": null,
    "metadata": {},
    "created_at": "2026-02-09T15:30:00Z"
}
```

**📋 SAVE THE DOCUMENT ID** from response.

### Step 4.3: Check Ingestion Job Status (Postman)

**Wait 5-10 seconds**, then:

**Request:**
```
GET http://127.0.0.1:8000/api/v1/content/jobs/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

**Expected Response (200 OK):**
```json
{
    "count": 1,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "job-uuid-here",
            "document": {
                "id": "document-uuid",
                "title": "Introduction to Fundamental Rights"
            },
            "status": "completed",
            "error_log": null,
            "started_at": "2026-02-09T15:30:01Z",
            "completed_at": "2026-02-09T15:30:05Z",
            "created_at": "2026-02-09T15:30:00Z"
        }
    ]
}
```

**✅ Check:** `status` should be `"completed"`

---

## PART 5: VERIFY CHUNKS & EMBEDDINGS

### Step 5.1: Get Chunks (Postman)

**Request:**
```
GET http://127.0.0.1:8000/api/v1/content/chunks/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

**Expected Response (200 OK):**
```json
{
    "count": 8,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "chunk-uuid-1",
            "chunk_text": "Chapter 1: Introduction to Rights\n\nRights are fundamental...",
            "chunk_index": 0,
            "page_number": null,
            "source_type": "static",
            "document": {
                "id": "document-uuid",
                "title": "Introduction to Fundamental Rights"
            },
            "chapter_name": "Chapter 1",
            "quality_flag": "high",
            "confidence_score": 0.95,
            "created_at": "2026-02-09T15:30:02Z"
        },
        // ... more chunks
    ]
}
```

**✅ Check:** 
- `count` should be 8-10 chunks
- Each chunk has `chunk_text`, `chapter_name`, `quality_flag`

### Step 5.2: Verify Embeddings (PostgreSQL)

```powershell
# Open psql
psql -U postgres -d knowledgeorbit

# Inside psql:
SELECT 
    content_type, 
    COUNT(*) as total,
    AVG(array_length(vector, 1)) as avg_dimension
FROM content_embedding
GROUP BY content_type;

# Expected output:
#  content_type | total | avg_dimension 
# --------------+-------+---------------
#  chunk        |     8 |           384
```

**✅ Check:** 
- `total` matches chunk count
- `avg_dimension` is 384

```sql
-- View sample embeddings
SELECT 
    id,
    content_type,
    content_id,
    array_length(vector, 1) as dimensions,
    created_at
FROM content_embedding
LIMIT 3;

\q
```

---

## PART 6: ADMIN PANEL VERIFICATION

### Step 6.1: Login to Admin

**Open browser:**
```
http://127.0.0.1:8000/admin/
```

**Login:**
- Username: `admin`
- Password: `admin123`

### Step 6.2: Check Content Engine Tables

**Navigate:**
1. Click **Content** (left sidebar)
2. Click **Documents** → Should show 1 document
3. Click **Chunks** → Should show 8-10 chunks
4. Click **Embeddings** → Should show 8-10 embeddings
5. Click **Ingestion jobs** → Should show 1 completed job

**Click on a chunk:**
- Verify `chunk_text` is readable
- Check `chapter_name` is detected
- Check `quality_flag` is set

---

## PART 7: KNOWLEDGE ENGINE - CREATE SYLLABUS

### Step 7.1: Create Program (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/knowledge/programs/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "name": "UPSC Civil Services Examination",
    "description": "India's premier civil service exam for IAS, IPS, IFS officers",
    "exam_pattern": {
        "stages": ["Prelims", "Mains", "Interview"],
        "total_marks": 2025,
        "subjects": ["GS", "Optional", "Essay", "Interview"]
    }
}
```

**Expected Response (201 Created):**
```json
{
    "id": "program-uuid-here",
    "name": "UPSC Civil Services Examination",
    "description": "India's premier civil service exam...",
    "exam_pattern": {
        "stages": ["Prelims", "Mains", "Interview"],
        "total_marks": 2025,
        "subjects": ["GS", "Optional", "Essay", "Interview"]
    },
    "is_active": true,
    "created_at": "2026-02-09T15:40:00Z"
}
```

**📋 SAVE THE PROGRAM ID**

### Step 7.2: Create Subject (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/knowledge/subjects/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "name": "Indian Polity",
    "program": "YOUR_PROGRAM_ID_HERE",
    "description": "Indian Constitution, governance, political system",
    "order_index": 1
}
```

**Expected Response (201 Created):**
```json
{
    "id": "subject-uuid-here",
    "name": "Indian Polity",
    "program": "program-uuid",
    "description": "Indian Constitution, governance...",
    "order_index": 1,
    "is_active": true,
    "created_at": "2026-02-09T15:41:00Z"
}
```

**📋 SAVE THE SUBJECT ID**

### Step 7.3: Create Module (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/knowledge/modules/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "name": "Fundamental Rights",
    "subject": "YOUR_SUBJECT_ID_HERE",
    "description": "Part III of Indian Constitution - Articles 12-35",
    "order_index": 1
}
```

**Expected Response (201 Created):**
```json
{
    "id": "module-uuid-here",
    "name": "Fundamental Rights",
    "subject": "subject-uuid",
    "description": "Part III of Indian Constitution...",
    "order_index": 1,
    "is_active": true,
    "created_at": "2026-02-09T15:42:00Z"
}
```

**📋 SAVE THE MODULE ID**

### Step 7.4: Create Topics (Postman)

**Request 1: Right to Equality**
```
POST http://127.0.0.1:8000/api/v1/knowledge/topics/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "name": "Right to Equality",
    "module": "YOUR_MODULE_ID_HERE",
    "subject": "YOUR_SUBJECT_ID_HERE",
    "description": "Equality before law, equal protection, non-discrimination based on religion, race, caste, sex or place of birth. Articles 14-18 of Indian Constitution.",
    "keywords": [
        "equality",
        "rights",
        "fundamental",
        "constitution",
        "article 14",
        "article 15",
        "discrimination",
        "equal protection",
        "government",
        "citizens"
    ],
    "topic_type": "syllabus",
    "difficulty_level": "medium",
    "order_index": 1
}
```

**Expected Response (201 Created):**
```json
{
    "id": "topic-equality-uuid",
    "name": "Right to Equality",
    "module": "module-uuid",
    "subject": "subject-uuid",
    "parent_topic": null,
    "description": "Equality before law...",
    "keywords": ["equality", "rights", ...],
    "topic_type": "syllabus",
    "difficulty_level": "medium",
    "order_index": 1,
    "is_active": true,
    "created_at": "2026-02-09T15:43:00Z"
}
```

**📋 SAVE THIS TOPIC ID** (you'll use it for mapping)

**Request 2: Right to Freedom**
```
POST http://127.0.0.1:8000/api/v1/knowledge/topics/
```

**Body (JSON):**
```json
{
    "name": "Right to Freedom",
    "module": "YOUR_MODULE_ID_HERE",
    "subject": "YOUR_SUBJECT_ID_HERE",
    "description": "Freedom of speech, expression, assembly, association, movement, residence, and profession. Articles 19-22.",
    "keywords": [
        "freedom",
        "speech",
        "expression",
        "article 19",
        "article 21",
        "assembly",
        "association",
        "movement",
        "liberty"
    ],
    "topic_type": "syllabus",
    "difficulty_level": "medium",
    "order_index": 2
}
```

**📋 SAVE THIS TOPIC ID TOO**

---

## PART 8: AI-ASSISTED CHUNK-TOPIC MAPPING

### Step 8.1: Auto-Suggest Chunks for Topic (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/knowledge/topics/YOUR_EQUALITY_TOPIC_ID/auto-suggest-chunks/?limit=20
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

**Expected Response (200 OK):**
```json
{
    "topic_id": "topic-equality-uuid",
    "topic_name": "Right to Equality",
    "suggestions": [
        {
            "chunk_id": "chunk-uuid-1",
            "chunk_text": "Article 14 of the Indian Constitution guarantees equality...",
            "chunk_index": 2,
            "page_number": null,
            "chapter_name": "Chapter 2",
            "document_id": "document-uuid",
            "document_title": "Introduction to Fundamental Rights",
            "relevance_score": 0.743,
            "quality_flag": "high"
        },
        {
            "chunk_id": "chunk-uuid-2",
            "chunk_text": "Article 15 prohibits discrimination on grounds...",
            "chunk_index": 3,
            "page_number": null,
            "chapter_name": "Chapter 2",
            "document_id": "document-uuid",
            "document_title": "Introduction to Fundamental Rights",
            "relevance_score": 0.698,
            "quality_flag": "high"
        }
        // ... more suggestions
    ],
    "count": 6
}
```

**✅ Check:**
- `count` should be 4-8 (chunks matching "equality" keywords)
- Top `relevance_score` should be > 0.50
- `chunk_text` should contain relevant content

**📋 COPY 3-5 CHUNK IDs** from suggestions for next step

### Step 8.2: Approve Mappings (Postman)

**Request:**
```
POST http://127.0.0.1:8000/api/v1/knowledge/topics/YOUR_EQUALITY_TOPIC_ID/approve-mappings/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
Content-Type: application/json
```

**Body (JSON):**
```json
{
    "chunk_ids": [
        "chunk-uuid-1",
        "chunk-uuid-2",
        "chunk-uuid-3",
        "chunk-uuid-4",
        "chunk-uuid-5"
    ],
    "priority": 1
}
```

**Expected Response (200 OK):**
```json
{
    "topic_id": "topic-equality-uuid",
    "created": 5,
    "skipped": 0,
    "total_mappings": 5
}
```

**✅ Check:** `created` should equal number of chunk_ids submitted

### Step 8.3: Verify Mappings (Postman)

**Request:**
```
GET http://127.0.0.1:8000/api/v1/knowledge/topics/YOUR_EQUALITY_TOPIC_ID/chunks/
```

**Headers:**
```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

**Expected Response (200 OK):**
```json
{
    "count": 5,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": "mapping-uuid-1",
            "chunk": {
                "id": "chunk-uuid-1",
                "chunk_text": "Article 14 of the Indian Constitution...",
                "chapter_name": "Chapter 2",
                "quality_flag": "high"
            },
            "topic": {
                "id": "topic-equality-uuid",
                "name": "Right to Equality"
            },
            "relevance_score": 0.743,
            "priority": 1,
            "auto_mapped": true,
            "created_at": "2026-02-09T15:50:00Z"
        }
        // ... 4 more mappings
    ]
}
```

**✅ Check:**
- `count` is 5
- Each mapping has `relevance_score`, `priority`, `auto_mapped: true`

---

## PART 9: REPEAT FOR "RIGHT TO FREEDOM" TOPIC

**Repeat Steps 8.1-8.3 for the second topic:**

1. Auto-suggest chunks for "Right to Freedom" topic
2. Approve top 3-5 mappings
3. Verify mappings created

**Expected:** 3-5 chunks mapped (from Chapter 3 content about freedoms)

---

## PART 10: ADMIN PANEL - FINAL VERIFICATION

### Step 10.1: Check Knowledge Engine Tables

**Browser:** http://127.0.0.1:8000/admin/

**Navigate:**
1. Click **Knowledge** (left sidebar)
2. Click **Programs** → Should show 1 program (UPSC)
3. Click **Subjects** → Should show 1 subject (Polity)
4. Click **Modules** → Should show 1 module (Fundamental Rights)
5. Click **Topics** → Should show 2 topics (Equality, Freedom)
6. Click **Chunk topic maps** → Should show 8-10 mappings total

### Step 10.2: View Mapping Details

**Click on a ChunkTopicMap:**
- Verify `chunk` shows readable text
- Verify `topic` shows correct topic name
- Check `relevance_score` (should be 0.4-0.8)
- Check `priority` is 1
- Check `auto_mapped` is True

---

## PART 11: DATABASE VERIFICATION (PostgreSQL)

### Step 11.1: Check All Tables

```powershell
psql -U postgres -d knowledgeorbit
```

**Inside psql:**
```sql
-- Content Engine tables
SELECT 'Documents' as table_name, COUNT(*) as rows FROM content_document
UNION ALL
SELECT 'Chunks', COUNT(*) FROM content_chunk
UNION ALL
SELECT 'Embeddings', COUNT(*) FROM content_embedding
UNION ALL
SELECT 'Assets', COUNT(*) FROM content_asset
UNION ALL
SELECT 'Ingestion Jobs', COUNT(*) FROM content_ingestionjob
UNION ALL
-- Knowledge Engine tables
SELECT 'Programs', COUNT(*) FROM knowledge_program
UNION ALL
SELECT 'Subjects', COUNT(*) FROM knowledge_subject
UNION ALL
SELECT 'Modules', COUNT(*) FROM knowledge_module
UNION ALL
SELECT 'Topics', COUNT(*) FROM knowledge_topic
UNION ALL
SELECT 'Chunk-Topic Maps', COUNT(*) FROM knowledge_chunktopicmap;
```

**Expected Output:**
```
   table_name      | rows 
-------------------+------
 Documents         |    1
 Chunks            |    8
 Embeddings        |    8
 Assets            |    0
 Ingestion Jobs    |    1
 Programs          |    1
 Subjects          |    1
 Modules           |    1
 Topics            |    2
 Chunk-Topic Maps  |    8
```

### Step 11.2: Check Mapping Quality

```sql
-- View mappings with details
SELECT 
    t.name as topic,
    c.chunk_index,
    c.chapter_name,
    m.relevance_score,
    m.priority,
    LEFT(c.chunk_text, 80) as chunk_preview
FROM knowledge_chunktopicmap m
JOIN knowledge_topic t ON m.topic_id = t.id
JOIN content_chunk c ON m.chunk_id = c.id
ORDER BY t.name, m.relevance_score DESC;
```

**Expected:** List of mappings showing topics matched to relevant chunks

```sql
\q
```

---

## PART 12: PYTHON SHELL - FINAL TEST

```powershell
python manage.py shell
```

**Inside Python shell:**
```python
from django.db import models
from engines.content.models import Document, Chunk, Embedding
from engines.knowledge.models import Program, Subject, Module, Topic, ChunkTopicMap

# Content Engine Stats
print("=== CONTENT ENGINE ===")
print(f"Documents: {Document.objects.count()}")
print(f"Chunks: {Chunk.objects.count()}")
print(f"Embeddings: {Embedding.objects.count()}")

# Knowledge Engine Stats
print("\n=== KNOWLEDGE ENGINE ===")
print(f"Programs: {Program.objects.count()}")
print(f"Subjects: {Subject.objects.count()}")
print(f"Modules: {Module.objects.count()}")
print(f"Topics: {Topic.objects.count()}")
print(f"Mappings: {ChunkTopicMap.objects.count()}")

# Show topics with mapping counts
print("\n=== TOPICS WITH MAPPINGS ===")
for topic in Topic.objects.all():
    # Use 'chunk_mappings' (defined in ChunkTopicMap.topic related_name)
    mapping_count = topic.chunk_mappings.count()
    
    avg_score = topic.chunk_mappings.aggregate(
        avg=models.Avg('relevance_score')
    )['avg'] or 0
    
    print(f"{topic.name}: {mapping_count} chunks (avg score: {avg_score:.3f})")

# Test chunk retrieval for article generation
print("\n=== TEST ARTICLE GENERATION PREP ===")
topic = Topic.objects.filter(name="Right to Equality").first()

if topic:
    # Use 'topic_mappings' (defined in ChunkTopicMap.chunk related_name)
    # Filter chunks that have a mapping to this topic
    chunks = Chunk.objects.filter(
        topic_mappings__topic=topic
    ).order_by('-topic_mappings__relevance_score')
    
    print(f"\nTopic: {topic.name}")
    print(f"Chunks ready for article: {chunks.count()}")
    
    if chunks.exists():
        print("\nTop chunk preview:")
        print(f"{chunks.first().chunk_text[:200]}...")
else:
    print("Topic 'Right to Equality' not found.")
    
exit()
```

**Expected Output:**
```
=== CONTENT ENGINE ===
Documents: 1
Chunks: 8
Embeddings: 8

=== KNOWLEDGE ENGINE ===
Programs: 1
Subjects: 1
Modules: 1
Topics: 2
Mappings: 8

=== TOPICS WITH MAPPINGS ===
Right to Equality: 5 chunks (avg score: 0.628)
Right to Freedom: 3 chunks (avg score: 0.572)

=== TEST ARTICLE GENERATION PREP ===

Topic: Right to Equality
Chunks ready for article: 5

Top chunk preview:
Article 14 of the Indian Constitution guarantees equality before law and equal protection of laws. This means that the State cannot deny any person equality before the law or equal protection...
```

---

## ✅ SUCCESS CRITERIA CHECKLIST

**Content Engine:**
- [ ] Document uploaded successfully
- [ ] Chunks created (8-10 total)
- [ ] Embeddings generated (384-dim vectors)
- [ ] Ingestion job status = completed
- [ ] Chapter names detected
- [ ] Quality flags assigned

**Knowledge Engine:**
- [ ] Program created (UPSC CSE)
- [ ] Subject created (Indian Polity)
- [ ] Module created (Fundamental Rights)
- [ ] 2 Topics created (Equality, Freedom)
- [ ] Auto-suggest returns relevant chunks
- [ ] Mappings created (8+ total)
- [ ] Relevance scores > 0.40
- [ ] All data visible in admin panel

**Integration:**
- [ ] Chunks linked to topics via ChunkTopicMap
- [ ] Can retrieve chunks by topic_id
- [ ] Ready for article generation
- [ ] All tables populated correctly

---

## TROUBLESHOOTING

### Issue: No chunks suggested
**Solution:** Lower similarity threshold in `mapping_service.py` line 17:
```python
SIMILARITY_THRESHOLD = 0.30  # Lower if needed
```

### Issue: Ingestion job stuck in "processing"
**Solution:** Check error logs:
```sql
SELECT id, status, error_log FROM content_ingestionjob;
```

### Issue: 401 Unauthorized in Postman
**Solution:** Get fresh token (tokens expire after 5 minutes):
```
POST http://127.0.0.1:8000/api/token/
```

### Issue: Embeddings not created
**Solution:** Check Python shell for errors during upload. Verify sentence-transformers installed:
```powershell
pip list | findstr sentence
```

---

## NEXT STEPS

**After completing this guide:**

1. **Upload Real NCERT PDF** (Phase 2)
   - Polity, History, Geography PDFs
   - Verify page number tracking works

2. **Create More Topics** (Phase 2)
   - Add 10+ topics covering syllabus
   - Map chunks to all topics

3. **Article Generation Engine** (Week 5)
   - RAG: Fetch chunks by topic
   - GROQ: Generate article from chunks
   - Store with source attribution

4. **Assessment Engine** (Week 4)
   - Generate MCQs from chunks
   - Quiz taking API
   - Auto-grading

---

## FILE LOCATIONS REFERENCE

**Backend:**
- Project: `D:\AI_Projects\TheKnowledgeOrbits\backend\`
- Virtual Env: `D:\AI_Projects\TheKnowledgeOrbits\backend\myenv\`
- Manage: `D:\AI_Projects\TheKnowledgeOrbits\backend\manage.py`

**Engines:**
- Content: `backend\engines\content\`
- Knowledge: `backend\engines\knowledge\`

**Models:**
- Content: `backend\engines\content\models.py`
- Knowledge: `backend\engines\knowledge\models.py`

**Services:**
- Ingestion: `backend\engines\content\services\ingestion_service.py`
- Chunking: `backend\engines\content\services\chunking_service.py`
- Mapping: `backend\engines\knowledge\services\mapping_service.py`

**Test File:**
- Location: `D:\AI_Projects\test_content.txt`

---

## API ENDPOINTS SUMMARY

**Authentication:**
- `POST /api/token/` - Get JWT tokens
- `POST /api/token/refresh/` - Refresh access token

**Content Engine:**
- `POST /api/v1/content/upload/` - Upload document
- `GET /api/v1/content/documents/` - List documents
- `GET /api/v1/content/chunks/` - List chunks
- `GET /api/v1/content/chunks/:id/` - Get chunk details
- `GET /api/v1/content/ingestion-jobs/` - Check job status

**Knowledge Engine:**
- `GET/POST /api/v1/knowledge/programs/` - Programs CRUD
- `GET/POST /api/v1/knowledge/subjects/` - Subjects CRUD
- `GET/POST /api/v1/knowledge/modules/` - Modules CRUD
- `GET/POST /api/v1/knowledge/topics/` - Topics CRUD
- `POST /api/v1/knowledge/topics/:id/auto-suggest-chunks/` - AI suggestions
- `POST /api/v1/knowledge/topics/:id/approve-mappings/` - Approve mappings
- `GET /api/v1/knowledge/topics/:id/chunks/` - Get mapped chunks
- `GET/POST /api/v1/knowledge/mappings/` - View/Create mappings

---

**STATUS: Ready for Phase 1 Week 3 Testing** ✅

**Last Updated:** February 9, 2026  
**Author:** TheKnowledgeOrbits Development Team
