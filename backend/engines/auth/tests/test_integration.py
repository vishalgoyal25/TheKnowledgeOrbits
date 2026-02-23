"""
Auth Engine - Integration Tests

End-to-end user flow tests.
"""

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.auth.models import User


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.mark.django_db
class TestAuthenticationFlow:
    """Test complete authentication flow."""

    def test_complete_registration_verification_login_flow(self, api_client):
        """Test: Register → Verify → Login."""
        # Step 1: Register
        register_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "full_name": "Test User",
        }

        response = api_client.post("/api/v1/auth/register/", register_data)
        assert response.status_code == status.HTTP_201_CREATED

        # Step 2: Get verification token (simulate)
        user = User.objects.get(email="newuser@example.com")
        assert not user.is_verified
        token = user.verification_token

        # Step 3: Verify email
        response = api_client.post(f"/api/v1/auth/verify-email/{token}/")
        assert response.status_code == status.HTTP_200_OK

        user.refresh_from_db()
        assert user.is_verified

        # Step 4: Login
        login_data = {"email": "newuser@example.com", "password": "SecurePass123!"}

        response = api_client.post("/api/v1/auth/login/", login_data)
        assert response.status_code == status.HTTP_200_OK
        assert "tokens" in response.data

        # Step 5: Access protected endpoint
        access_token = response.data["tokens"]["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "newuser@example.com"

    def test_password_reset_flow(self, api_client):
        """Test: Forgot Password → Reset → Login with new password."""
        # Step 1: Create verified user
        user = User.objects.create_user(
            email="test@example.com", password="OldPass123!"
        )
        user.is_verified = True
        user.save()

        # Step 2: Request password reset
        response = api_client.post(
            "/api/v1/auth/forgot-password/", {"email": "test@example.com"}
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 3: Get reset token
        user.refresh_from_db()
        token = user.reset_token
        assert token is not None

        # Step 4: Reset password
        response = api_client.post(
            f"/api/v1/auth/reset-password/{token}/",
            {"password": "NewPass123!", "password_confirm": "NewPass123!"},
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 5: Login with new password
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "NewPass123!"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert "tokens" in response.data

    def test_role_assignment_on_registration(self, api_client):
        """Test user gets default role on registration."""
        # Register user
        response = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED

        # Check default role assigned
        user = User.objects.get(email="test@example.com")
        assert user.role_assignments.filter(role__name="free_user").exists()

        # Verify in response
        assert "free_user" in response.data["user"]["roles"]


@pytest.mark.django_db
class TestAuthenticationEdgeCases:
    """Test edge cases and error scenarios."""

    def test_cannot_login_before_email_verification(self, api_client):
        """Test login blocked until email verified."""
        # Register
        api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "test@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
        )

        # Try to login
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": "test@example.com", "password": "SecurePass123!"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "EMAIL_NOT_VERIFIED"

    def test_expired_tokens_rejected(self, api_client):
        """Test expired verification token is rejected."""
        from datetime import timedelta

        from django.utils import timezone

        # Create user with expired token
        user = User.objects.create_user(email="test@example.com", password="pass")
        user.verification_token = "expired-token"
        user.verification_sent_at = timezone.now() - timedelta(hours=25)
        user.save()

        # Try to verify
        response = api_client.post("/api/v1/auth/verify-email/expired-token/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "TOKEN_EXPIRED"

    def test_resend_verification_for_unverified_user(self, api_client):
        """Test resending verification email."""
        # Create unverified user
        user = User.objects.create_user(
            email="test@example.com", password="pass", is_verified=False
        )
        old_token = "old-token"
        user.verification_token = old_token
        user.save()

        # Resend verification
        response = api_client.post(
            "/api/v1/auth/resend-verification/", {"email": "test@example.com"}
        )

        assert response.status_code == status.HTTP_200_OK

        # Check new token generated
        user.refresh_from_db()
        assert user.verification_token != old_token
