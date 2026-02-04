"""
Development settings for TheKnowledgeOrbits.
"""
from .base import *

DEBUG = True

# Development-specific settings
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Console email backend for development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development logging with rich
LOGGING['handlers']['console']['class'] = 'rich.logging.RichHandler'
