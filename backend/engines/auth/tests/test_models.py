"""
Auth Engine - Model Tests

Tests for User, Role, and RoleAssignment models.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from engines.auth.models import User, Role, RoleAssignment


@pytest.mark.django_db
class TestUserModel:
    """Test User model."""

    def test_create_user_success(self):
        """Test creating a regular user."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        assert user.email == "test@example.com"
        assert user.check_password("TestPass123")
        assert not user.is_verified
        assert user.subscription_tier == "free"
        assert not user.is_staff
        assert not user.is_superuser
        assert user.is_active

    def test_create_user_with_full_name(self):
        """Test creating user with full name."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123", full_name="John Doe"
        )

        assert user.full_name == "John Doe"

    def test_create_user_without_email_fails(self):
        """Test creating user without email raises error."""
        with pytest.raises(ValueError, match="Email is required"):
            User.objects.create_user(email="", password="TestPass123")

    def test_create_superuser_success(self):
        """Test creating a superuser."""
        user = User.objects.create_superuser(
            email="admin@example.com", password="AdminPass123"
        )

        assert user.email == "admin@example.com"
        assert user.is_staff
        assert user.is_superuser
        assert user.is_verified

    def test_user_str_representation(self):
        """Test user string representation."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        assert str(user) == "test@example.com"

    def test_email_normalization(self):
        """Test email is normalized (lowercase)."""
        user = User.objects.create_user(
            email="Test@EXAMPLE.COM", password="TestPass123"
        )

        assert user.email == "test@example.com"

    def test_user_has_uuid_primary_key(self):
        """Test user has UUID as primary key."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        assert isinstance(user.id, type(user.id))  # UUID
        assert len(str(user.id)) == 36  # UUID format

    def test_verification_token_valid_within_24_hours(self):
        """Test verification token is valid within 24 hours."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        user.verification_token = "test-token"
        user.verification_sent_at = timezone.now()
        user.save()

        assert user.is_verification_token_valid()

    def test_verification_token_expired_after_24_hours(self):
        """Test verification token expires after 24 hours."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        user.verification_token = "test-token"
        user.verification_sent_at = timezone.now() - timedelta(hours=25)
        user.save()

        assert not user.is_verification_token_valid()

    def test_verification_token_invalid_without_sent_at(self):
        """Test verification token invalid if sent_at not set."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        user.verification_token = "test-token"
        user.verification_sent_at = None
        user.save()

        assert not user.is_verification_token_valid()

    def test_reset_token_valid_within_1_hour(self):
        """Test reset token is valid within 1 hour."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        user.reset_token = "reset-token"
        user.reset_sent_at = timezone.now()
        user.save()

        assert user.is_reset_token_valid()

    def test_reset_token_expired_after_1_hour(self):
        """Test reset token expires after 1 hour."""
        user = User.objects.create_user(
            email="test@example.com", password="TestPass123"
        )

        user.reset_token = "reset-token"
        user.reset_sent_at = timezone.now() - timedelta(hours=2)
        user.save()

        assert not user.is_reset_token_valid()

    def test_user_ordering(self):
        """Test users ordered by created_at descending."""
        user1 = User.objects.create_user(email="first@example.com", password="pass")
        user2 = User.objects.create_user(email="second@example.com", password="pass")

        users = list(User.objects.all())
        assert users[0] == user2
        assert users[1] == user1

    def test_unique_email_constraint(self):
        """Test email must be unique."""
        User.objects.create_user(email="test@example.com", password="pass")

        with pytest.raises(Exception):  # IntegrityError
            User.objects.create_user(email="test@example.com", password="pass")


@pytest.mark.django_db
class TestRoleModel:
    """Test Role model."""

    def test_create_role_success(self):
        """Test creating a role."""
        role = Role.objects.create(name="admin", description="Administrator role")

        assert role.name == "admin"
        assert role.description == "Administrator role"

    def test_role_str_representation(self):
        """Test role string representation."""
        role = Role.objects.create(name="admin")

        assert str(role) == "Administrator"  # From ROLE_CHOICES

    def test_role_has_uuid_primary_key(self):
        """Test role has UUID as primary key."""
        role = Role.objects.create(name="admin")

        assert len(str(role.id)) == 36

    def test_unique_role_name_constraint(self):
        """Test role name must be unique."""
        Role.objects.create(name="admin")

        with pytest.raises(Exception):  # IntegrityError
            Role.objects.create(name="admin")

    def test_role_ordering(self):
        """Test roles ordered by name."""
        role1 = Role.objects.create(name="student")
        role2 = Role.objects.create(name="admin")

        roles = list(Role.objects.all())
        assert roles[0] == role2  # 'admin' comes first
        assert roles[1] == role1


@pytest.mark.django_db
class TestRoleAssignmentModel:
    """Test RoleAssignment model."""

    def test_create_role_assignment_success(self):
        """Test creating a role assignment."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")

        assignment = RoleAssignment.objects.create(user=user, role=role)

        assert assignment.user == user
        assert assignment.role == role

    def test_role_assignment_str_representation(self):
        """Test role assignment string representation."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")
        assignment = RoleAssignment.objects.create(user=user, role=role)

        assert "test@example.com" in str(assignment)
        assert "admin" in str(assignment)

    def test_role_assignment_has_uuid_primary_key(self):
        """Test role assignment has UUID as primary key."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")
        assignment = RoleAssignment.objects.create(user=user, role=role)

        assert len(str(assignment.id)) == 36

    def test_unique_user_role_constraint(self):
        """Test user can't have same role twice."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")

        RoleAssignment.objects.create(user=user, role=role)

        with pytest.raises(Exception):  # IntegrityError
            RoleAssignment.objects.create(user=user, role=role)

    def test_user_can_have_multiple_roles(self):
        """Test user can have multiple different roles."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role1 = Role.objects.create(name="admin")
        role2 = Role.objects.create(name="student")

        RoleAssignment.objects.create(user=user, role=role1)
        RoleAssignment.objects.create(user=user, role=role2)

        assert user.role_assignments.count() == 2

    def test_cascade_delete_user(self):
        """Test deleting user deletes role assignments."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")
        RoleAssignment.objects.create(user=user, role=role)

        user.delete()

        assert RoleAssignment.objects.count() == 0

    def test_cascade_delete_role(self):
        """Test deleting role deletes role assignments."""
        user = User.objects.create_user(email="test@example.com", password="pass")
        role = Role.objects.create(name="admin")
        RoleAssignment.objects.create(user=user, role=role)

        role.delete()

        assert RoleAssignment.objects.count() == 0
