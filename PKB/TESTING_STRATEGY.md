# TESTING_STRATEGY.md

## TheKnowledgeOrbits — Testing Strategy

**PKB File #13 | Version: 1.0 | Date: Feb 2026**

---

## 1. PURPOSE

This file defines:

- How every engine is tested (structure, patterns, tooling)
- Coverage targets that are non-negotiable
- What must be tested before an engine is marked stable
- How cross-engine boundaries are validated without breaking isolation
- Phase-specific test requirements and counts

❌ No engine ships without tests passing
❌ No migration runs without model tests passing first
✅ Tests are written BEFORE approval — never after

---

## 2. TEST TOOLING (Locked per TECH_STACK.md)

| Tool         | Phase | Purpose                               |
| ------------ | ----- | ------------------------------------- |
| pytest       | 0     | Test runner — all phases              |
| factory_boy  | 0     | Fixture factories — all phases        |
| faker        | 0     | Fake data generation — all phases     |
| Schemathesis | 1     | API property-based testing — Phase 1+ |
| Locust       | 8     | Load/performance testing — Phase 8+   |

❌ No test tool outside this list without human approval
✅ pytest is the ONLY runner. No unittest discovery, no nose

---

## 3. PER-ENGINE TEST STRUCTURE

Every engine's `tests/` folder follows this exact layout:

```
engines/<engine_name>/tests/
├── __init__.py
├── factories.py          # factory_boy factories for this engine's models
├── test_models.py        # Model-level tests (validation, constraints, methods)
├── test_serializers.py   # Serializer tests (input validation, output shape)
├── test_services.py      # Business logic tests (the core of each engine)
└── test_views.py         # API endpoint tests (HTTP layer, auth, RBAC, responses)
```

### Rules:

- ❌ No test file outside this structure
- ❌ No test imports models from another engine
- ❌ No test queries another engine's DB tables directly
- ✅ Cross-engine calls in tests are mocked at the HTTP boundary
- ✅ Every engine has its own `factories.py` — no shared factory file

---

## 4. COVERAGE TARGETS (Non-Negotiable)

| Layer    | Target | Measured by                                          |
| -------- | ------ | ---------------------------------------------------- |
| Models   | 90%    | All fields, constraints, Meta, **str**, indexes      |
| Services | 85%    | All business logic paths, edge cases, error branches |
| Views    | 80%    | All endpoints, auth states, RBAC roles, error codes  |

### What counts toward coverage:

- Models: field validation, ForeignKey cascades, UNIQUE constraints, default values, help_text presence
- Services: happy path, error path, boundary inputs, side-effect triggers (event emissions)
- Views: 200/201 success, 400 validation, 401 unauthenticated, 403 wrong role, 404 not found, 409 conflict

### What does NOT count:

- ❌ Admin panel (Django admin is not tested)
- ❌ Migration files (migrations are not unit-tested)
- ❌ **init**.py files

---

## 5. NAMING + AAA PATTERN (Mandatory)

### Naming Convention

```
test_{what}_{condition}_{expected}

Examples:
  test_quiz_generation_with_valid_topic_returns_questions
  test_bookmark_duplicate_content_returns_conflict
  test_chunk_upload_without_auth_returns_401
  test_mastery_score_after_perfect_quiz_equals_100
```

### AAA Pattern (every test)

```python
def test_topic_mastery_updates_after_quiz_completion():
    # ARRANGE
    user = UserFactory()
    topic = TopicFactory()
    quiz = QuizFactory(topic=topic)
    attempt = QuizAttemptFactory(quiz=quiz, user=user)

    # ACT
    result = update_mastery(
        user_id=user.id,
        topic_id=topic.id,
        correct=8,
        total=10,
        difficulty_level="medium"
    )

    # ASSERT
    mastery = TopicMastery.objects.get(user=user, topic=topic)
    assert mastery.mastery_score == result["mastery_score"]
    assert mastery.questions_attempted == 10
    assert mastery.questions_correct == 8
```

### Rules:

- ❌ No arrange/act/assert comments required — but structure must follow the pattern
- ❌ No test longer than 40 lines — extract helpers if needed
- ✅ Each test asserts exactly ONE thing (single assertion principle)
- ✅ Descriptive names replace comments — the name IS the documentation

---

## 6. FACTORY PATTERNS

Every engine defines its own factories in `engines/<engine_name>/tests/factories.py`.

### Base Factory Pattern

```python
import factory
import uuid
from factory.django import DjangoModelFactory
from engines.<engine_name>.models import <ModelName>

class <ModelName>Factory(DjangoModelFactory):
    """Factory for <ModelName> test fixtures."""

    class Meta:
        model = <ModelName>

    id = factory.LazyFunction(uuid.uuid4)
    created_at = factory.django.django_utils.now
    # ... all fields with sensible defaults or faker values
```

### Cross-Engine Factory Rule

When Engine A's test needs a user (owned by Auth Engine):

```python
# engines/assessment/tests/factories.py

# ✅ ALLOWED: Import Auth engine's factory for fixture creation only
from engines.auth.tests.factories import UserFactory

class QuizAttemptFactory(DjangoModelFactory):
    class Meta:
        model = QuizAttempt

    user = factory.SubFactory(UserFactory)   # Creates user via Auth factory
    quiz = factory.SubFactory(QuizFactory)
```

### Rules:

- ✅ Factories MAY import other engines' factories (fixture wiring)
- ❌ Test code (test\_\*.py) may NEVER import another engine's models or factories directly
- ❌ No hardcoded UUIDs in factories — always `factory.LazyFunction(uuid.uuid4)`
- ✅ Use `faker` for realistic string data (names, emails, paragraphs)

---

## 7. CROSS-ENGINE BOUNDARY TESTING

Engines are isolated. Tests must respect that boundary. When Engine A calls Engine B's API in production, tests mock that call at the HTTP layer.

### Pattern: Mock External Engine Calls

```python
from unittest.mock import patch

@patch("engines.article_gen.services.content_engine_client.get_chunks")
def test_article_generation_assembles_chunks_correctly(mock_get_chunks):
    # ARRANGE
    mock_get_chunks.return_value = [
        {"id": "uuid-1", "chunk_text": "Polity content...", "source_type": "static"},
        {"id": "uuid-2", "chunk_text": "Recent news...", "source_type": "dynamic"},
    ]

    # ACT
    article = generate_article(topic_id="some-topic-uuid")

    # ASSERT
    mock_get_chunks.assert_called_once_with(topic_id="some-topic-uuid")
    assert article["source_count"] == 2
```

### Rules:

- ✅ Mock at the HTTP client boundary — not at the DB level
- ✅ Mock returns must match the actual API response shape (from API_REFERENCE.md)
- ❌ No test spins up another engine's actual DB or service
- ❌ No test uses another engine's internal ORM models

---

## 8. IDEMPOTENCY TESTS (Mandatory per DATA_FLOW_PATTERNS)

Every operation marked as idempotent in DATA_FLOW_PATTERNS.md MUST have a dedicated test proving it.

### Test Pattern: Idempotent Endpoint

```python
def test_bookmark_duplicate_call_returns_existing_not_error():
    # ARRANGE
    user = UserFactory()
    article = ArticleFactory()

    # ACT — first call
    response_1 = client.post("/api/v1/user-state/bookmark", {
        "content_type": "article",
        "content_id": str(article.id),
    })

    # ACT — duplicate call (identical payload)
    response_2 = client.post("/api/v1/user-state/bookmark", {
        "content_type": "article",
        "content_id": str(article.id),
    })

    # ASSERT — both succeed, no duplicate row
    assert response_1.status_code == 201
    assert response_2.status_code == 201  # or 200, not 409
    assert Bookmark.objects.filter(user=user, content_id=article.id).count() == 1
```

### Test Pattern: Idempotent Event Listener

```python
def test_quiz_completed_listener_processes_duplicate_event_safely():
    # ARRANGE
    user = UserFactory()
    topic = TopicFactory()
    payload = {
        "attempt_id": str(uuid.uuid4()),
        "user_id": str(user.id),
        "topic_id": str(topic.id),
        "score": 80.0,
        "correct": 8,
        "total": 10,
        "difficulty_level": "medium",
    }

    # ACT — process same event twice (simulates at-least-once delivery)
    handle_quiz_completed(payload)
    handle_quiz_completed(payload)  # duplicate

    # ASSERT — mastery updated once, not double-counted
    mastery = TopicMastery.objects.get(user=user, topic=topic)
    assert mastery.questions_attempted == 10  # NOT 20
    assert mastery.questions_correct == 8     # NOT 16
```

### Mandatory idempotency tests for:

| Endpoint / Listener            | Idempotency Key                     |
| ------------------------------ | ----------------------------------- |
| POST /content/upload           | title + source_edition              |
| POST /knowledge/map-chunk      | chunk_id + topic_id                 |
| POST /user-state/bookmark      | user_id + content_type + content_id |
| POST /assessment/submit-quiz   | attempt_id                          |
| POST /ca/link-topic            | ca_chunk_id + topic_id              |
| handle_quiz_completed listener | attempt_id                          |
| handle_article_read listener   | user_id + article_id + read_at      |

---

## 9. EVENT EMISSION TESTS

Every endpoint that emits an event (per EVENT_DRIVEN_ARCHITECTURE.md) must have a test verifying the emission.

### Pattern

```python
from unittest.mock import patch

@patch("engines.assessment.events.emit_quiz_completed")
def test_submit_quiz_fires_quiz_completed_event(mock_emit):
    # ARRANGE
    user = UserFactory()
    attempt = QuizAttemptFactory(user=user, status="active")

    # ACT
    response = client.post("/api/v1/assessment/submit-quiz", {
        "attempt_id": str(attempt.id),
    })

    # ASSERT
    assert response.status_code == 200
    mock_emit.assert_called_once()
    payload = mock_emit.call_args[1]
    assert payload["user_id"] == str(user.id)
    assert payload["attempt_id"] == str(attempt.id)
    assert "score" in payload
```

### Mandatory event emission tests:

| Endpoint                             | Event Emitted        |
| ------------------------------------ | -------------------- |
| POST /assessment/submit-quiz         | quiz_completed       |
| POST /user-state/bookmark            | bookmark_added       |
| Content ingestion job completion     | content_ingested     |
| POST /articles/generate (completion) | article_generated    |
| CA daily scrape completion           | ca_chunks_classified |

---

## 10. AUTH + RBAC TESTS (Every View)

Every view endpoint must be tested across all relevant auth states.

### Mandatory Auth Test Matrix (per endpoint)

```
| State                  | Expected Result |
|------------------------|-----------------|
| No token               | 401             |
| Valid token, wrong role | 403             |
| Valid token, correct role | 200/201       |
| Expired token          | 401             |
```

### Pattern

```python
class TestContentUpload:
    """Tests for POST /api/v1/content/upload."""

    def test_upload_without_token_returns_401(self, client):
        response = client.post("/api/v1/content/upload", ...)
        assert response.status_code == 401

    def test_upload_with_student_role_returns_403(self, client, student_token):
        response = client.post("/api/v1/content/upload", ..., headers={"Authorization": f"Bearer {student_token}"})
        assert response.status_code == 403

    def test_upload_with_admin_role_returns_201(self, client, admin_token):
        response = client.post("/api/v1/content/upload", ..., headers={"Authorization": f"Bearer {admin_token}"})
        assert response.status_code == 201

    def test_upload_with_expired_token_returns_401(self, client, expired_token):
        response = client.post("/api/v1/content/upload", ..., headers={"Authorization": f"Bearer {expired_token}"})
        assert response.status_code == 401
```

---

## 11. PHASE-SPECIFIC TEST COUNTS

These counts are go/no-go gates per EXECUTION_ROADMAP.md.

| Phase      | Engine(s)                           | Minimum Tests | Breakdown                       |
| ---------- | ----------------------------------- | ------------- | ------------------------------- |
| 0          | Setup                               | 1             | Health check endpoint           |
| 1 (Week 2) | Content + Auth                      | 35+           | Content: 20+, Auth: 15+         |
| 1 (Week 3) | Knowledge                           | 15+           | CRUD + mapping + search         |
| 1 (Week 4) | Assessment + User State + Analytics | 30+           | Combined across all three       |
| 1 (Total)  | All Phase 1                         | 65+           | Gate before Phase 2             |
| 2          | Article Gen + Current Affairs       | 25+           | RAG flow + CA pipeline + events |
| 3          | Frontend                            | N/A           | Covered by E2E (Phase 4)        |
| 4          | E2E                                 | 10+           | Full user journey tests         |

---

## 12. INTEGRATION TEST TIERS

```
Tier 1: Unit Tests (per file)
  → Models, Serializers, Service functions in isolation
  → Factory fixtures, no external calls
  → Run: `just test`

Tier 2: Engine Integration Tests (per engine)
  → Full engine flow (upload → chunk → map, or start → answer → submit)
  → Uses test DB, real ORM, mocked external APIs (GROQ, sentence-transformers)
  → Run: `just test --integration`

Tier 3: Cross-Engine Integration Tests
  → Two or more engines working together via mocked HTTP
  → Example: Assessment submits → event fires → User State updates
  → Run: `just test --cross-engine`

Tier 4: E2E Tests (Phase 4+)
  → Full browser flow: register → login → read article → take quiz → see progress
  → Run against staging environment
  → Run: `just test --e2e`
```

### Rules:

- Tier 1 runs on every commit (CI)
- Tier 2 runs on every PR
- Tier 3 runs on every PR (Phase 2+)
- Tier 4 runs before every production deploy (Phase 4+)

---

## 13. CONFTEST STRUCTURE

```python
# backend/conftest.py — Global fixtures only

import pytest
from engines.auth.tests.factories import UserFactory

@pytest.fixture
def api_client(db):
    """Unauthenticated DRF test client."""
    from rest_framework.test import APIClient
    return APIClient()

@pytest.fixture
def admin_user(db):
    """Admin user with valid token."""
    return UserFactory(role="admin")

@pytest.fixture
def student_user(db):
    """Student user with valid token."""
    return UserFactory(role="student")

@pytest.fixture
def admin_token(admin_user):
    """Valid JWT access token for admin user."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(admin_user)
    return str(refresh.access_token)

@pytest.fixture
def student_token(student_user):
    """Valid JWT access token for student user."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(student_user)
    return str(refresh.access_token)
```

### Rules:

- ✅ Only auth-related fixtures in global conftest (every engine needs users)
- ❌ No engine-specific fixtures in global conftest
- ✅ Each engine can have its own `tests/conftest.py` for engine-local fixtures

---

## 14. RULES

- ❌ No engine marked stable without all coverage targets met
- ❌ No migration generated without model tests passing
- ❌ No test accesses another engine's DB directly
- ❌ No test without running before human approval
- ✅ Idempotency tests are mandatory for every idempotent operation
- ✅ Event emission tests are mandatory for every event-emitting endpoint
- ✅ Auth matrix (401/403/200/expired) tested on every protected endpoint
- ✅ factory_boy factories are the ONLY way to create test data
- ✅ Schemathesis runs on all public APIs from Phase 1 onward
- ✅ Locust load tests activate Phase 8 only
