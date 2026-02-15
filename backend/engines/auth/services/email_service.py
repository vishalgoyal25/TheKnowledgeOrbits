"""
Email Service

Handles email sending for:
- Email verification
- Password reset
"""

import logging
from typing import Optional
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending authentication emails."""
    
    @staticmethod
    def send_verification_email(user, token: str) -> bool:
        """
        Send email verification email.
        
        Args:
            user: User instance
            token: Verification token
            
        Returns:
            bool: True if sent successfully
        """
        try:
            verification_url = f"{settings.FRONTEND_URL}/auth/verify/{token}"
            
            context = {
                'user': user,
                'verification_url': verification_url,
                'site_name': 'TheKnowledgeOrbits',
            }
            
            html_message = render_to_string(
                'emails/verification.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject='Verify Your Email - TheKnowledgeOrbits',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Verification email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            return False
    
    @staticmethod
    def send_password_reset_email(user, token: str) -> bool:
        """
        Send password reset email.
        
        Args:
            user: User instance
            token: Reset token
            
        Returns:
            bool: True if sent successfully
        """
        try:
            reset_url = f"{settings.FRONTEND_URL}/auth/reset-password/{token}"
            
            context = {
                'user': user,
                'reset_url': reset_url,
                'site_name': 'TheKnowledgeOrbits',
            }
            
            html_message = render_to_string(
                'emails/password_reset.html',
                context
            )
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject='Password Reset Request - TheKnowledgeOrbits',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Password reset email sent to {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send reset email: {str(e)}")
            return False


# Singleton
_email_service = None

def get_email_service() -> EmailService:
    """Get or create global email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
    