"""
Production settings for TheKnowledgeOrbits.

Activated by: DJANGO_SETTINGS_MODULE=core.settings.prod
Deployment target: Render (web service)
Database: Supabase PostgreSQL with pgvector
"""

import os

from .base import *  # noqa: F401, F403
from .base import DATABASES, LOGGING, MIDDLEWARE, env

# ── Security ─────────────────────────────────────────────────────────────────
DEBUG = False


# Robust helper for lists that may be space or comma separated in Render UI
def get_env_list(var_name, default=None):
    raw_val = env(var_name, default="")
    if not raw_val:
        return default or []
    # Convert spaces/tabs to commas, then split by comma
    cleaned = raw_val.replace("\t", ",").replace(" ", ",")
    return [s.strip() for s in cleaned.split(",") if s.strip()]


ALLOWED_HOSTS = get_env_list(
    "ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "theknowledgeorbits-backend.onrender.com",
        "theknowledgeorbits.com",
        "www.theknowledgeorbits.com",
    ],
)

CSRF_TRUSTED_ORIGINS = get_env_list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://theknowledgeorbits.vercel.app",
        "https://theknowledgeorbits-backend.onrender.com",
        "https://theknowledgeorbits.com",
        "https://www.theknowledgeorbits.com",
    ],
)

# HTTPS security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)  # required for Render
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SECURE_REDIRECT_EXEMPT = [r"^/api/v1/health/", r"^/$"]

# ── Static Files (WhiteNoise) ────────────────────────────────────────────────
# WhiteNoise serves static files directly from Django — no S3/CDN needed on
# free-tier Render. It compresses and caches files automatically.
#
# Base MIDDLEWARE order:
#   [0] CorsMiddleware
#   [1] SecurityMiddleware   ← WhiteNoise must go immediately AFTER this
#   [2] SessionMiddleware ...
MIDDLEWARE.insert(  # noqa: F405
    2,  # Index 2 = right after SecurityMiddleware (index 1)
    "whitenoise.middleware.WhiteNoiseMiddleware",
)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ── Response Compression (Phase 6.3) ─────────────────────────────────────────
# Gzip compresses the huge ~30KB JSON arrays from the database down to ~5KB.
# Must be at index 0 (the FIRST middleware) so it applies to the final response.
MIDDLEWARE.insert(0, "django.middleware.gzip.GZipMiddleware")  # noqa: F405

# ── Unused Middleware Purge (Phase 6.2) ──────────────────────────────────────
# The API uses JWT, so dragging SessionMiddleware around wastes a DB query per
# request. It also returns JSON, making MessageMiddleware (flash msgs) useless.
# By removing these only in prod.py, the local /admin still functions properly.
MIDDLEWARE = [
    m
    for m in MIDDLEWARE  # noqa: F405
    if m
    not in (
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    )
]

# ── Database Performance & Security (Phase 5 & 6) ───────────────────────────
# We guard these with an engine check to prevent crashes during Render build mode
# (which uses a temporary SQLite :memory: database).
if "postgresql" in DATABASES["default"]["ENGINE"]:  # noqa: F405
    # SSL & Connection Tuning
    DATABASES["default"]["OPTIONS"].update(
        {  # noqa: F405
            "sslmode": "require",
            "connect_timeout": 30,  # PgBouncer over cross-ocean link needs more time
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        }
    )

    # Persistent Connections (Phase 5.1)
    # Reuse connections for 10 min (600s). Saves ~200-300ms TLS handshake per request.
    DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

    # Supabase / PgBouncer Tuning
    # Required for transaction mode pooling on port 6543
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True  # noqa: F405

# ── CORS for Vercel Frontend ─────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = get_env_list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "https://theknowledgeorbits.vercel.app",
        "https://theknowledgeorbits-backend.onrender.com",
        "https://theknowledgeorbits.com",
        "https://www.theknowledgeorbits.com",
    ],
)

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.theknowledgeorbits\.com$",
]

CORS_ALLOW_CREDENTIALS = True

# ── Email always SMTP in production ──────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ── Logging: structured JSON for Render log drain ────────────────────────────
LOGGING["handlers"]["console"]["formatter"] = "json_formatter"  # noqa: F405
LOGGING["root"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",
}

# Silence verbose SQL logging in production for performance & security
LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "level": "WARNING",
    "handlers": ["console"],
    "propagate": False,
}

# ── Sentry environment label ─────────────────────────────────────────────────
os.environ.setdefault("SENTRY_ENVIRONMENT", "production")

# ── Ensure FRONTEND_URL never defaults to localhost in production ────────────
FRONTEND_URL = env("FRONTEND_URL", default="https://theknowledgeorbits.com")
