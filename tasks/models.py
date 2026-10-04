"""
tasks/models.py

Task model + post_save / post_delete signals that:
  1. Write to ActivityLog (audit trail)
  2. Invalidate Redis cache for dashboard/reports
  3. Enqueue Celery notification tasks on assignment or status change
"""

import uuid
import logging

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger("app")


class Task(models.Model):

    class Status(models.TextChoices):
        PENDING     = "pending",     "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED   = "completed",   "Completed"
        OVERDUE     = "overdue",     "Overdue"

    class Priority(models.TextChoices):
        LOW    = "low",    "Low"
        MEDIUM = "medium", "Medium"
        HIGH   = "high",   "High"

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status      = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    priority    = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    due_date    = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    assigned_to = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.SET_NULL,
                    null=True, blank=True,
                    related_name="assigned_tasks",
                    db_index=True,
                  )
    created_by  = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.SET_NULL,
                    null=True,
                    related_name="created_tasks",
                  )
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["status", "-created_at"],       name="task_status_time_idx"),
            models.Index(fields=["assigned_to", "-created_at"],  name="task_user_time_idx"),
            models.Index(fields=["due_date"],                     name="task_due_date_idx"),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"


class TaskWatcher(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='watchers')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('task', 'user')   # ek user ek task ko do baar watch na kare


# ─────────────────────────────────────────────────────────────────────────────
# SIGNALS
# ─────────────────────────────────────────────────────────────────────────────

@receiver(post_save, sender=Task)
def task_post_save(sender, instance: Task, created: bool, **kwargs):
    """
    Fires after every Task.save().
    • Logs to ActivityLog
    • Invalidates cache keys
    """
    from logs.utils import log_activity
    from django.core.cache import cache

    action = "task.created" if created else "task.updated"

    log_activity(
        user          = instance.created_by,
        action        = action,
        resource_type = "Task",
        resource_id   = instance.pk,
        metadata      = {
            "title":       instance.title,
            "status":      instance.status,
            "priority":    instance.priority,
            "assigned_to": str(instance.assigned_to_id) if instance.assigned_to_id else None,
        },
    )

    # Phase 3 — bust cache so dashboard reflects the change immediately
    cache.delete_many([
        "tnb:dashboard_summary",
        f"tnb:task_detail:{instance.pk}",
    ])

    # Phase 4 — enqueue notification on assignment
    # if created and instance.assigned_to_id:
    #
    #     send_notification_task.delay(
    #         user_id    = instance.assigned_to.pk,
    #         message    = f"You have been assigned a new task: '{instance.title}'.",
    #         notif_type = "task",
    #     )
    #     logger.info(
    #         "task_assigned_notification_queued",
    #         extra={"task_id": str(instance.pk), "user_id": str(instance.assigned_to.pk)},
    #     )


@receiver(post_delete, sender=Task)
def task_post_delete(sender, instance: Task, **kwargs):
    from logs.utils import log_activity
    from django.core.cache import cache

    log_activity(
        user          = instance.created_by,
        action        = "task.deleted",
        resource_type = "Task",
        resource_id   = instance.pk,
        metadata      = {"title": instance.title},
    )
    #TO-D0
    cache.delete_many([
        "tnb:dashboard_summary",
        f"tnb:task_detail:{instance.pk}",
    ])