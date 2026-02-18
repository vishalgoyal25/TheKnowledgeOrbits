"""
Authorization Engine - Integration Tests

End-to-end RBAC workflows.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from engines.auth.models import User, Role, RoleAssignment


@pytest.fixture
def admin_client():
    """Authenticated admin client."""
    user = User.objects.create_user(email='admin@test.com', password='pass')
    user.is_verified = True
    user.save()
    admin_role, _ = Role.objects.get_or_create(name='admin')
    RoleAssignment.objects.create(user=user, role=admin_role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.mark.django_db
class TestRoleManagementFlow:
    """Test complete role management workflow."""
    
    def test_create_user_assign_roles_verify_permissions(self, admin_client):
        """Test: Create user → Assign roles → Verify permissions."""
        client, admin = admin_client
        
        # Step 1: Create new user
        new_user = User.objects.create_user(
            email='newuser@test.com',
            password='pass'
        )
        
        # Step 2: Assign student role
        Role.objects.get_or_create(name='student')
        response = client.post('/api/v1/authorization/assign-role/', {
            'user_id': str(new_user.id),
            'role_name': 'student'
        })
        assert response.status_code == status.HTTP_201_CREATED
        
        # Step 3: Verify roles
        response = client.get(f'/api/v1/authorization/user-roles/{new_user.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert 'student' in response.data['roles']
        
        # Step 4: Promote to content manager
        Role.objects.get_or_create(name='content_manager')
        response = client.post('/api/v1/authorization/assign-role/', {
            'user_id': str(new_user.id),
            'role_name': 'content_manager'
        })
        assert response.status_code == status.HTTP_201_CREATED
        
        # Step 5: Verify multiple roles
        response = client.get(f'/api/v1/authorization/user-roles/{new_user.id}/')
        assert len(response.data['roles']) == 2
        
        # Step 6: Remove student role
        response = client.post('/api/v1/authorization/remove-role/', {
            'user_id': str(new_user.id),
            'role_name': 'student'
        })
        assert response.status_code == status.HTTP_200_OK
        
        # Step 7: Verify role removed
        response = client.get(f'/api/v1/authorization/user-roles/{new_user.id}/')
        assert len(response.data['roles']) == 1
        assert 'content_manager' in response.data['roles']


@pytest.mark.django_db
class TestRoleBasedAccessControl:
    """Test RBAC enforcement in protected endpoints."""
    
    def test_admin_access_protected_endpoint(self, admin_client):
        """Test admin can access admin-only endpoints."""
        client, admin = admin_client
        
        # Admin can list roles
        response = client.get('/api/v1/authorization/roles/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_non_admin_denied_protected_endpoint(self):
        """Test non-admin denied access to admin endpoints."""
        # Create student user
        user = User.objects.create_user(email='student@test.com', password='pass')
        role, _ = Role.objects.get_or_create(name='student')
        RoleAssignment.objects.create(user=user, role=role)
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        # Student cannot list roles
        response = client.get('/api/v1/authorization/roles/')
        assert response.status_code == status.HTTP_403_FORBIDDEN

