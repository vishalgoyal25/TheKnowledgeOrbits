"""
Auth Engine - Service Tests

Tests for EmailService and TokenService.
"""

from unittest.mock import MagicMock, patch

import pytest

from engines.auth.models import User
from engines.auth.services.email_service import EmailService, get_email_service
from engines.auth.services.token_service import TokenService, get_token_service


@pytest.mark.django_db
class TestEmailService:
    """Test EmailService."""

    @patch("engines.auth.services.email_service.threading.Thread")
    @patch("engines.auth.services.email_service.send_mail")
    def test_send_verification_email_success(self, mock_send_mail, mock_thread):
        """Test sending verification email."""

        def run_target(target, daemon=False):
            target()
            return MagicMock()

        mock_thread.side_effect = run_target

        user = User.objects.create_user(email="test@example.com", password="pass")
        token = "test-token"

        service = EmailService()
        result = service.send_verification_email(user, token)

        assert result is True
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        assert "Verify Your Email" in kwargs["subject"]
        assert user.email in kwargs["recipient_list"]

    @patch("engines.auth.services.email_service.threading.Thread")
    @patch("engines.auth.services.email_service.send_mail")
    def test_send_password_reset_email_success(self, mock_send_mail, mock_thread):
        """Test sending password reset email."""

        def run_target(target, daemon=False):
            target()
            return MagicMock()

        mock_thread.side_effect = run_target

        user = User.objects.create_user(email="test@example.com", password="pass")
        token = "reset-token"

        service = EmailService()
        result = service.send_password_reset_email(user, token)

        assert result is True
        mock_send_mail.assert_called_once()
        args, kwargs = mock_send_mail.call_args
        assert "Password Reset" in kwargs["subject"]

    @patch("engines.auth.services.email_service.threading.Thread")
    @patch(
        "engines.auth.services.email_service.send_mail",
        side_effect=Exception("SMTP error"),
    )
    def test_send_email_failure(self, mock_send_mail, mock_thread):
        """Test email sending failure."""

        def run_target(target, daemon=False):
            target()
            return MagicMock()

        mock_thread.side_effect = run_target

        user = User.objects.create_user(email="test@example.com", password="pass")

        service = EmailService()
        result = service.send_verification_email(user, "token")

        # Result is True because threading handles it asynchronously without failing the request
        assert result is True

    def test_get_email_service_singleton(self):
        """Test email service returns same instance."""
        service1 = get_email_service()
        service2 = get_email_service()

        assert service1 is service2


class TestTokenService:
    """Test TokenService."""

    def test_generate_verification_token(self):
        """Test verification token generation."""
        service = TokenService()
        token = service.generate_verification_token()

        assert isinstance(token, str)
        assert len(token) == 36  # UUID length
        assert "-" in token  # UUID format

    def test_generate_reset_token(self):
        """Test reset token generation."""
        service = TokenService()
        token = service.generate_reset_token()

        assert isinstance(token, str)
        assert len(token) > 30  # URL-safe token

    def test_tokens_are_unique(self):
        """Test generated tokens are unique."""
        service = TokenService()

        token1 = service.generate_verification_token()
        token2 = service.generate_verification_token()

        assert token1 != token2

    def test_get_token_service_singleton(self):
        """Test token service returns same instance."""
        service1 = get_token_service()
        service2 = get_token_service()

        assert service1 is service2
