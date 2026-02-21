"""
Development settings for TheKnowledgeOrbits.
"""
from .base import *

DEBUG = True

# Development-specific settings
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# Email backend for development
# Default to console so we don't spam real emails
# Set USE_REAL_EMAIL_IN_DEV=True in .env to test actual email delivery
if os.getenv('USE_REAL_EMAIL_IN_DEV', 'False') == 'True':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Development logging with rich
LOGGING['handlers']['console']['class'] = 'rich.logging.RichHandler'
