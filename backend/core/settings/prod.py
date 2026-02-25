"""
Production settings for TheKnowledgeOrbits.

Activated by: DJANGO_SETTINGS_MODULE=core.settings.prod
Deployment target: Render (web service)
Database: Supabase PostgreSQL with pgvector
"""

import os

from .base import *  # noqa: F401, F403

# ── Security ──────────────────────────────────────────────────────────────────
DEBUG = False

# Render provides the HOST as an env var; Vercel frontend URL also needs to be
# added once the frontend is deployed.
# Format: comma-separated list, e.g. "myapp.onrender.com,www.myapp.com"
ALLOWED_HOSTS = env.list(  # noqa: F405
    "ALLOWED_HOSTS",
    default=["localhost"],
)

# CSRF: must trust both the Render service URL and the Vercel frontend URL
CSRF_TRUSTED_ORIGINS = env.list(  # noqa: F405
    "CSRF_TRUSTED_ORIGINS",
    default=[],
)

# HTTPS security headers
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # required for Render
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/"]

# ── Static Files (WhiteNoise) ─────────────────────────────────────────────────
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

# ── Database SSL (Supabase requires SSL) ──────────────────────────────────────
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    "sslmode": "require",
    "options": "-c timezone=Asia/Kolkata",
}

# ── CORS for Vercel Frontend ──────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=[],
)

# ── Email always SMTP in production ──────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# ── Logging: structured JSON for Render log drain ────────────────────────────
LOGGING["handlers"]["console"]["formatter"] = "json_formatter"  # noqa: F405
LOGGING["root"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",
}

# ── Sentry environment label ──────────────────────────────────────────────────
os.environ.setdefault("SENTRY_ENVIRONMENT", "production")
