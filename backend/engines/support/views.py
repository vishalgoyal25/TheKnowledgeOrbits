from rest_framework import viewsets, mixins, permissions
from .models import Feedback
from .serializers import FeedbackSerializer

class FeedbackViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for handling public feedback submissions.
    Only allows 'POST' (create) for non-authenticated users.
    """
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.AllowAny]
