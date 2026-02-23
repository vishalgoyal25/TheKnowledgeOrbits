"""
Development settings for TheKnowledgeOrbits.
"""

import os

from .base import *  # noqa: F403, F401

DEBUG = True

# Development-specific settings
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]  # nosec: B104 (dev only)

# Email backend for development
# Default to console so we don't spam real emails
# Set USE_REAL_EMAIL_IN_DEV=True in .env to test actual email delivery
if os.getenv("USE_REAL_EMAIL_IN_DEV", "False") == "True":  # noqa: F405  # type: ignore
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Development logging with rich
LOGGING["handlers"]["console"] = {  # noqa: F405
    "level": "DEBUG",
    "class": "rich.logging.RichHandler",
    "rich_tracebacks": True,
}
LOGGING["root"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "INFO",
}
