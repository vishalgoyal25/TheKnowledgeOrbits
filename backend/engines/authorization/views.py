"""
Authorization Engine Views

Role management API (admin only).

5 Endpoints:
1. GET /roles/
2. GET /roles/{id}/
3. POST /assign-role/
4. POST /remove-role/
5. GET /user-roles/{user_id}/
"""

from typing import cast

from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

import structlog

from engines.auth.models import Role, RoleAssignment, User
from engines.authorization.permissions import IsAdmin
from engines.authorization.serializers import (
    AssignRoleSerializer,
    RemoveRoleSerializer,
    RoleAssignmentSerializer,
    RoleSerializer,
    UserRolesSerializer,
)

logger = structlog.get_logger(__name__)


@api_view(["GET"])
@permission_classes([IsAdmin])
def list_roles(request: Request) -> Response:
    """
    List all roles.

    GET /api/v1/authorization/roles/
    """
    roles = Role.objects.all().order_by("name")
    serializer = RoleSerializer(roles, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAdmin])
def get_role(request: Request, role_id: str) -> Response:
    """
    Get role details.

    GET /api/v1/authorization/roles/{role_id}/
    """
    role = get_object_or_404(Role, id=role_id)
    serializer = RoleSerializer(role)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAdmin])
def assign_role(request: Request) -> Response:
    """
    Assign role to user.

    POST /api/v1/authorization/assign-role/
    Body: {
        "user_id": "uuid",
        "role_name": "admin"
    }
    """
    serializer = AssignRoleSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data["user_id"]
    role_name = serializer.validated_data["role_name"]

    # Get user and role
    user = get_object_or_404(User, id=user_id)
    role = get_object_or_404(Role, name=role_name)

    # Check if already assigned
    if RoleAssignment.objects.filter(user=user, role=role).exists():
        return Response(
            {"error": "ALREADY_ASSIGNED", "message": "User already has this role"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Assign role
    assignment = RoleAssignment.objects.create(user=user, role=role)

    admin_user = cast(User, request.user)
    logger.info(
        "role_assigned",
        user_email=user.email,
        role=role_name,
        assigned_by=admin_user.email,
    )

    result = RoleAssignmentSerializer(assignment)
    return Response(result.data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAdmin])
def remove_role(request: Request) -> Response:
    """
    Remove role from user.

    POST /api/v1/authorization/remove-role/
    Body: {
        "user_id": "uuid",
        "role_name": "student"
    }
    """
    serializer = RemoveRoleSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user_id = serializer.validated_data["user_id"]
    role_name = serializer.validated_data["role_name"]

    # Get user and role
    user = get_object_or_404(User, id=user_id)
    role = get_object_or_404(Role, name=role_name)

    # Check if assigned
    try:
        assignment = RoleAssignment.objects.get(user=user, role=role)
        assignment.delete()

        admin_user = cast(User, request.user)
        logger.info(
            "role_removed",
            user_email=user.email,
            role=role_name,
            removed_by=admin_user.email,
        )

        return Response({"message": "Role removed successfully"})

    except RoleAssignment.DoesNotExist:
        return Response(
            {"error": "NOT_ASSIGNED", "message": "User does not have this role"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
@permission_classes([IsAdmin])
def get_user_roles(request: Request, user_id: str) -> Response:
    """
    Get user's roles.

    GET /api/v1/authorization/user-roles/{user_id}/
    """
    user = get_object_or_404(User, id=user_id)
    serializer = UserRolesSerializer(user)
    return Response(serializer.data)
