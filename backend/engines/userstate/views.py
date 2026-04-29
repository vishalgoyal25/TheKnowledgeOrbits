"""User State Engine Views."""

from typing import Any, cast

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

import sentry_sdk
import structlog

from core.pagination import StandardPageNumberPagination
from engines.auth.models import User
from engines.userstate.models import (
    ReadingProgress,
    UserEvent,
    UserProgress,
    UserPreferences,
    UserProfile,
)
from engines.userstate.serializers import (
    BookmarkCreateSerializer,
    BookmarkSerializer,
    ReadingProgressSerializer,
    ReadingProgressUpdateSerializer,
    TopicMasterySerializer,
    UserEventSerializer,
    UserPreferencesSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer,
    UserProgressSerializer,
)
from engines.userstate.services.bookmark_service import get_bookmark_service
from engines.userstate.services.progress_service import get_progress_service

logger = structlog.get_logger(__name__)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_progress(request: Request) -> Response:
    """
    Get user progress.

    GET /api/v1/userstate/progress/
    """
    progress_service = get_progress_service()
    user = cast(User, request.user)
    progress = progress_service.update_progress(user)

    serializer = UserProgressSerializer(progress)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_mastery(request: Request) -> Response:
    """
    Get topic mastery scores.

    GET /api/v1/userstate/mastery/
    Query params:
        - weak (bool): Filter weak topics
        - strong (bool): Filter strong topics
    """
    user = cast(User, request.user)
    masteries = user.topic_masteries.select_related("topic").all()

    # Apply filters
    if request.query_params.get("weak"):
        masteries = masteries.filter(mastery_score__lt=50, questions_attempted__gte=3)

    if request.query_params.get("strong"):
        masteries = masteries.filter(mastery_score__gte=80, questions_attempted__gte=5)

    masteries = masteries.order_by("-mastery_score")

    paginator = StandardPageNumberPagination()
    paginated_masteries: Any = paginator.paginate_queryset(masteries, request)
    serializer = TopicMasterySerializer(paginated_masteries, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_events(request: Request) -> Response:
    """
    Get recent user events.

    GET /api/v1/userstate/events/
    Query params:
        - limit (int): Number of events (default 20)
        - event_type (str): Filter by type
    """
    limit = int(request.query_params.get("limit", 20))
    event_type = request.query_params.get("event_type")

    user = cast(User, request.user)
    events = user.events.all()

    if event_type:
        events = events.filter(event_type=event_type)

    events = events[:limit]

    serializer = UserEventSerializer(events, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_bookmarks(request: Request) -> Response:
    """
    List user bookmarks.

    GET /api/v1/userstate/bookmarks/
    Query params:
        - content_type (str): Filter by type
    """
    content_type = request.query_params.get("content_type")

    user = cast(User, request.user)
    bookmark_service = get_bookmark_service()

    try:
        bookmarks = bookmark_service.get_bookmarks(user=user, content_type=content_type)

        # We need to turn list into queryset or deal with list inside paginator.
        # Since get_bookmarks returns a queryset (Bookmark config), we can paginate directly.
        paginator = StandardPageNumberPagination()
        paginated_bookmarks: Any = paginator.paginate_queryset(bookmarks, request)
        serializer = BookmarkSerializer(paginated_bookmarks, many=True)
        return paginator.get_paginated_response(serializer.data)

    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_bookmark(request: Request) -> Response:
    """
    Add bookmark.

    POST /api/v1/userstate/bookmarks/
    Body: {
        "content_type": "article",
        "content_id": "uuid",
        "notes": "optional"
    }
    """
    serializer = BookmarkCreateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = cast(User, request.user)
    bookmark_service = get_bookmark_service()

    try:
        bookmark = bookmark_service.add_bookmark(
            user=user,
            content_type=serializer.validated_data["content_type"],
            content_id=str(serializer.validated_data["content_id"]),
            notes=serializer.validated_data.get("notes", ""),
        )

        result = BookmarkSerializer(bookmark)
        return Response(result.data, status=status.HTTP_201_CREATED)

    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_bookmark(request: Request, bookmark_id: str) -> Response:
    """
    Remove bookmark.

    DELETE /api/v1/userstate/bookmarks/{bookmark_id}/
    """
    user = cast(User, request.user)
    bookmark_service = get_bookmark_service()

    try:
        bookmark_service.remove_bookmark(user=user, bookmark_id=bookmark_id)

        return Response({"message": "Bookmark removed"})

    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_reading_progress(request: Request, article_id: str) -> Response:
    """
    Get reading progress for article.

    GET /api/v1/userstate/reading-progress/{article_id}/
    """
    try:
        user = cast(User, request.user)
        progress = ReadingProgress.objects.get(user=user, article_id=article_id)
        serializer = ReadingProgressSerializer(progress)
        return Response(serializer.data)

    except ReadingProgress.DoesNotExist:
        return Response(
            {"percent_read": 0, "last_position": 0}, status=status.HTTP_200_OK
        )


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_reading_progress(request: Request, article_id: str) -> Response:
    """
    Update reading progress.

    PUT /api/v1/userstate/reading-progress/{article_id}/
    Body: {
        "percent_read": 45.5,
        "last_position": 1234
    }
    """
    serializer = ReadingProgressUpdateSerializer(
        data={**request.data, "article_id": article_id}
    )

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = cast(User, request.user)
    progress, created = ReadingProgress.objects.update_or_create(
        user=user,
        article_id=article_id,
        defaults={
            "percent_read": serializer.validated_data["percent_read"],
            "last_position": serializer.validated_data["last_position"],
        },
    )

    # Check for completion (75%)
    if progress.percent_read >= 75.0:
        exists = UserEvent.objects.filter(
            user=user,
            event_type="article_read",
            event_data__article_id=str(article_id),
        ).exists()

        if not exists:
            title = "Unknown Article"
            try:
                from engines.article_generation.models import Article

                article = Article.objects.get(id=article_id)
                title = article.title
            except Exception as e:
                sentry_sdk.capture_exception(e)
                logger.debug(
                    "article_title_lookup_failed", article_id=article_id, error=str(e)
                )

            UserEvent.objects.create(
                user=user,
                event_type="article_read",
                event_data={"article_id": str(article_id), "title": title},
            )

            user_progress, _ = UserProgress.objects.get_or_create(user=user)
            user_progress.total_articles_read += 1
            user_progress.save()

    result = ReadingProgressSerializer(progress)
    return Response(result.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_reading_progress(request: Request) -> Response:
    """
    List user reading progress.

    GET /api/v1/userstate/reading-progress/
    """
    user = cast(User, request.user)
    progress = ReadingProgress.objects.filter(user=user).order_by("-updated_at")

    paginator = StandardPageNumberPagination()
    paginated_progress: Any = paginator.paginate_queryset(progress, request)
    serializer = ReadingProgressSerializer(paginated_progress, many=True)
    return paginator.get_paginated_response(serializer.data)


# ── Profile ───────────────────────────────────────────────────────────────────


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request: Request) -> Response:
    """
    GET /api/v1/userstate/profile/
    Returns full profile including flattened auth fields.
    """
    user = cast(User, request.user)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    serializer = UserProfileSerializer(profile)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request: Request) -> Response:
    """
    PATCH /api/v1/userstate/profile/update/
    Body: { "full_name": "...", "bio": "..." }
    """
    user = cast(User, request.user)
    serializer = UserProfileUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    profile, _ = UserProfile.objects.get_or_create(user=user)

    if "full_name" in serializer.validated_data:
        user.full_name = serializer.validated_data["full_name"]
        user.save(update_fields=["full_name"])

    if "bio" in serializer.validated_data:
        profile.bio = serializer.validated_data["bio"]
        profile.save(update_fields=["bio"])

    logger.info("profile_updated", user_email=user.email)
    return Response(UserProfileSerializer(profile).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_avatar(request: Request) -> Response:
    """
    POST /api/v1/userstate/profile/avatar/
    Body: multipart/form-data  { "avatar": <file> }
    Returns: { "avatar_url": "https://..." }
    """
    import cloudinary.uploader  # type: ignore

    avatar_file = request.FILES.get("avatar")
    if not avatar_file:
        return Response(
            {"error": "No file provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if avatar_file.content_type not in allowed_types:
        return Response(
            {"error": "Only JPEG, PNG, and WEBP images are allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = cast(User, request.user)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    try:
        # Delete previous avatar from Cloudinary if one exists
        if profile.avatar_public_id:
            cloudinary.uploader.destroy(profile.avatar_public_id)

        result = cloudinary.uploader.upload(
            avatar_file,
            folder="tko/avatars",
            public_id=f"user_{user.id}",
            overwrite=True,
            resource_type="image",
            transformation={
                "width": 400,
                "height": 400,
                "crop": "fill",
                "gravity": "face",
            },
        )

        profile.avatar_url = result["secure_url"]
        profile.avatar_public_id = result["public_id"]
        profile.save(update_fields=["avatar_url", "avatar_public_id"])

        logger.info("avatar_uploaded", user_email=user.email)
        return Response({"avatar_url": profile.avatar_url})

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("avatar_upload_failed", error=str(exc), exc_info=True)
        return Response(
            {"error": "Upload failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_avatar(request: Request) -> Response:
    """
    DELETE /api/v1/userstate/profile/avatar/delete/
    Removes avatar from Cloudinary and clears DB fields.
    """
    import cloudinary.uploader  # type: ignore

    user = cast(User, request.user)
    profile, _ = UserProfile.objects.get_or_create(user=user)

    if not profile.avatar_public_id:
        return Response({"message": "No avatar to remove."})

    try:
        cloudinary.uploader.destroy(profile.avatar_public_id)
        profile.avatar_url = ""
        profile.avatar_public_id = ""
        profile.save(update_fields=["avatar_url", "avatar_public_id"])
        logger.info("avatar_deleted", user_email=user.email)
        return Response({"message": "Avatar removed."})

    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("avatar_delete_failed", error=str(exc), exc_info=True)
        return Response(
            {"error": "Delete failed. Please try again."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ── Preferences ───────────────────────────────────────────────────────────────


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def preferences(request: Request) -> Response:
    """
    GET  /api/v1/userstate/preferences/  — fetch current prefs (auto-created with defaults)
    PATCH /api/v1/userstate/preferences/ — update any subset of fields
    """
    user = cast(User, request.user)
    prefs, _ = UserPreferences.objects.get_or_create(user=user)

    if request.method == "GET":
        return Response(UserPreferencesSerializer(prefs).data)

    serializer = UserPreferencesSerializer(prefs, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    logger.info("preferences_updated", user_email=user.email)
    return Response(serializer.data)
