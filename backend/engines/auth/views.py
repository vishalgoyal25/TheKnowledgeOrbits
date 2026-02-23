import sentry_sdk

"""
Auth Engine Views (PKB-Compliant)

9 Endpoints:
1. POST /register/
2. POST /verify-email/{token}/
3. POST /resend-verification/
4. POST /login/
5. POST /logout/
6. POST /forgot-password/
7. POST /reset-password/{token}/
8. POST /change-password/
9. GET /me/
"""

from typing import Any, cast

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

import structlog
from rest_framework_simplejwt.tokens import RefreshToken

from engines.auth.models import Role, RoleAssignment, User
from engines.auth.serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)
from engines.auth.services.email_service import get_email_service
from engines.auth.services.token_service import get_token_service

logger = structlog.get_logger(__name__)


def get_tokens_for_user(user) -> Any:  # type: ignore
    """Generate JWT tokens."""
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@transaction.atomic
def register(request: Request) -> Response:
    """
    Register new user.

    POST /api/v1/auth/register/
    Body: {
        "email": "user@example.com",
        "password": "SecurePass123",
        "password_confirm": "SecurePass123",
        "full_name": "John Doe" (optional)
    }
    """
    serializer = RegisterSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Create user
        user = User.objects.create_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            full_name=serializer.validated_data.get("full_name", ""),
            is_verified=False,
        )

        # Assign default role (free_user)
        default_role, _ = Role.objects.get_or_create(
            name="free_user", defaults={"description": "Free tier user"}
        )
        RoleAssignment.objects.create(user=user, role=default_role)

        # Generate verification token
        token_service = get_token_service()
        token = token_service.generate_verification_token()

        user.verification_token = token
        user.verification_sent_at = timezone.now()
        user.save()

        # Send email
        email_service = get_email_service()
        email_service.send_verification_email(user, token)

        logger.info("user_registered_successfully", email=user.email, id=str(user.id))

        return Response(
            {
                "message": "Registration successful. Check your email to verify.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error("registration_process_failed", error=str(e), exc_info=True)
        return Response(
            {
                "error": "REGISTRATION_FAILED",
                "message": "An unexpected error occurred during registration.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_email(request: Request, token: str) -> Response:
    """
    Verify user email.

    POST /api/v1/auth/verify-email/{token}/
    """
    try:
        user = User.objects.get(verification_token=token)

        if not user.is_verification_token_valid():
            return Response(
                {"error": "TOKEN_EXPIRED", "message": "Token expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_verified = True
        user.verification_token = None
        user.verification_sent_at = None
        user.save()

        logger.info("email_verified_successfully", email=user.email)

        return Response({"message": "Email verified successfully"})

    except User.DoesNotExist:
        return Response({"error": "INVALID_TOKEN"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([AllowAny])
def resend_verification(request: Request) -> Response:
    """
    Resend verification email.

    POST /api/v1/auth/resend-verification/
    Body: {"email": "user@example.com"}
    """
    email = request.data.get("email", "").lower()

    try:
        user = User.objects.get(email=email)

        if user.is_verified:
            return Response(
                {"error": "ALREADY_VERIFIED"}, status=status.HTTP_400_BAD_REQUEST
            )

        token_service = get_token_service()
        token = token_service.generate_verification_token()

        user.verification_token = token
        user.verification_sent_at = timezone.now()
        user.save()

        email_service = get_email_service()
        email_service.send_verification_email(user, token)

        return Response({"message": "Verification email sent"})

    except User.DoesNotExist:
        # Don't reveal if email exists
        return Response({"message": "If email exists, verification sent"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request: Request) -> Response:
    """
    Login user.

    POST /api/v1/auth/login/
    Body: {
        "email": "user@example.com",
        "password": "SecurePass123"
    }
    """
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"].lower()
    password = serializer.validated_data["password"]

    user = authenticate(request, username=email, password=password)

    if not user:
        return Response(
            {"error": "INVALID_CREDENTIALS"}, status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_verified:
        return Response(
            {"error": "EMAIL_NOT_VERIFIED", "email": user.email},
            status=status.HTTP_403_FORBIDDEN,
        )

    tokens = get_tokens_for_user(user)

    user.last_login = timezone.now()
    user.save()

    logger.info("user_logged_in_successfully", email=user.email)

    return Response(
        {
            "message": "Login successful",
            "user": UserSerializer(user).data,
            "tokens": tokens,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request: Request) -> Response:
    """
    Logout user.

    POST /api/v1/auth/logout/
    """
    user = cast(User, request.user)
    logger.info("user_logged_out", email=user.email)
    return Response({"message": "Logout successful"})


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request: Request) -> Response:
    """
    Request password reset.

    POST /api/v1/auth/forgot-password/
    Body: {"email": "user@example.com"}
    """
    serializer = ForgotPasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data["email"].lower()

    try:
        user = User.objects.get(email=email)

        token_service = get_token_service()
        token = token_service.generate_reset_token()

        user.reset_token = token
        user.reset_sent_at = timezone.now()
        user.save()

        email_service = get_email_service()
        email_service.send_password_reset_email(user, token)

        logger.info("password_reset_link_requested", email=user.email)

    except User.DoesNotExist:
        pass  # Don't reveal if email exists

    return Response({"message": "If email exists, reset link sent"})


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request: Request, token: str) -> Response:
    """
    Reset password with token.

    POST /api/v1/auth/reset-password/{token}/
    Body: {
        "password": "NewPass123",
        "password_confirm": "NewPass123"
    }
    """
    serializer = ResetPasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(reset_token=token)

        if not user.is_reset_token_valid():
            return Response(
                {"error": "TOKEN_EXPIRED"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(serializer.validated_data["password"])
        user.reset_token = None
        user.reset_sent_at = None
        user.save()

        logger.info("password_reset_successful", email=user.email)

        return Response({"message": "Password reset successful"})

    except User.DoesNotExist:
        return Response({"error": "INVALID_TOKEN"}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request: Request) -> Response:
    """
    Change password (when logged in).

    POST /api/v1/auth/change-password/
    Body: {
        "old_password": "OldPass123",
        "new_password": "NewPass123",
        "new_password_confirm": "NewPass123"
    }
    """
    serializer = ChangePasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = cast(User, request.user)

    if not user.check_password(serializer.validated_data["old_password"]):
        return Response(
            {"error": "INVALID_PASSWORD"}, status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(serializer.validated_data["new_password"])
    user.save()

    logger.info("password_changed_successfully", email=user.email)

    return Response({"message": "Password changed successfully"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request: Request) -> Response:
    """
    Get current user profile.

    GET /api/v1/auth/me/
    """
    user = cast(User, request.user)
    serializer = UserSerializer(user)
    return Response(serializer.data)
