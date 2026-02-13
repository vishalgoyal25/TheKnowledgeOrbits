# API_REFERENCE.md
## TheKnowledgeOrbits — API Reference
**PKB File #9 | Version: 1.0 | Date: Feb 2026**

---

## 1. GLOBAL CONVENTIONS

### Versioning
- All endpoints: `/api/v1/...`
- Version bump only on breaking changes

### Authentication
- Header: `Authorization: Bearer <access_token>`
- OR: HttpOnly cookie (preferred, set by login)
- Unauthenticated requests → 401

### Response Format
```json
// Success
{ "data": { ... }, "meta": { ... } }

// List (paginated)
{ "data": [...], "meta": { "cursor": "...", "has_next": true, "count": 50 } }

// Error (always)
{ "error": "ERROR_CODE", "message": "Human-readable explanation" }
```

### Pagination
- Cursor-based (no offset)
- Query params: `?cursor=<token>&limit=20`
- Default limit: 20. Max limit: 100

### Error Codes (Standard Set)
| Code | HTTP Status | Meaning |
|------|-------------|---------|
| UNAUTHORIZED | 401 | Missing or invalid token |
| FORBIDDEN | 403 | Valid token, role lacks permission |
| NOT_FOUND | 404 | Resource does not exist |
| VALIDATION_ERROR | 400 | Invalid input payload |
| CONFLICT | 409 | Duplicate or state conflict |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Unexpected server failure |

---

## 2. AUTH ENGINE

### POST /api/v1/auth/register
- **Auth:** None
- **Body:** `{ "email": string, "password": string, "full_name": string }`
- **Response:** `{ "data": { "user_id": uuid, "email": string, "is_verified": false } }`
- **Errors:** VALIDATION_ERROR, CONFLICT (email exists)

### POST /api/v1/auth/login
- **Auth:** None
- **Body:** `{ "email": string, "password": string }`
- **Response:** `{ "data": { "user_id": uuid, "access_token": string, "refresh_token": string, "expires_in": 300 } }`
- **Side Effect:** Sets HttpOnly cookies (access_token, refresh_token)
- **Errors:** VALIDATION_ERROR, UNAUTHORIZED

### POST /api/v1/auth/verify-email
- **Auth:** None
- **Body:** `{ "token": string }`
- **Response:** `{ "data": { "verified": true } }`
- **Errors:** VALIDATION_ERROR, NOT_FOUND (invalid token)

### POST /api/v1/auth/refresh-token
- **Auth:** None (reads refresh_token from HttpOnly cookie)
- **Body:** `{}` (token from cookie)
- **Response:** `{ "data": { "access_token": string, "expires_in": 300 } }`
- **Errors:** UNAUTHORIZED (expired/invalid refresh token)

---

## 3. CONTENT ENGINE

### POST /api/v1/content/upload
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `multipart/form-data` — `file` (PDF/text), `title`, `source_type` (static|dynamic), `subject_id` (optional)
- **Response:** `{ "data": { "document_id": uuid, "status": "pending" } }`
- **Side Effect:** Fires ingestion_job (async chunking via Celery)
- **Errors:** VALIDATION_ERROR, FORBIDDEN

### GET /api/v1/content/documents
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?subject_id=uuid&source_type=static|dynamic&limit=20&cursor=...`
- **Response:** `{ "data": [{ document }], "meta": { cursor, has_next, count } }`

### GET /api/v1/content/chunks
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?document_id=uuid&topic_id=uuid&source_type=static|dynamic&limit=20&cursor=...`
- **Response:** `{ "data": [{ chunk }], "meta": { cursor, has_next, count } }`

### GET /api/v1/content/assets
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?chunk_id=uuid&asset_type=table|diagram|formula`
- **Response:** `{ "data": [{ asset }] }`

### GET /api/v1/content/ingestion-jobs/:job_id
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Response:** `{ "data": { "job_id": uuid, "status": string, "error_log": string|null } }`

---

## 4. KNOWLEDGE ENGINE

### GET /api/v1/knowledge/programs
- **Auth:** YES
- **RBAC:** all authenticated
- **Response:** `{ "data": [{ program }] }`

### GET /api/v1/knowledge/subjects
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?program_id=uuid`
- **Response:** `{ "data": [{ subject }] }`

### GET /api/v1/knowledge/modules
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?subject_id=uuid`
- **Response:** `{ "data": [{ module }] }`

### GET /api/v1/knowledge/topics
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?module_id=uuid&subject_id=uuid&parent_topic_id=uuid`
- **Response:** `{ "data": [{ topic }] }`

### POST /api/v1/knowledge/programs
- **Auth:** YES
- **RBAC:** admin
- **Body:** `{ "name": string, "description": string, "exam_pattern": object }`
- **Response:** `{ "data": { program } }`

### POST /api/v1/knowledge/subjects
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "name": string, "program_id": uuid }`
- **Response:** `{ "data": { subject } }`

### POST /api/v1/knowledge/modules
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "name": string, "subject_id": uuid, "order_index": int }`
- **Response:** `{ "data": { module } }`

### POST /api/v1/knowledge/topics
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "name": string, "module_id": uuid, "subject_id": uuid, "parent_topic_id": uuid|null, "difficulty_level": string }`
- **Response:** `{ "data": { topic } }`

### POST /api/v1/knowledge/map-chunk
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "chunk_id": uuid, "topic_id": uuid, "relevance_score": float }`
- **Response:** `{ "data": { "chunk_id": uuid, "topic_id": uuid, "mapped": true } }`
- **Errors:** CONFLICT (mapping already exists), NOT_FOUND

### GET /api/v1/knowledge/search
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?q=string&limit=20`
- **Response:** `{ "data": [{ "type": "topic"|"chunk", "id": uuid, "title": string, "score": float }] }`

---

## 5. ASSESSMENT ENGINE

### POST /api/v1/assessment/generate-quiz
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "topic_id": uuid, "question_count": int, "difficulty_level": string, "time_limit": int }`
- **Response:** `{ "data": { "quiz_id": uuid, "status": "generating" } }`
- **Side Effect:** Async (Celery). Quiz populated when generation completes
- **Errors:** VALIDATION_ERROR, NOT_FOUND (topic)

### POST /api/v1/assessment/start-quiz
- **Auth:** YES
- **RBAC:** student, free_user
- **Body:** `{ "quiz_id": uuid }`
- **Response:** `{ "data": { "attempt_id": uuid, "questions": [{ question }], "time_limit": int, "started_at": timestamp } }`
- **Errors:** NOT_FOUND, CONFLICT (attempt already active)

### POST /api/v1/assessment/submit-answer
- **Auth:** YES
- **RBAC:** student, free_user
- **Body:** `{ "attempt_id": uuid, "question_id": uuid, "answer": string }`
- **Response:** `{ "data": { "recorded": true } }`
- **Errors:** NOT_FOUND, CONFLICT (attempt not active)

### POST /api/v1/assessment/submit-quiz
- **Auth:** YES
- **RBAC:** student, free_user
- **Body:** `{ "attempt_id": uuid }`
- **Response:** `{ "data": { "attempt_id": uuid, "score": float, "correct": int, "total": int, "results": [{ question_id, is_correct, explanation }] } }`
- **Side Effect:** Fires event `quiz_completed` → User State Engine updates mastery
- **Errors:** NOT_FOUND, CONFLICT (already submitted)

### GET /api/v1/assessment/attempts
- **Auth:** YES
- **RBAC:** all authenticated (own attempts only)
- **Query Params:** `?quiz_id=uuid&status=pending|active|submitted&limit=20&cursor=...`
- **Response:** `{ "data": [{ attempt }], "meta": { cursor, has_next, count } }`

---

## 6. USER STATE ENGINE

### POST /api/v1/user-state/event
- **Auth:** YES
- **RBAC:** all authenticated (self only)
- **Body:** `{ "event_type": string, "event_data": object }`
- **Response:** `{ "data": { "event_id": uuid, "recorded": true } }`

### GET /api/v1/user-state/progress
- **Auth:** YES
- **RBAC:** own → all authenticated | others → admin
- **Query Params:** `?user_id=uuid` (admin only)
- **Response:** `{ "data": { "total_articles_read": int, "total_quizzes_taken": int, "current_streak": int, "syllabus_coverage_percent": float } }`

### GET /api/v1/user-state/topic-mastery
- **Auth:** YES
- **RBAC:** own → all authenticated | others → admin
- **Query Params:** `?topic_id=uuid&limit=20&cursor=...`
- **Response:** `{ "data": [{ "topic_id": uuid, "mastery_score": float, "questions_attempted": int, "questions_correct": int }] }`

### POST /api/v1/user-state/bookmark
- **Auth:** YES
- **RBAC:** all authenticated (self only)
- **Body:** `{ "content_type": string, "content_id": uuid }`
- **Response:** `{ "data": { "bookmarked": true, "content_type": string, "content_id": uuid } }`
- **Errors:** CONFLICT (already bookmarked)

### GET /api/v1/user-state/bookmarks
- **Auth:** YES
- **RBAC:** all authenticated (own only)
- **Query Params:** `?content_type=article|quiz|chunk&limit=20&cursor=...`
- **Response:** `{ "data": [{ bookmark }], "meta": { cursor, has_next, count } }`

### DELETE /api/v1/user-state/bookmarks/:bookmark_id
- **Auth:** YES
- **RBAC:** all authenticated (own only)
- **Response:** `{ "data": { "removed": true } }`

### PUT /api/v1/user-state/reading-progress
- **Auth:** YES
- **RBAC:** all authenticated (self only)
- **Body:** `{ "article_id": uuid, "percent_read": float, "last_position": int }`
- **Response:** `{ "data": { "updated": true } }`

---

## 7. ANALYTICS ENGINE

### GET /api/v1/analytics/dashboard
- **Auth:** YES
- **RBAC:** own → all authenticated | all → admin
- **Query Params:** `?user_id=uuid&from=date&to=date`
- **Response:** `{ "data": { "daily_aggregates": [{ aggregate }], "insights": [{ insight }] } }`

### GET /api/v1/analytics/performance
- **Auth:** YES
- **RBAC:** own → all authenticated | all → admin
- **Query Params:** `?user_id=uuid&topic_id=uuid`
- **Response:** `{ "data": { "scores_over_time": [...], "weak_topics": [...], "strong_topics": [...] } }`

---

## 8. ARTICLE GENERATION ENGINE (Phase 2)

### POST /api/v1/articles/generate
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "topic_id": uuid, "include_current_affairs": bool, "format": "text"|"infographic"|"timeline" }`
- **Response:** `{ "data": { "article_id": uuid, "status": "generating" } }`
- **Side Effect:** Async (Celery). RAG fetch → GROQ generate → quality check → publish

### GET /api/v1/articles
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?topic_id=uuid&generation_type=ai_generated|human_curated&limit=20&cursor=...`
- **Response:** `{ "data": [{ article }], "meta": { cursor, has_next, count } }`

### GET /api/v1/articles/:id
- **Auth:** YES
- **RBAC:** all authenticated
- **Response:** `{ "data": { article with full content } }`
- **Side Effect:** Frontend fires `article_read` event to User State Engine

### GET /api/v1/articles/:id/sources
- **Auth:** YES
- **RBAC:** all authenticated
- **Response:** `{ "data": [{ "chunk_id": uuid, "relevance_weight": float, "sequence_order": int }] }`

---

## 9. CURRENT AFFAIRS ENGINE (Phase 2)

### GET /api/v1/ca/articles
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?from=date&to=date&status=pending|processed&limit=20&cursor=...`
- **Response:** `{ "data": [{ ca_article }], "meta": { cursor, has_next, count } }`

### GET /api/v1/ca/chunks
- **Auth:** YES
- **RBAC:** all authenticated
- **Query Params:** `?topic_id=uuid&from=date&limit=20&cursor=...`
- **Response:** `{ "data": [{ ca_chunk }], "meta": { cursor, has_next, count } }`

### POST /api/v1/ca/link-topic
- **Auth:** YES
- **RBAC:** admin, content_manager
- **Body:** `{ "ca_chunk_id": uuid, "topic_id": uuid, "relevance_score": float }`
- **Response:** `{ "data": { "linked": true } }`
- **Errors:** CONFLICT (link exists), NOT_FOUND

---

## 10. PHASE 5+ ENDPOINTS (Compact)

| Engine | Method | Endpoint | RBAC |
|--------|--------|----------|------|
| Search | GET | /api/v1/search?q=string&type=topic\|chunk\|article | all auth |
| Notification | GET | /api/v1/notifications | own |
| Notification | PUT | /api/v1/notifications/:id/read | own |
| Commerce | GET | /api/v1/commerce/plans | all auth |
| Commerce | POST | /api/v1/commerce/subscribe | all auth |
| Commerce | GET | /api/v1/commerce/subscriptions | own |
| Gamification | GET | /api/v1/gamification/achievements | own |
| Gamification | GET | /api/v1/gamification/leaderboard | all auth |
| Revision | GET | /api/v1/revision/due-cards | own |
| Revision | POST | /api/v1/revision/review | own |
| Personalization | GET | /api/v1/personalization/learning-path | own |
| Personalization | GET | /api/v1/personalization/recommendations | own |
| AI Tutor | POST | /api/v1/tutor/ask | all auth |
| AI Tutor | GET | /api/v1/tutor/history | own |
| Mock Test | GET | /api/v1/mock-tests | all auth |
| Mock Test | POST | /api/v1/mock-tests/start | all auth |
| Mock Test | GET | /api/v1/mock-tests/attempts/:id/report | own |

---

## 11. RULES

- ❌ No endpoint without Auth specified
- ❌ No endpoint without RBAC role defined
- ✅ Every write operation returns the created/updated resource
- ✅ Every list operation is cursor-paginated
- ✅ Every error returns standard error format
- ✅ Side effects (event emissions) documented per endpoint
- ✅ New endpoints require entry here BEFORE implementation
