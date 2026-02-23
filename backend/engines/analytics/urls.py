"""
Analytics Engine URLs
"""

from django.urls import path

from engines.analytics import views

app_name = "analytics"

urlpatterns = [
    path("dashboard/", views.get_dashboard, name="dashboard"),
    path("weekly-stats/", views.get_weekly_stats, name="weekly-stats"),
    path("monthly-stats/", views.get_monthly_stats, name="monthly-stats"),
    path("insights/", views.get_insights, name="insights"),
    path("generate-insights/", views.generate_insights, name="generate-insights"),
]
