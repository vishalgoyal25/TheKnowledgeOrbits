"""
Authorization Engine URLs
"""

from django.urls import path

from engines.authorization import views

app_name = "authorization"

urlpatterns = [
    # Role Management (Admin Only)
    path("roles/", views.list_roles, name="list-roles"),
    path("roles/<uuid:role_id>/", views.get_role, name="get-role"),
    path("assign-role/", views.assign_role, name="assign-role"),
    path("remove-role/", views.remove_role, name="remove-role"),
    path("user-roles/<uuid:user_id>/", views.get_user_roles, name="user-roles"),
]
