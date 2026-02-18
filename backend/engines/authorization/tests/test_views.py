"""
Authorization Engine - View Tests

Tests for role management API endpoints.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from engines.auth.models import User, Role, RoleAssignment


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def admin_user():
    """Create admin user."""
    user = User.objects.create_user(email='admin@test.com', password='pass')
    user.is_verified = True
    user.save()
    admin_role, _ = Role.objects.get_or_create(name='admin')
    RoleAssignment.objects.create(user=user, role=admin_role)
    return user


@pytest.fixture
def student_user():
    """Create student user."""
    user = User.objects.create_user(email='student@test.com', password='pass')
    user.is_verified = True
    user.save()
    role, _ = Role.objects.get_or_create(name='student')
    RoleAssignment.objects.create(user=user, role=role)
    return user


@pytest.fixture
def authenticated_admin(api_client, admin_user):
    """Authenticated admin client."""
    api_client.force_authenticate(user=admin_user)
    return api_client, admin_user


@pytest.mark.django_db
class TestListRolesView:
    """Test list roles endpoint."""
    
    def test_admin_can_list_roles(self, authenticated_admin):
        """Test admin can list all roles."""
        client, user = authenticated_admin
        
        # Create roles
        Role.objects.get_or_create(name='admin')
        Role.objects.get_or_create(name='student')
        
        response = client.get('/api/v1/authorization/roles/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 2
    
    def test_non_admin_denied(self, api_client, student_user):
        """Test non-admin cannot list roles."""
        api_client.force_authenticate(user=student_user)
        
        response = api_client.get('/api/v1/authorization/roles/')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAssignRoleView:
    """Test assign role endpoint."""
    
    def test_admin_can_assign_role(self, authenticated_admin):
        """Test admin can assign role to user."""
        client, admin = authenticated_admin
        
        # Create target user
        target_user = User.objects.create_user(email='target@test.com', password='pass')
        
        # Create role
        role, _ = Role.objects.get_or_create(name='student')
        
        data = {
            'user_id': str(target_user.id),
            'role_name': 'student'
        }
        
        response = client.post('/api/v1/authorization/assign-role/', data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert RoleAssignment.objects.filter(user=target_user, role=role).exists()
    
    def test_cannot_assign_duplicate_role(self, authenticated_admin):
        """Test cannot assign same role twice."""
        client, admin = authenticated_admin
        
        target_user = User.objects.create_user(email='target@test.com', password='pass')
        role, _ = Role.objects.get_or_create(name='student')
        
        # Assign once
        RoleAssignment.objects.create(user=target_user, role=role)
        
        # Try to assign again
        data = {
            'user_id': str(target_user.id),
            'role_name': 'student'
        }
        
        response = client.post('/api/v1/authorization/assign-role/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'ALREADY_ASSIGNED' in response.data['error']


@pytest.mark.django_db
class TestRemoveRoleView:
    """Test remove role endpoint."""
    
    def test_admin_can_remove_role(self, authenticated_admin):
        """Test admin can remove role from user."""
        client, admin = authenticated_admin
        
        target_user = User.objects.create_user(email='target@test.com', password='pass')
        role, _ = Role.objects.get_or_create(name='student')
        RoleAssignment.objects.create(user=target_user, role=role)
        
        data = {
            'user_id': str(target_user.id),
            'role_name': 'student'
        }
        
        response = client.post('/api/v1/authorization/remove-role/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert not RoleAssignment.objects.filter(user=target_user, role=role).exists()
    
    def test_remove_nonexistent_role_fails(self, authenticated_admin):
        """Test removing non-assigned role fails."""
        client, admin = authenticated_admin
        
        target_user = User.objects.create_user(email='target@test.com', password='pass')
        Role.objects.get_or_create(name='student')
        
        data = {
            'user_id': str(target_user.id),
            'role_name': 'student'
        }
        
        response = client.post('/api/v1/authorization/remove-role/', data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestGetUserRolesView:
    """Test get user roles endpoint."""
    
    def test_admin_can_get_user_roles(self, authenticated_admin):
        """Test admin can get user's roles."""
        client, admin = authenticated_admin
        
        target_user = User.objects.create_user(email='target@test.com', password='pass')
        role1, _ = Role.objects.get_or_create(name='student')
        role2, _ = Role.objects.get_or_create(name='content_manager')
        RoleAssignment.objects.create(user=target_user, role=role1)
        RoleAssignment.objects.create(user=target_user, role=role2)
        
        response = client.get(f'/api/v1/authorization/user-roles/{target_user.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['roles']) == 2
        assert 'student' in response.data['roles']
        assert 'content_manager' in response.data['roles']

