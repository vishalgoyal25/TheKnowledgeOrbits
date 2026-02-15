"""
Mastery Service

Handles topic mastery computation.
"""

import logging
from engines.userstate.models import TopicMastery

logger = logging.getLogger(__name__)


class MasteryService:
    """Service for computing topic mastery scores."""
    
    @staticmethod
    def update_mastery(user, topic_id: str, is_correct: bool):
        """
        Update topic mastery after quiz question.
        
        Args:
            user: User instance
            topic_id: Topic UUID
            is_correct: Whether answer was correct
        """
        mastery, created = TopicMastery.objects.get_or_create(
            user=user,
            topic_id=topic_id,
            defaults={
                'questions_attempted': 0,
                'questions_correct': 0,
                'mastery_score': 0.0
            }
        )
        
        # Increment counters
        mastery.questions_attempted += 1
        if is_correct:
            mastery.questions_correct += 1
        
        # Recalculate mastery score
        mastery.update_mastery()
        
        logger.info(
            f"Mastery updated: {user.email} - Topic {topic_id} - "
            f"{mastery.mastery_score:.1f}%"
        )
        
        return mastery
    
    @staticmethod
    def get_weak_topics(user, threshold: float = 50.0):
        """
        Get topics where user has low mastery.
        
        Args:
            user: User instance
            threshold: Mastery score threshold (default 50%)
            
        Returns:
            QuerySet of TopicMastery instances
        """
        return TopicMastery.objects.filter(
            user=user,
            mastery_score__lt=threshold,
            questions_attempted__gte=3  # At least 3 attempts
        ).select_related('topic').order_by('mastery_score')
    
    @staticmethod
    def get_strong_topics(user, threshold: float = 80.0):
        """Get topics where user has high mastery."""
        return TopicMastery.objects.filter(
            user=user,
            mastery_score__gte=threshold,
            questions_attempted__gte=5  # At least 5 attempts
        ).select_related('topic').order_by('-mastery_score')


# Singleton
_mastery_service = None

def get_mastery_service() -> MasteryService:
    """Get or create global mastery service instance."""
    global _mastery_service
    if _mastery_service is None:
        _mastery_service = MasteryService()
    return _mastery_service

    