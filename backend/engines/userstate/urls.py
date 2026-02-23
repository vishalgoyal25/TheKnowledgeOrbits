"""User State Engine URLs."""

from django.urls import path

from engines.userstate import views

app_name = "userstate"

urlpatterns = [
    # Progress & Mastery
    path("progress/", views.get_progress, name="progress"),
    path("mastery/", views.get_mastery, name="mastery"),
    path("events/", views.get_events, name="events"),
    # Bookmarks
    path("bookmarks/", views.list_bookmarks, name="list-bookmarks"),
    path("bookmarks/add/", views.add_bookmark, name="add-bookmark"),
    path(
        "bookmarks/<uuid:bookmark_id>/", views.remove_bookmark, name="remove-bookmark"
    ),
    # Reading Progress
    path(
        "reading-progress/", views.list_reading_progress, name="list-reading-progress"
    ),
    path(
        "reading-progress/<uuid:article_id>/",
        views.get_reading_progress,
        name="get-reading-progress",
    ),
    path(
        "reading-progress/<uuid:article_id>/update/",
        views.update_reading_progress,
        name="update-reading-progress",
    ),
]
