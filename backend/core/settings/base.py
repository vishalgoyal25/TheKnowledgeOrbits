"""
Django Base settings for TheKnowledgeOrbits.
"""

import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

import environ
from django.core.exceptions import ImproperlyConfigured

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Environment variables
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-this-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG", default=True)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "cloudinary_storage",  # Must be before staticfiles
    "django.contrib.staticfiles",
    "cloudinary",  # Cloudinary integration
    # Third-party (DRF converts Python objects → JSON.)
    "rest_framework",  # This enables backend → frontend JSON communication.
    "rest_framework_simplejwt",  # This handles JWT authentication (access/refresh tokens).
    "corsheaders",  # This allows frontend to communicate with backend.
    "pgvector",  # This enables vector storage for AI embeddings.
    "background_task",
    # Local engines (will be added as we build them)
    "engines.content",
    "engines.knowledge",
    "engines.article_generation",
    "engines.current_affairs",
    "engines.assessment",
    "engines.auth",
    "engines.userstate",
    "engines.authorization",
    "engines.analytics",
    "engines.support",
    "engines.book_content",
    # Feature 2 engines
    "engines.daily_ca",
    "engines.tags",
    # Feature 6 — Social Interaction Engine
    "engines.social",
]

# Custom User Model
AUTH_USER_MODEL = "authentication.User"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "engines.authorization.middleware.RBACMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

# Database Configuration
# Professional standard: Use a DUMMY database during Render build to avoid timeouts.
# We use an explicit environment variable to ensure the shield stays active during build.
RENDER_BUILD_MODE = (
    os.getenv("RENDER") == "true" and os.getenv("IS_BUILD_PHASE") == "true"
)

if RENDER_BUILD_MODE:
    DATABASES: Dict[str, Any] = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    DATABASES = {
        # ── Local Postgres (default) ──────────────────────────────────────────
        # Used by: python manage.py migrate
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", default=env("NAME", default="TheKnowledgeOrbits")),
            "USER": env("DB_USER", default=env("USER", default="postgres")),
            "PASSWORD": env("DB_PASSWORD", default=env("PASSWORD", default="")),
            "HOST": env("DB_HOST", default=env("HOST", default="localhost")),
            "PORT": env("DB_PORT", default="5433"),
            "OPTIONS": {
                "options": "-c timezone=Asia/Kolkata",
            },
        },
        # ── Supabase Postgres ─────────────────────────────────────────────────
        # Used by: python manage.py migrate --database=supabase
        # Credentials live in .env as SB_DB_* keys — no commenting needed.
        "supabase": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("SB_DB_NAME", default="postgres"),
            "USER": env("SB_DB_USER", default="postgres"),
            "PASSWORD": env("SB_DB_PASSWORD", default=""),
            "HOST": env("SB_DB_HOST", default="localhost"),
            "PORT": env("SB_DB_PORT", default="5432"),
            "OPTIONS": {
                "options": "-c timezone=Asia/Kolkata",
                "sslmode": "require",
            },
        },
    }

# Standard URL Configuration
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:3000")
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"]
)
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS", default=["http://localhost:3000"]
)

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Password Hashing - Use PBKDF2 as primary for free tier memory limits
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# =====================================
# CLOUDINARY CONFIGURATION
# =====================================
CLOUDINARY_STORAGE = {
    "CLOUD_NAME": env("CLOUDINARY_CLOUD_NAME", default=""),
    "API_KEY": env("CLOUDINARY_API_KEY", default=""),
    "API_SECRET": env("CLOUDINARY_API_SECRET", default=""),
}

# Set Cloudinary as the default storage for media files
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_FILTER_BACKENDS": [
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Fix ordering field
    "ORDERING_PARAM": "ordering",
}

# JWT Settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=24),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS Settings
# CORS Settings (Managed by Switchboard above)
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    "DELETE",
    "GET",
    "OPTIONS",
    "PATCH",
    "POST",
    "PUT",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-admin-key",
]

# CSRF Trusted Origins (Managed by Switchboard above)
# CSRF_TRUSTED_ORIGINS is already defined.
# If you need to add more:
# CSRF_TRUSTED_ORIGINS += ["..."]

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Logging Configuration
LOGGING: Dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json_formatter": {
            "format": '{"level": "%(levelname)s", "time": "%(asctime)s", "module": "%(module)s", "message": "%(message)s"}',
        },
        "plain_console": {
            "format": "%(levelname)s %(asctime)s %(module)s %(message)s",
        },
        "key_value": {
            "format": "level=%(levelname)s time=%(asctime)s module=%(module)s msg='%(message)s'",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain_console",
        },
    },
    "loggers": {
        "django_structlog": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "engines": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# Structlog configuration temporarily removed for mypy scan

# Sentry Configuration
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        environment=env("SENTRY_ENVIRONMENT", default="development"),
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        send_default_pii=True,
    )


# GROQ Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "dummy-key-for-build")

# Only raise if not in build/test mode (to avoid crashing Render build)
if not GROQ_API_KEY and not os.getenv("RENDER"):
    raise ImproperlyConfigured("GROQ_API_KEY environment variable is not set")

# ── Additional LLM Providers (optional — add keys to unlock more capacity) ───
# Cerebras: free tier, llama-3.3-70b, api.cerebras.ai/v1
# Comma-separated if multiple keys from same provider.
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


# ==============================================================================
# EMAIL CONFIGURATION
# ==============================================================================

# Default to SMTP, but this will be overridden in dev.py for safety
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "vishal25goyal25@gmail.com")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# SMTP Configuration (Brevo)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp-relay.brevo.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("true", "1", "yes")
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Optional: Brevo API Key if using their official API client instead of SMTP
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")

# Cache Configuration
REDIS_URL = env("REDIS_URL", default=None)

if REDIS_URL:
    try:
        import django_redis  # noqa: F401

        CACHES = {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": REDIS_URL,
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {
                        "ssl_cert_reqs": None  # Required for Upstash rediss:// URIs
                    },
                },
                "KEY_PREFIX": "theknowledgeorbits",
                "TIMEOUT": 300,  # 5 minutes default
            }
        }
    except ImportError:
        # Fallback: django-redis not yet installed (e.g., during Docker build / CI)
        CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "fallback-no-redis-package",
            }
        }
else:
    # No REDIS_URL set — use in-memory cache for local development
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }

# Cache TTL presets
CACHE_TTL = {
    "dashboard": 300,  # 5 minutes
    "weekly_stats": 600,  # 10 minutes
    "monthly_stats": 1800,  # 30 minutes
}

# Admin Security
INTERNAL_ADMIN_KEY = env("INTERNAL_ADMIN_KEY", default="")
