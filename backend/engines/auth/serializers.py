"""
Auth Engine Serializers (PKB-Compliant)
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from engines.auth.models import User, Role


class RegisterSerializer(serializers.Serializer):
    """User registration serializer."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate_email(self, value):
        """Check if email already exists."""
        if User.objects.filter(email=value.lower()).exists():
            raise serializers.ValidationError("Email already registered")
        return value.lower()

    def validate(self, data):
        """Validate passwords match."""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}
            )
        validate_password(data["password"])
        return data


class LoginSerializer(serializers.Serializer):
    """User login serializer."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer."""

    class Meta:
        model = Role
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]


class UserSerializer(serializers.ModelSerializer):
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

    def get_roles(self, obj):
        """Get user's assigned roles."""
        return [
            assignment.role.name
            for assignment in obj.role_assignments.select_related("role").all()
        ]


class ForgotPasswordSerializer(serializers.Serializer):
    """Forgot password serializer."""

    email = serializers.EmailField(required=True)


class ResetPasswordSerializer(serializers.Serializer):
    """Reset password serializer."""

    password = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )
    password_confirm = serializers.CharField(
        required=True, write_only=True, style={"input_type": "password"}
    )

    def validate(self, data):
        """Validate passwords match."""
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match"}
            )
        validate_password(data["password"])
        return data


class ChangePasswordSerializer(serializers.Serializer):
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

    def validate(self, data):
        """Validate passwords match."""
        if data["new_password"] != data["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match"}
            )
        validate_password(data["new_password"])
        return data
