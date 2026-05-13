from django.db import models

# Create your models here.

"""
logs/models.py
Append-only audit trail. Never update or delete rows here.
"""

import uuid

from django.conf import settings
from django.db import models


class ActivityLog(models.Model):

    class Action(models.TextChoices):
        # Auth
        USER_REGISTERED    = "user.registered",     "User registered"
        USER_LOGIN         = "user.login",           "User logged in"
        USER_LOGOUT        = "user.logout",          "User logged out"
        USER_UPDATED       = "user.updated",         "User profile updated"
        # Tasks
        TASK_CREATED       = "task.created",         "Task created"
        TASK_UPDATED       = "task.updated",         "Task updated"
        TASK_DELETED       = "task.deleted",         "Task deleted"
        TASK_ASSIGNED      = "task.assigned",        "Task assigned"
        TASK_STATUS_CHANGED= "task.status_changed",  "Task status changed"
        # Notifications
        NOTIF_SENT         = "notification.sent",    "Notification sent"
        NOTIF_READ         = "notification.read",    "Notification marked read"
        # System / Celery
        SYSTEM_ERROR       = "system.error",         "System error"
        CELERY_FAILED      = "celery.task_failed",   "Celery task failed"

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user          = models.ForeignKey(
                        settings.AUTH_USER_MODEL,
                        on_delete=models.SET_NULL,
                        null=True, blank=True,
                        related_name="activity_logs",
                        db_index=True,
                    )
    action        = models.CharField(max_length=60, choices=Action.choices, db_index=True)
    resource_type = models.CharField(max_length=60, blank=True, help_text="e.g. Task, Notification")
    resource_id   = models.CharField(max_length=100, blank=True)
    metadata      = models.JSONField(default=dict, blank=True)
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.CharField(max_length=300, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name        = "Activity Log"
        verbose_name_plural = "Activity Logs"
        indexes = [
            models.Index(fields=["user", "-created_at"],       name="log_user_time_idx"),
            models.Index(fields=["action", "-created_at"],     name="log_action_time_idx"),
            models.Index(fields=["resource_type","resource_id"], name="log_resource_idx"),
        ]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.user} → {self.action}"