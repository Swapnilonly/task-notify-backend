# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.conf import settings
from notifications.models import NotificationPreference, TaskEvent
from notifications.constants import DEFAULT_CHANNEL_ENABLED  # e.g. {"IN_APP": True, "EMAIL": False}


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def seed_default_notification_preferences(sender, instance, created, **kwargs):
    """
    Seed default notification preferences for every newly created user.

    Runs once, on user creation only (created=True). Uses ignore_conflicts
    so this is safe to call more than once without producing duplicates.
    """
    if not created:
        return

    event_types = [event_type for event_type, _label in TaskEvent.EVENT_CHOICES]
    default_rows = [
        NotificationPreference(
            user=instance,
            event_type=event_type,
            channel=channel,
            enabled=enabled,
        )
        for event_type in event_types
        for channel, enabled in DEFAULT_CHANNEL_ENABLED.items()
    ]
    NotificationPreference.objects.bulk_create(default_rows, ignore_conflicts=True)