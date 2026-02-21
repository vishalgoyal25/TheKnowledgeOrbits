"""
Production settings for TheKnowledgeOrbits.
"""
from .base import *

DEBUG = False

# Production security settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Email is handled primarily in base.py (defaults to SMTP)

