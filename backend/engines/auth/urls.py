"""
Auth Engine URLs
"""

from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from engines.auth import views

app_name = "auth"

urlpatterns = [
    # Registration & Verification
    path("register/", views.register, name="register"),
    path("verify-email/<str:token>/", views.verify_email, name="verify-email"),
    path("resend-verification/", views.resend_verification, name="resend-verification"),
    # Login & Logout
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    # Password Management
    path("forgot-password/", views.forgot_password, name="forgot-password"),
    path("reset-password/<str:token>/", views.reset_password, name="reset-password"),
    path("change-password/", views.change_password, name="change-password"),
    # Profile
    path("me/", views.get_current_user, name="current-user"),
]
