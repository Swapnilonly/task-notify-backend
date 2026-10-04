from notifications.models import NotificationPreference
from notifications.models import Notification

def resolve_recipient_ids(task):
    watcher_ids = set(task.watchers.values_list('user_id', flat=True))
    return watcher_ids | {task.assigned_to_id, task.created_by_id} - {None}


def get_enabled_channels(recipient_ids, event_type):
    return NotificationPreference.objects.filter(
        user_id__in=recipient_ids, event_type=event_type, enabled=True
    ).values_list('user_id', 'channel')

def build_notifications(task, event, prefs):
    notifications = []

    for user_id, channel in prefs:
        notification = Notification(
            user_id=user_id,
            task_event=event,
            channel=channel,
            title=f"Task update: {task.title}",
            message=f"'{task.title}' status: {event.event_type}",
            type=Notification.Type.TASK,
            event_type=event.event_type,
            event_id=f"{event.id}:{user_id}:{channel}",
        )

        notifications.append(notification)

    return notifications

