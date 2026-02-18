"""
Authorization Engine - Service Tests

Tests for PermissionService.
"""

import pytest
from engines.auth.models import User, Role, RoleAssignment
from engines.authorization.services.permission_service import PermissionService


@pytest.fixture
def admin_user():
    """Create admin user."""
    user = User.objects.create_user(email='admin@test.com', password='pass')
    admin_role, _ = Role.objects.get_or_create(name='admin')
    RoleAssignment.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def content_manager_user():
    """Create content manager user."""
    user = User.objects.create_user(email='manager@test.com', password='pass')
    role, _ = Role.objects.get_or_create(name='content_manager')
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.fixture
def student_user():
    """Create student user."""
    user = User.objects.create_user(email='student@test.com', password='pass')
    role, _ = Role.objects.get_or_create(name='student')
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.mark.django_db
class TestPermissionService:
    """Test PermissionService."""
    
    def test_has_role(self, admin_user):
        """Test has_role method."""
        service = PermissionService()
        
        assert service.has_role(admin_user, 'admin')
        assert not service.has_role(admin_user, 'student')
    
    def test_has_any_role(self, content_manager_user):
        """Test has_any_role method."""
        service = PermissionService()
        
        assert service.has_any_role(content_manager_user, ['admin', 'content_manager'])
        assert not service.has_any_role(content_manager_user, ['admin', 'student'])
    
    def test_get_user_roles(self, admin_user):
        """Test get_user_roles method."""
        service = PermissionService()
        
        roles = service.get_user_roles(admin_user)
        
        assert 'admin' in roles
        assert len(roles) == 1
    
    def test_can_manage_content(self, content_manager_user, student_user):
        """Test can_manage_content method."""
        service = PermissionService()
        
        assert service.can_manage_content(content_manager_user)
        assert not service.can_manage_content(student_user)
    
    def test_can_generate_quiz(self, admin_user, student_user):
        """Test can_generate_quiz method."""
        service = PermissionService()
        
        assert service.can_generate_quiz(admin_user)
        assert not service.can_generate_quiz(student_user)
    
    def test_can_manage_roles(self, admin_user, content_manager_user):
        """Test can_manage_roles method."""
        service = PermissionService()
        
        assert service.can_manage_roles(admin_user)
        assert not service.can_manage_roles(content_manager_user)

