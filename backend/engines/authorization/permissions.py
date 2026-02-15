"""
Authorization Engine - DRF Permission Classes

Provides role-based permission classes for Django REST Framework views.
"""

from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission class: User must have 'admin' role.
    """
    
    message = "Admin role required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has admin role
        return request.user.role_assignments.filter(
            role__name='admin'
        ).exists()


class IsContentManager(permissions.BasePermission):
    """
    Permission class: User must have 'content_manager' or 'admin' role.
    """
    
    message = "Content manager or admin role required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has content_manager or admin role
        return request.user.role_assignments.filter(
            role__name__in=['admin', 'content_manager']
        ).exists()


class IsStudent(permissions.BasePermission):
    """
    Permission class: User must have 'student', 'content_manager', or 'admin' role.
    """
    
    message = "Student, content manager, or admin role required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has student, content_manager, or admin role
        return request.user.role_assignments.filter(
            role__name__in=['admin', 'content_manager', 'student']
        ).exists()


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class: User must be the owner or have admin role.
    
    Usage: For object-level permissions (e.g., edit own profile).
    """
    
    message = "Owner or admin role required."
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions only for owner or admin
        is_owner = hasattr(obj, 'user') and obj.user == request.user
        is_admin = request.user.role_assignments.filter(
            role__name='admin'
        ).exists()
        
        return is_owner or is_admin


class CanManageContent(permissions.BasePermission):
    """
    Permission class: User can manage content (upload, edit, delete).
    
    Allowed roles: admin, content_manager
    """
    
    message = "Content management permission required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Read-only for all authenticated users
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions for admin and content_manager
        return request.user.role_assignments.filter(
            role__name__in=['admin', 'content_manager']
        ).exists()


class CanGenerateQuiz(permissions.BasePermission):
    """
    Permission class: User can generate quizzes.
    
    Allowed roles: admin, content_manager
    """
    
    message = "Quiz generation permission required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.role_assignments.filter(
            role__name__in=['admin', 'content_manager']
        ).exists()


class CanGenerateArticle(permissions.BasePermission):
    """
    Permission class: User can generate articles.
    
    Allowed roles: admin, content_manager
    """
    
    message = "Article generation permission required."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.role_assignments.filter(
            role__name__in=['admin', 'content_manager']
        ).exists()
        