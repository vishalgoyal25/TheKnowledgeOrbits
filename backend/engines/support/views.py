from rest_framework import viewsets, mixins, permissions
from .models import Feedback
from .serializers import FeedbackSerializer


class FeedbackViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):  # type: ignore
    """
    ViewSet for handling public feedback submissions.

    Attributes:
        queryset: All Feedback instances.
        serializer_class: FeedbackSerializer.
        permission_classes: AllowAny (Public).
    """

    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.AllowAny]
