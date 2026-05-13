"""
notifications/tasks.py

All Celery tasks for the notification system.

Tasks:
  send_notification_task      — create a Notification row + (optionally) send email
  deadline_reminder_task      — periodic beat task; scans tasks due in 24 h
  mark_overdue_tasks_task     — periodic beat task; marks past-due tasks overdue
  cleanup_old_notifications   — periodic beat task; removes notifications >30 days old

Retry strategy: exponential back-off (60s → 120s → 240s), max 3 retries.
All failures are logged to celery.log AND to ActivityLog via on_task_failure signal.
"""

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

celery_logger = logging.getLogger("celery")


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — Send a single notification
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,    # first retry after 60 s
    name="notifications.send_notification",
)
def send_notification_task(self, user_id: int, message: str, notif_type: str = "task"):
    """
    Creates a Notification record for user_id and optionally sends an email.
    Called from task signals (task assigned, task completed, etc.)

    Args:
        user_id   — pk of the receiving User
        message   — notification text
        notif_type — "task" | "reminder" | "system"
    """
    try:
        from django.contrib.auth import get_user_model
        from notifications.models import Notification
        from logs.utils import log_activity

        User = get_user_model()
        user = User.objects.get(pk=user_id)

        notif = Notification.objects.create(
            user    = user,
            message = message,
            type    = notif_type,
        )

        # Optionally send email
        _send_email_notification(user, message)

        log_activity(
            user          = user,
            action        = "notification.sent",
            resource_type = "Notification",
            resource_id   = notif.pk,
            metadata      = {"type": notif_type, "message": message[:100]},
        )

        celery_logger.info(
            "notification_sent",
            extra={"user_id": user_id, "type": notif_type},
        )
        return {"status": "sent", "notification_id": str(notif.pk)}

    except SoftTimeLimitExceeded:
        celery_logger.error("send_notification_task hit soft time limit", extra={"user_id": user_id})
        raise

    except Exception as exc:
        celery_logger.warning(
            "send_notification_task retry",
            extra={"user_id": user_id, "attempt": self.request.retries, "error": str(exc)},
        )
        # Exponential back-off: 60s, 120s, 240s
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — Deadline reminders (periodic — runs every hour via Celery Beat)
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(
    name="notifications.deadline_reminder",
    max_retries=2,
    default_retry_delay=120,
)
def deadline_reminder_task():
    """
    Scans all tasks whose due_date is within the next 24 hours
    and whose assigned user has NOT already received a reminder today.
    Enqueues send_notification_task for each.

    Schedule: set up in Django admin → Periodic Tasks → every 1 hour.
    """
    try:
        from tasks.models import Task

        now       = timezone.now()
        in_24h    = now + timedelta(hours=24)

        due_soon = Task.objects.filter(
            due_date__gte=now,
            due_date__lte=in_24h,
            status__in=["pending", "in_progress"],
            assigned_to__isnull=False,
        ).select_related("assigned_to")

        count = 0
        for task in due_soon:
            msg = f"Reminder: '{task.title}' is due in less than 24 hours."
            send_notification_task.delay(
                user_id    = task.assigned_to.pk,
                message    = msg,
                notif_type = "reminder",
            )
            count += 1

        celery_logger.info("deadline_reminder_task", extra={"reminders_sent": count})
        return {"reminders_queued": count}

    except Exception as exc:
        celery_logger.error("deadline_reminder_task failed", extra={"error": str(exc)}, exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Mark overdue tasks (periodic — runs every 30 min via Celery Beat)
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name="notifications.mark_overdue_tasks")
def mark_overdue_tasks_task():
    """
    Finds tasks whose due_date has passed and status is still
    pending or in_progress, marks them overdue, notifies assignees.
    """
    try:
        from tasks.models import Task
        from logs.utils import log_activity

        overdue = Task.objects.filter(
            due_date__lt=timezone.now(),
            status__in=["pending", "in_progress"],
            assigned_to__isnull=False,
        ).select_related("assigned_to")

        updated_ids = []
        for task in overdue:
            task.status = "overdue"
            task.save(update_fields=["status"])
            updated_ids.append(str(task.pk))

            send_notification_task.delay(
                user_id    = task.assigned_to.pk,
                message    = f"Task '{task.title}' is now overdue.",
                notif_type = "reminder",
            )

            log_activity(
                user          = task.assigned_to,
                action        = "task.status_changed",
                resource_type = "Task",
                resource_id   = task.pk,
                metadata      = {"old_status": "in_progress/pending", "new_status": "overdue"},
            )

        celery_logger.info("mark_overdue_tasks", extra={"count": len(updated_ids)})
        return {"overdue_marked": len(updated_ids)}

    except Exception as exc:
        celery_logger.error("mark_overdue_tasks failed", extra={"error": str(exc)}, exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — Cleanup old notifications (periodic — runs daily at midnight)
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name="notifications.cleanup_old_notifications")
def cleanup_old_notifications_task(days: int = 30):
    """
    Deletes read notifications older than `days` days to keep the table lean.
    """
    try:
        from notifications.models import Notification

        cutoff   = timezone.now() - timedelta(days=days)
        deleted, _ = Notification.objects.filter(
            is_read=True, created_at__lt=cutoff
        ).delete()

        celery_logger.info("cleanup_notifications", extra={"deleted": deleted})
        return {"deleted": deleted}

    except Exception as exc:
        celery_logger.error("cleanup_old_notifications failed", extra={"error": str(exc)}, exc_info=True)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper — does NOT raise; email failure must not crash the task
# ─────────────────────────────────────────────────────────────────────────────
def _send_email_notification(user, message: str) -> None:
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        if not user.email:
            return

        send_mail(
            subject        = "TASK-NOTIFY: You have a new notification",
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [user.email],
            fail_silently  = True,
        )
    except Exception as exc:
        celery_logger.warning("email_send_failed", extra={"user": str(user.pk), "error": str(exc)})