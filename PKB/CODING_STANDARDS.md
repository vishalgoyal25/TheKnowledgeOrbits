# CODING_STANDARDS.md

## TheKnowledgeOrbits — Coding Standards

**PKB File #4 | Version: 1.0 | Date: Feb 2026**

---

## 1. DESIGN PRINCIPLES (MANDATORY)

- **SOLID** — Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion
- **DRY** — No duplicated logic. Extract into services/utils
- **KISS** — Simplest solution that works. No premature optimization
- **YAGNI** — Don't build what's not needed now
- **Fail Fast** — Validate early. Never swallow errors silently

---

## 2. PYTHON STANDARDS

### Naming:

- Variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

### Mandatory in every file:

- Type hints on all functions
- Docstrings on all classes and functions
- Logger initialization: `logger = structlog.get_logger(__name__)`
- No `print()` anywhere

### Function signature pattern:

```python
def function_name(param: str, count: int = 0) -> dict[str, Any]:
    """One-line description of what this does."""
    logger.info("function_called", param=param)
    ...
```

### Error handling pattern:

```python
try:
    result = some_operation()
except ExpectedError as e:
    logger.warning("expected_error", error=str(e))
    raise
except Exception as e:
    logger.error("unexpected_error", error=str(e))
    sentry_sdk.capture_exception(e)
    raise
```

---

## 3. TYPESCRIPT / NEXT.JS STANDARDS

### Naming:

- Variables/functions: `camelCase`
- Components/Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `kebab-case.tsx`

### Mandatory:

- Type/interface on all props and return types
- No `console.log()` — use chalk
- JSDoc on all exported functions/components

### Component pattern:

```typescript
import chalk from 'chalk';

interface Props {
  title: string;
  count: number;
}

export default function ComponentName({ title, count }: Props): JSX.Element {
  /** Brief description */
  return (<div>...</div>);
}
```

---

## 4. DJANGO MODEL STANDARDS

```python
import uuid
from django.db import models

class EngineModelName(models.Model):
    """Description of what this model represents."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier"
    )
    # All fields MUST have help_text

    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp")
    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    class Meta:
        db_table = "enginename_modelname"   # MANDATORY format
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["field_name"]),  # Index all FKs
        ]

    def __str__(self) -> str:
        return self.name
```

### Rules:

- ❌ No auto-increment IDs. UUID only
- ❌ No hardcoded values in models
- ✅ `help_text` on ALL fields
- ✅ `created_at` + `updated_at` on every model
- ✅ `db_table` = `enginename_modelname` format
- ✅ Index on all ForeignKey fields

---

## 5. SECURITY PATTERNS (MANDATORY)

### JWT Authentication:

```python
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated

class ProtectedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
```

### Argon2 Password Hashing:

```python
from django.contrib.auth.hashers import make_password, check_password

hashed = make_password(raw_password)          # Hash
is_valid = check_password(raw_password, hashed)  # Verify
```

### RBAC Decorator:

```python
from engines.authorization.decorators import require_role

@require_role("admin")
def admin_only_view(request):
    ...
```

### Rules:

- ❌ No bcrypt / pbkdf2 — Argon2 only
- ❌ No session-based auth
- ❌ No `alg=none` in JWT
- ❌ No permission checks inside views — middleware only
- ✅ Roles extracted from verified JWT claims only
- ✅ Tokens in HttpOnly cookies

---

## 6. LOGGING PATTERNS

### Python (structlog):

```python
import structlog
logger = structlog.get_logger(__name__)

logger.info("action_name", user_id=user.id, key="value")
logger.warning("warning_event", reason="...")
logger.error("error_event", error=str(e))
```

### Node.js (chalk):

```typescript
import chalk from "chalk";

console.log(chalk.green("[INFO]"), "message");
console.log(chalk.yellow("[WARN]"), "message");
console.log(chalk.red("[ERROR]"), "message");
```

### Log schema (every log must include):

- `timestamp` (auto)
- `level`
- `engine_name`
- `event_name`
- `trace_id` (when available)

---

## 7. API STANDARDS

- Versioned: `/api/v1/...`
- REST conventions: GET (read), POST (create), PUT (update), DELETE (remove)
- Response always JSON
- Errors return: `{ "error": "code", "message": "human readable" }`
- Pagination: cursor-based
- Auth header: `Authorization: Bearer <token>` or HttpOnly cookie

---

## 8. GIT STANDARDS

### Commit format (conventional commits):

```
type(scope): short description

Types: feat, fix, docs, chore, test, refactor
Scope: engine name (content, knowledge, auth...)

Examples:
feat(content): add PDF chunking service
fix(auth): handle token refresh edge case
test(assessment): add quiz generation tests
```

### Rules:

- ❌ No force-push to main/develop
- ✅ Feature branches only: `feature/engine-name-description`
- ✅ commitlint enforced via pre-commit

---

## 9. DATABASE STANDARDS

- Table naming: `enginename_modelname`
- Primary keys: UUID only
- ForeignKeys: always indexed
- No raw SQL unless absolutely necessary — use ORM
- Migrations: one per logical change, never squash in dev

---

## 10. TESTING STANDARDS

- Test naming: `test_{what}_{condition}_{expected}`
- Pattern: AAA (Arrange, Act, Assert)
- Fixtures via factory_boy
- No test touches another engine's DB directly
- Coverage targets: Models 90%, Services 85%, Views 80%
