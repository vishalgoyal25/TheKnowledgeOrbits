"""
Authorization Engine Admin

Note: This engine uses auth_role and auth_role_assignment (read-only).
Admin interfaces are registered in Auth engine.
"""

from django.contrib import admin

# This engine doesn't register its own models in admin
# It uses models from Auth engine (read-only access)

# Optional: Custom admin actions for role management
# Can be added here if needed
