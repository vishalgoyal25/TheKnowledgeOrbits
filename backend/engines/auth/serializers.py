"""
Auth Engine Serializers (PKB-Compliant)
"""

from typing import Any, Dict, List

from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

import structlog

from engines.auth.models import Role, User

logger = structlog.get_logger(__name__)


class RegisterSerializer(serializers.Serializer):  # type: ignore
    """User registration serializer."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_email(self, value: str) -> str:
        """Ensure email is unique and normalized."""
        if User.objects.filter(email=value.lower()).exists():
            logger.warning("registration_email_already_exists", email=value.lower())
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify password matching and complexity."""
        if data["password"] != data["password_confirm"]:
            logger.warning("password_mismatch_validation_error")
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}  # nosec: B105
            )
        validate_password(data["password"])
        return data


class LoginSerializer(serializers.Serializer):  # type: ignore
    """User login serializer."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )


class RoleSerializer(serializers.ModelSerializer):  # type: ignore
    """Role serializer."""

    class Meta:
        model = Role
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):  # type: ignore
    """User serializer."""

    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "is_verified",
            "subscription_tier",
            "created_at",
            "last_login",
            "roles",
        ]
        read_only_fields = ["id", "email", "is_verified", "created_at", "last_login"]

    def get_roles(self, obj: User) -> List[str]:
        """Retrieve established roles for the user instance."""
        return [
            assignment.role.name
            for assignment in obj.role_assignments.select_related("role").all()
        ]


class ForgotPasswordSerializer(serializers.Serializer):  # type: ignore
    """Forgot password serializer."""

    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):  # type: ignore
    """Reset password serializer."""

    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, data) -> Any:  # type: ignore
        """Validate passwords match."""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}  # nosec: B105
            )
        validate_password(data["password"])
        return data


class ChangePasswordSerializer(serializers.Serializer):  # type: ignore
    """Change password serializer (when logged in)."""

    old_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    new_password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Verify complexity and matching for logged-in password change."""
        if data["new_password"] != data["new_password_confirm"]:
            logger.warning("change_password_mismatch")
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match"}  # nosec: B105
            )
        validate_password(data["new_password"])
        return data
