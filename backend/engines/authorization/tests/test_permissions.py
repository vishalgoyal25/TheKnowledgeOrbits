"""
Authorization Engine - Permission Class Tests

Tests for DRF permission classes.
"""

from rest_framework.test import APIRequestFactory

import pytest

from engines.auth.models import Role, RoleAssignment, User
from engines.authorization.permissions import (
    CanGenerateArticle,
    CanGenerateQuiz,
    CanManageContent,
    IsAdmin,
    IsContentManager,
    IsStudent,
)


@pytest.fixture
def factory():
    """API request factory."""
    return APIRequestFactory()


@pytest.fixture
def admin_user():
    """Create admin user."""
    user = User.objects.create_user(email="admin@test.com", password="pass")
    admin_role, _ = Role.objects.get_or_create(name="admin")
    RoleAssignment.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def content_manager_user():
    """Create content manager user."""
    user = User.objects.create_user(email="manager@test.com", password="pass")
    role, _ = Role.objects.get_or_create(name="content_manager")
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.fixture
def student_user():
    """Create student user."""
    user = User.objects.create_user(email="student@test.com", password="pass")
    role, _ = Role.objects.get_or_create(name="student")
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.fixture
def free_user():
    """Create free user."""
    user = User.objects.create_user(email="free@test.com", password="pass")
    role, _ = Role.objects.get_or_create(name="free_user")
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
class TestIsAdminPermission:
    """Test IsAdmin permission class."""

    def test_admin_has_permission(self, factory, admin_user):
        """Test admin user has permission."""
        request = factory.get("/")
        request.user = admin_user

        permission = IsAdmin()
        assert permission.has_permission(request, None)

    def test_non_admin_denied(self, factory, student_user):
        """Test non-admin user denied."""
        request = factory.get("/")
        request.user = student_user

        permission = IsAdmin()
        assert not permission.has_permission(request, None)

    def test_anonymous_denied(self, factory):
        """Test anonymous user denied."""
        from django.contrib.auth.models import AnonymousUser

        request = factory.get("/")
        request.user = AnonymousUser()

        permission = IsAdmin()
        assert not permission.has_permission(request, None)


@pytest.mark.django_db
class TestIsContentManagerPermission:
    """Test IsContentManager permission class."""

    def test_content_manager_has_permission(self, factory, content_manager_user):
        """Test content manager has permission."""
        request = factory.get("/")
        request.user = content_manager_user

        permission = IsContentManager()
        assert permission.has_permission(request, None)

    def test_admin_has_permission(self, factory, admin_user):
        """Test admin also has content manager permission."""
        request = factory.get("/")
        request.user = admin_user

        permission = IsContentManager()
        assert permission.has_permission(request, None)

    def test_student_denied(self, factory, student_user):
        """Test student denied."""
        request = factory.get("/")
        request.user = student_user

        permission = IsContentManager()
        assert not permission.has_permission(request, None)


@pytest.mark.django_db
class TestIsStudentPermission:
    """Test IsStudent permission class."""

    def test_student_has_permission(self, factory, student_user):
        """Test student has permission."""
        request = factory.get("/")
        request.user = student_user

        permission = IsStudent()
        assert permission.has_permission(request, None)

    def test_admin_has_permission(self, factory, admin_user):
        """Test admin has permission."""
        request = factory.get("/")
        request.user = admin_user

        permission = IsStudent()
        assert permission.has_permission(request, None)

    def test_free_user_denied(self, factory, free_user):
        """Test free user denied."""
        request = factory.get("/")
        request.user = free_user

        permission = IsStudent()
        assert not permission.has_permission(request, None)


@pytest.mark.django_db
class TestCanManageContentPermission:
    """Test CanManageContent permission class."""

    def test_read_allowed_for_authenticated(self, factory, student_user):
        """Test read operations allowed for any authenticated user."""
        request = factory.get("/")
        request.user = student_user

        permission = CanManageContent()
        assert permission.has_permission(request, None)

    def test_write_allowed_for_manager(self, factory, content_manager_user):
        """Test write operations allowed for content manager."""
        request = factory.post("/")
        request.user = content_manager_user

        permission = CanManageContent()
        assert permission.has_permission(request, None)

    def test_write_denied_for_student(self, factory, student_user):
        """Test write operations denied for student."""
        request = factory.post("/")
        request.user = student_user

        permission = CanManageContent()
        assert not permission.has_permission(request, None)


@pytest.mark.django_db
class TestCanGenerateQuizPermission:
    """Test CanGenerateQuiz permission class."""

    def test_manager_can_generate(self, factory, content_manager_user):
        """Test content manager can generate quizzes."""
        request = factory.post("/")
        request.user = content_manager_user

        permission = CanGenerateQuiz()
        assert permission.has_permission(request, None)

    def test_student_cannot_generate(self, factory, student_user):
        """Test student cannot generate quizzes."""
        request = factory.post("/")
        request.user = student_user

        permission = CanGenerateQuiz()
        assert not permission.has_permission(request, None)


@pytest.mark.django_db
class TestCanGenerateArticlePermission:
    """Test CanGenerateArticle permission class."""

    def test_manager_can_generate(self, factory, content_manager_user):
        """Test content manager can generate articles."""
        request = factory.post("/")
        request.user = content_manager_user

        permission = CanGenerateArticle()
        assert permission.has_permission(request, None)

    def test_student_cannot_generate(self, factory, student_user):
        """Test student cannot generate articles."""
        request = factory.post("/")
        request.user = student_user

        permission = CanGenerateArticle()
        assert not permission.has_permission(request, None)
