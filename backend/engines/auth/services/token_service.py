"""
Token Service

Handles token generation for:
- Email verification
- Password reset
"""

import uuid
import secrets


class TokenService:
    """Service for managing authentication tokens."""
    
    @staticmethod
    def generate_verification_token() -> str:
        """
        Generate secure email verification token.
        
        Returns:
            str: UUID token
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_reset_token() -> str:
        """
        Generate secure password reset token.
        
        Returns:
            str: 32-byte hex token
        """
        return secrets.token_urlsafe(32)


# Singleton
_token_service = None

def get_token_service() -> TokenService:
    """Get or create global token service instance."""
    global _token_service
    if _token_service is None:
        _token_service = TokenService()
    return _token_service
    