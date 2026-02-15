"""
Authorization Engine Serializers

For role management operations.
"""

from rest_framework import serializers
from engines.auth.models import Role, RoleAssignment, User


class RoleSerializer(serializers.ModelSerializer):
    """Role serializer."""
    
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'user_count', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def get_user_count(self, obj):
        """Count users with this role."""
        return obj.assignments.count()


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """Role assignment serializer."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    
    class Meta:
        model = RoleAssignment
        fields = ['id', 'user', 'user_email', 'role', 'role_name', 'created_at']
        read_only_fields = ['id', 'created_at']


class AssignRoleSerializer(serializers.Serializer):
    """Serializer for assigning role to user."""
    
    user_id = serializers.UUIDField(required=True)
    role_name = serializers.ChoiceField(
        choices=['admin', 'content_manager', 'student', 'free_user'],
        required=True
    )


class RemoveRoleSerializer(serializers.Serializer):
    """Serializer for removing role from user."""
    
    user_id = serializers.UUIDField(required=True)
    role_name = serializers.ChoiceField(
        choices=['admin', 'content_manager', 'student', 'free_user'],
        required=True
    )


class UserRolesSerializer(serializers.ModelSerializer):
    """User with roles serializer."""
    
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'roles']
    
    def get_roles(self, obj):
        """Get user's role names."""
        return [
            assignment.role.name
            for assignment in obj.role_assignments.select_related('role').all()
        ]

        