"""
Production settings for TheKnowledgeOrbits.

Activated by: DJANGO_SETTINGS_MODULE=core.settings.prod
Deployment target: Render (web service)
Database: Supabase PostgreSQL with pgvector
"""

import os

from .base import *  # noqa: F401, F403
from .base import env

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

# ── Database SSL/Keepalive (Crucial for Oregon-Mumbai Latency) ──────────────────
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    "sslmode": "require",
    "options": "-c timezone=Asia/Kolkata",
    "connect_timeout": 10,  # Increase timeout for cross-ocean handshake
    "keepalives": 1,
    "keepalives_idle": 30,
    "keepalives_interval": 10,
    "keepalives_count": 5,
}

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

# ── Sentry environment label ─────────────────────────────────────────────────
os.environ.setdefault("SENTRY_ENVIRONMENT", "production")

# ── Ensure FRONTEND_URL never defaults to localhost in production ────────────
FRONTEND_URL = env("FRONTEND_URL", default="https://theknowledgeorbits.com")
