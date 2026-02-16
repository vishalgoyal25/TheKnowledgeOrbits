"""
Auth Engine - View Tests

Tests for all 9 API endpoints.
"""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from engines.auth.models import User, Role, RoleAssignment


@pytest.fixture
def api_client():
    """API client fixture."""
    return APIClient()


@pytest.fixture
def create_user():
    """Fixture to create a user."""
    def _create_user(email='test@example.com', password='TestPass123', is_verified=True):
        user = User.objects.create_user(email=email, password=password)
        user.is_verified = is_verified
        user.save()
        return user
    return _create_user


@pytest.fixture
def authenticated_client(api_client, create_user):
    """Authenticated API client fixture."""
    user = create_user()
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestRegisterView:
    """Test user registration endpoint."""
    
    def test_register_success(self, api_client):
        """Test successful user registration."""
        data = {
            'email': 'newuser@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'full_name': 'New User'
        }
        
        response = api_client.post('/api/v1/auth/register/', data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['message'] == 'Registration successful. Check your email to verify.'
        assert User.objects.filter(email='newuser@example.com').exists()
        
        user = User.objects.get(email='newuser@example.com')
        assert not user.is_verified
        assert user.full_name == 'New User'
        assert user.role_assignments.filter(role__name='free_user').exists()
    
    def test_register_password_mismatch(self, api_client):
        """Test registration fails with mismatched passwords."""
        data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass123!'
        }
        
        response = api_client.post('/api/v1/auth/register/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'password_confirm' in response.data
    
    def test_register_duplicate_email(self, api_client, create_user):
        """Test registration fails with existing email."""
        create_user(email='existing@example.com')
        
        data = {
            'email': 'existing@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        
        response = api_client.post('/api/v1/auth/register/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'email' in response.data


@pytest.mark.django_db
class TestVerifyEmailView:
    """Test email verification endpoint."""
    
    def test_verify_email_success(self, api_client, create_user):
        """Test successful email verification."""
        user = create_user(is_verified=False)
        user.verification_token = 'test-token-123'
        user.verification_sent_at = timezone.now()
        user.save()
        
        response = api_client.post(f'/api/v1/auth/verify-email/test-token-123/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Email verified successfully'
        
        user.refresh_from_db()
        assert user.is_verified
        assert user.verification_token is None
    
    def test_verify_email_invalid_token(self, api_client):
        """Test verification fails with invalid token."""
        response = api_client.post('/api/v1/auth/verify-email/invalid-token/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error'] == 'INVALID_TOKEN'
    
    def test_verify_email_expired_token(self, api_client, create_user):
        """Test verification fails with expired token."""
        from datetime import timedelta
        
        user = create_user(is_verified=False)
        user.verification_token = 'expired-token'
        user.verification_sent_at = timezone.now() - timedelta(hours=25)
        user.save()
        
        response = api_client.post('/api/v1/auth/verify-email/expired-token/')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'TOKEN_EXPIRED'


@pytest.mark.django_db
class TestLoginView:
    """Test user login endpoint."""
    
    def test_login_success(self, api_client, create_user):
        """Test successful login."""
        create_user(email='test@example.com', password='TestPass123')
        
        data = {
            'email': 'test@example.com',
            'password': 'TestPass123'
        }
        
        response = api_client.post('/api/v1/auth/login/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'tokens' in response.data
        assert 'access' in response.data['tokens']
        assert 'refresh' in response.data['tokens']
        assert 'user' in response.data
    
    def test_login_invalid_credentials(self, api_client, create_user):
        """Test login fails with wrong password."""
        create_user(email='test@example.com', password='TestPass123')
        
        data = {
            'email': 'test@example.com',
            'password': 'WrongPassword'
        }
        
        response = api_client.post('/api/v1/auth/login/', data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.data['error'] == 'INVALID_CREDENTIALS'
    
    def test_login_unverified_email(self, api_client, create_user):
        """Test login fails if email not verified."""
        create_user(email='test@example.com', password='TestPass123', is_verified=False)
        
        data = {
            'email': 'test@example.com',
            'password': 'TestPass123'
        }
        
        response = api_client.post('/api/v1/auth/login/', data)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data['error'] == 'EMAIL_NOT_VERIFIED'


@pytest.mark.django_db
class TestLogoutView:
    """Test user logout endpoint."""
    
    def test_logout_success(self, authenticated_client):
        """Test successful logout."""
        client, user = authenticated_client
        
        response = client.post('/api/v1/auth/logout/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Logout successful'
    
    def test_logout_unauthenticated(self, api_client):
        """Test logout fails without authentication."""
        response = api_client.post('/api/v1/auth/logout/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestForgotPasswordView:
    """Test forgot password endpoint."""
    
    def test_forgot_password_success(self, api_client, create_user):
        """Test forgot password request."""
        user = create_user(email='test@example.com')
        
        data = {'email': 'test@example.com'}
        
        response = api_client.post('/api/v1/auth/forgot-password/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'reset link sent' in response.data['message'].lower()
        
        user.refresh_from_db()
        assert user.reset_token is not None
        assert user.reset_sent_at is not None
    
    def test_forgot_password_nonexistent_email(self, api_client):
        """Test forgot password with non-existent email (should not reveal)."""
        data = {'email': 'nonexistent@example.com'}
        
        response = api_client.post('/api/v1/auth/forgot-password/', data)
        
        # Should return success to avoid email enumeration
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestResetPasswordView:
    """Test password reset endpoint."""
    
    def test_reset_password_success(self, api_client, create_user):
        """Test successful password reset."""
        user = create_user()
        user.reset_token = 'reset-token-123'
        user.reset_sent_at = timezone.now()
        user.save()
        
        data = {
            'password': 'NewSecurePass123!',
            'password_confirm': 'NewSecurePass123!'
        }
        
        response = api_client.post('/api/v1/auth/reset-password/reset-token-123/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Password reset successful'
        
        user.refresh_from_db()
        assert user.check_password('NewSecurePass123!')
        assert user.reset_token is None
    
    def test_reset_password_invalid_token(self, api_client):
        """Test reset fails with invalid token."""
        data = {
            'password': 'NewPass123!',
            'password_confirm': 'NewPass123!'
        }
        
        response = api_client.post('/api/v1/auth/reset-password/invalid-token/', data)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['error'] == 'INVALID_TOKEN'


@pytest.mark.django_db
class TestChangePasswordView:
    """Test change password endpoint."""
    
    def test_change_password_success(self, authenticated_client):
        """Test successful password change."""
        client, user = authenticated_client
        
        data = {
            'old_password': 'TestPass123',
            'new_password': 'NewSecurePass123!',
            'new_password_confirm': 'NewSecurePass123!'
        }
        
        response = client.post('/api/v1/auth/change-password/', data)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['message'] == 'Password changed successfully'
        
        user.refresh_from_db()
        assert user.check_password('NewSecurePass123!')
    
    def test_change_password_wrong_old_password(self, authenticated_client):
        """Test change password fails with wrong old password."""
        client, user = authenticated_client
        
        data = {
            'old_password': 'WrongPassword',
            'new_password': 'NewSecurePass123!',
            'new_password_confirm': 'NewSecurePass123!'
        }
        
        response = client.post('/api/v1/auth/change-password/', data)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['error'] == 'INVALID_PASSWORD'


@pytest.mark.django_db
class TestGetCurrentUserView:
    """Test get current user endpoint."""
    
    def test_get_current_user_success(self, authenticated_client):
        """Test getting current user profile."""
        client, user = authenticated_client
        
        response = client.get('/api/v1/auth/me/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == user.email
        assert 'roles' in response.data
    
    def test_get_current_user_unauthenticated(self, api_client):
        """Test getting current user fails without authentication."""
        response = api_client.get('/api/v1/auth/me/')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        