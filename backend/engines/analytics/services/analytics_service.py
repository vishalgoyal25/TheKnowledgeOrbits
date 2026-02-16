"""
Analytics Service

Handles data aggregation from UserEvent logs.
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Avg, Count

from engines.analytics.models import DailyAggregate
from engines.userstate.models import UserEvent

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for aggregating user analytics."""
    
    @staticmethod
    def aggregate_user_day(user, date):
        """
        Aggregate user activity for specific date.
        
        Args:
            user: User instance
            date: Date to aggregate (datetime.date)
            
        Returns:
            DailyAggregate instance
        """
        day_start = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(date, datetime.max.time()))
        
        # Get events for this day
        events = UserEvent.objects.filter(
            user=user,
            created_at__gte=day_start,
            created_at__lte=day_end
        )
        
        # Count articles read
        articles_read = events.filter(
            event_type='article_read'
        ).values('event_data__article_id').distinct().count()
        
        # Count quizzes taken
        quizzes_taken = events.filter(
            event_type='quiz_completed'
        ).count()
        
        # Sum quiz scores
        quiz_events = events.filter(event_type='quiz_completed')
        total_score = sum(
            float(event.event_data.get('score', 0))
            for event in quiz_events
        )
        
        # Calculate time spent (placeholder - implement based on actual tracking)
        time_spent_seconds = 0  # TODO: Implement time tracking
        
        # Create or update aggregate
        aggregate, created = DailyAggregate.objects.update_or_create(
            user=user,
            date=date,
            defaults={
                'articles_read': articles_read,
                'quizzes_taken': quizzes_taken,
                'total_score': total_score,
                'time_spent_seconds': time_spent_seconds,
            }
        )
        
        logger.info(
            f"Aggregated {user.email} for {date}: "
            f"{articles_read} articles, {quizzes_taken} quizzes"
        )
        
        return aggregate
    
    @staticmethod
    def aggregate_all_users(date):
        """
        Aggregate all users for specific date.
        
        Args:
            date: Date to aggregate
            
        Returns:
            int: Number of users aggregated
        """
        from engines.auth.models import User
        
        users = User.objects.filter(is_active=True)
        count = 0
        
        for user in users:
            try:
                AnalyticsService.aggregate_user_day(user, date)
                count += 1
            except Exception as e:
                logger.error(f"Failed to aggregate {user.email}: {str(e)}")
        
        logger.info(f"Aggregated {count} users for {date}")
        return count
    
    @staticmethod
    def get_weekly_stats(user):
        """
        Get user's stats for last 7 days.
        
        Returns:
            dict: Weekly statistics
        """
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        aggregates = DailyAggregate.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        return {
            'period': 'week',
            'start_date': start_date,
            'end_date': end_date,
            'total_articles': sum(a.articles_read for a in aggregates),
            'total_quizzes': sum(a.quizzes_taken for a in aggregates),
            'average_score': (
                sum(a.total_score for a in aggregates) /
                sum(a.quizzes_taken for a in aggregates)
                if sum(a.quizzes_taken for a in aggregates) > 0 else 0
            ),
            'daily_data': [
                {
                    'date': str(a.date),
                    'articles': a.articles_read,
                    'quizzes': a.quizzes_taken,
                    'avg_score': a.average_score
                }
                for a in aggregates
            ]
        }
    
    @staticmethod
    def get_monthly_stats(user):
        """Get user's stats for last 30 days."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        aggregates = DailyAggregate.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
        
        return {
            'period': 'month',
            'start_date': start_date,
            'end_date': end_date,
            'total_articles': sum(a.articles_read for a in aggregates),
            'total_quizzes': sum(a.quizzes_taken for a in aggregates),
            'average_score': (
                sum(a.total_score for a in aggregates) /
                sum(a.quizzes_taken for a in aggregates)
                if sum(a.quizzes_taken for a in aggregates) > 0 else 0
            ),
            'daily_data': [
                {
                    'date': str(a.date),
                    'articles': a.articles_read,
                    'quizzes': a.quizzes_taken,
                    'avg_score': a.average_score
                }
                for a in aggregates
            ]
        }


# Singleton
_analytics_service = None

def get_analytics_service() -> AnalyticsService:
    """Get or create global analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service

    