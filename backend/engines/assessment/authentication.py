"""
engines/assessment/authentication.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Optional JWT Authentication for public assessment endpoints.

DRF evaluates authentication BEFORE permissions.
This means that even with @permission_classes([AllowAny]), a request
carrying an expired or malformed token will get a 401 from the JWT
authenticator before AllowAny ever runs — causing the frontend
apiClient to redirect the user to /auth/login.

OptionalJWTAuthentication fixes this by silently returning None
(= AnonymousUser) instead of raising AuthenticationFailed when a
token is absent, expired, or invalid.

Usage:
    Pure public (read-only, request.user never needed):
        @authentication_classes([])
        @permission_classes([AllowAny])

    Mixed public (user logged in → save with FK; guest → save with None):
        @authentication_classes([OptionalJWTAuthentication])
        @permission_classes([AllowAny])

This class is ONLY used for the Daily Public Quiz flow.
All authenticated endpoints (generate, my-quizzes, my-attempts, etc.)
continue to use the default JWTAuthentication unchanged.
"""

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


class OptionalJWTAuthentication(JWTAuthentication):
    """
    JWTAuthentication that never raises 401.

    - No token in request  → returns None (AnonymousUser). ✓
    - Valid token           → returns (user, token) as normal. ✓
    - Expired / bad token  → returns None instead of raising 401. ✓

    Authenticated users still get full user context (mastery updates,
    attempt tracking). Guest users get user=None — same logic as before,
    but now immune to stale-token 401 redirects.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except AuthenticationFailed:
            # Token present but invalid/expired — treat as anonymous.
            # Never raise; never redirect. AllowAny handles the rest.
            return None
