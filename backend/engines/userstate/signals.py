"""
UserState signals — DailyAggregate auto-population.

Fires after every UserEvent save and upserts the analytics_daily_aggregate
row for that user + date. This is the bridge that makes the dashboard
weekly chart show real data instead of zeros.

Called from UserstateConfig.ready() to avoid circular imports at module load.
"""

import sentry_sdk
import structlog

logger = structlog.get_logger(__name__)


def _register() -> None:
    """Register all userstate signals. Called only from apps.py ready()."""
    from django.db.models.signals import post_save
    from django.dispatch import receiver

    from engines.userstate.models import UserEvent

    @receiver(post_save, sender=UserEvent)
    def on_event_saved(
        sender,  # noqa: ARG001
        instance: UserEvent,
        created: bool,
        **kwargs,  # noqa: ARG001
    ) -> None:
        """Upsert DailyAggregate for the user+date whenever a new event is created."""
        if not created:
            return  # Only aggregate on new events — not on updates

        try:
            from engines.analytics.services.analytics_service import (
                get_analytics_service,
            )

            event_date = instance.created_at.date()
            get_analytics_service().aggregate_user_day(instance.user, event_date)

            logger.debug(
                "daily_aggregate_updated",
                user_email=instance.user.email,
                date=str(event_date),
                event_type=instance.event_type,
            )

        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error(
                "daily_aggregate_signal_failed",
                error=str(exc),
                exc_info=True,
            )
