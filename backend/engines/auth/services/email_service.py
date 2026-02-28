import threading

import sentry_sdk

"""
Email Service

Handles email sending for:
- Email verification
- Password reset
"""

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

import structlog

if TYPE_CHECKING:
    from engines.auth.models import User

logger = structlog.get_logger(__name__)


class EmailService:
    """Service for sending authentication emails."""

    @staticmethod
    def send_verification_email(user: "User", token: str) -> bool:
        """
        Send an email verification link to a newly registered user.
        Uses a background thread to prevent blocking the web request.
        """

        def _send():
            from django.db import connection

            try:
                verification_url = f"{settings.FRONTEND_URL}/auth/verify/{token}"

                context = {
                    "user": user,
                    "verification_url": verification_url,
                    "site_name": "TheKnowledgeOrbits",
                }

                html_message = render_to_string("emails/verification.html", context)
                plain_message = strip_tags(html_message)

                send_mail(
                    subject="Verify Your Email - TheKnowledgeOrbits",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=True,  # Changed to True to avoid unhandled SMTP crash
                )

                logger.info("verification_email_dispatched", user_email=user.email)

            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(
                    "verification_email_failed", error=str(e), user_email=user.email
                )
            finally:
                connection.close()

        from django.db import transaction

        transaction.on_commit(
            lambda: threading.Thread(target=_send, daemon=True).start()
        )
        return True

    @staticmethod
    def send_password_reset_email(user: "User", token: str) -> bool:
        """
        Send a password reset link to a user who requested it.
        Uses a background thread to prevent blocking the web request.
        """

        def _send():
            from django.db import connection

            try:
                reset_url = f"{settings.FRONTEND_URL}/auth/reset-password/{token}"

                context = {
                    "user": user,
                    "reset_url": reset_url,
                    "site_name": "TheKnowledgeOrbits",
                }

                html_message = render_to_string("emails/password_reset.html", context)
                plain_message = strip_tags(html_message)

                send_mail(
                    subject="Password Reset Request - TheKnowledgeOrbits",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=True,
                )

                logger.info("password_reset_email_dispatched", user_email=user.email)

            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.error(
                    "password_reset_email_failed", error=str(e), user_email=user.email
                )
            finally:
                connection.close()

        from django.db import transaction

        transaction.on_commit(
            lambda: threading.Thread(target=_send, daemon=True).start()
        )
        return True


# Singleton
_email_service = None


def get_email_service() -> EmailService:
    """Get or create global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
