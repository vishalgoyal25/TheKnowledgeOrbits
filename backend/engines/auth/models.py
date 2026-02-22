"""
Auth Engine Models (PKB-Compliant)

Tables (per DATABASE_SCHEMA.md):
- auth_user
- auth_role
- auth_role_assignment

Note: This is the ONLY place where these models exist.
No UserProfile, UserEvent, or UserBookmark here (those belong to other engines).
"""

import uuid
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.utils import timezone
from datetime import timedelta
from typing import Any, Optional, cast


class UserManager(BaseUserManager):  # type: ignore
    """Custom user manager for email-based authentication."""

    def create_user(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        """
        Create, normalize, and save a regular User with the given email and password.

        Args:
            email (str): The unique identifier for the user.
            password (str, optional): The user's password.
            **extra_fields (Any): Arbitrary keyword arguments to be stored on User.

        Returns:
            User: The newly created user instance.
        """
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email).lower()
        user = cast(User, self.model(email=email, **extra_fields))
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, email: str, password: Optional[str] = None, **extra_fields: Any
    ) -> "User":
        """
        Create and save a SuperUser with administrative privileges.

        Args:
            email (str): The unique identifier for the admin.
            password (str, optional): The admin's password.
            **extra_fields (Any): Arbitrary keyword arguments.

        Returns:
            User: The newly created superuser instance.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    User model (PKB-compliant).

    Schema from DATABASE_SCHEMA.md (lines 320-329):
    - id (UUID)
    - email (unique, required)
    - password_hash (Argon2 only)
    - full_name
    - is_verified (email verification status)
    - subscription_tier (free, premium, etc.)
    - created_at, updated_at
    """

    SUBSCRIPTION_CHOICES = [
        ("free", "Free"),
        ("premium", "Premium"),
        ("enterprise", "Enterprise"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    email = models.EmailField(unique=True, help_text="Email address (used for login)")

    # Note: password field comes from AbstractBaseUser
    # We use Argon2 hasher (configured in settings)

    full_name = models.CharField(
        max_length=200, blank=True, help_text="User's full name"
    )

    is_verified = models.BooleanField(
        default=False, help_text="Email verification status"
    )

    subscription_tier = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default="free",
        help_text="Subscription level",
    )

    # Email verification fields
    verification_token = models.CharField(
        max_length=255, blank=True, null=True, help_text="Email verification token"
    )

    verification_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When verification email was sent"
    )

    # Password reset fields
    reset_token = models.CharField(
        max_length=255, blank=True, null=True, help_text="Password reset token"
    )

    reset_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When reset email was sent"
    )

    # Django required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Timestamps (PKB requirement)
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Account creation timestamp"
    )

    updated_at = models.DateTimeField(auto_now=True, help_text="Last update timestamp")

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "auth_user"  # PKB requirement
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["is_verified"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return self.email

    def is_verification_token_valid(self) -> bool:
        """Check if verification token is still valid (24 hours)."""
        if not self.verification_sent_at:
            return False
        expiry = self.verification_sent_at + timedelta(hours=24)
        return timezone.now() < expiry

    def is_reset_token_valid(self) -> bool:
        """Check if password reset token is still valid (1 hour)."""
        if not self.reset_sent_at:
            return False
        expiry = self.reset_sent_at + timedelta(hours=1)
        return timezone.now() < expiry


class Role(models.Model):
    """
    Role model (PKB-compliant).

    Schema from DATABASE_SCHEMA.md (lines 331-336):
    - id (UUID)
    - name (unique) - 'admin', 'content_manager', 'student', 'free_user'
    - description
    """

    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("content_manager", "Content Manager"),
        ("student", "Student"),
        ("free_user", "Free User"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    name = models.CharField(
        max_length=50, unique=True, choices=ROLE_CHOICES, help_text="Role name"
    )

    description = models.TextField(blank=True, help_text="Role description")

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Role creation timestamp"
    )

    class Meta:
        db_table = "auth_role"  # PKB requirement
        ordering = ["name"]

    def __str__(self) -> str:
        return self.get_name_display()


class RoleAssignment(models.Model):
    """
    Role Assignment model (PKB-compliant).

    Schema from DATABASE_SCHEMA.md (lines 338-344):
    - id (UUID)
    - user_id (FK to auth_user)
    - role_id (FK to auth_role)
    - created_at
    - UNIQUE(user_id, role_id)
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="role_assignments",
        help_text="User",
    )

    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="assignments", help_text="Role"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Assignment timestamp"
    )

    class Meta:
        db_table = "auth_role_assignment"  # PKB requirement
        unique_together = [["user", "role"]]
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.role.name}"
