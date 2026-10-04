from django.db import models

# Create your models here.

"""
notifications/models.py
"""

import uuid
from django.conf import settings
from django.db import models
from tasks.models import Task

class Notification(models.Model):

    class Type(models.TextChoices):
        TASK     = "task",     "Task"
        REMINDER = "reminder", "Reminder"
        SYSTEM   = "system",   "System"

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(
                    settings.AUTH_USER_MODEL,
                    on_delete=models.CASCADE,
                    related_name="notifications",
                    db_index=True,
                 )
    title = models.CharField(max_length=255, blank=True, default="")
    message    = models.TextField()
    type       = models.CharField(max_length=20, choices=Type.choices, default=Type.TASK)
    is_read    = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=50)
    task_event = models.ForeignKey('notifications.TaskEvent', null=True, blank=True, on_delete=models.SET_NULL)
    channel = models.CharField(max_length=20, default='IN_APP')
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)



    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["user", "is_read", "-created_at"], name="notif_user_read_idx"),
        ]

    def __str__(self):
        return f"[{self.type}] {self.user} — {'read' if self.is_read else 'unread'}"

class TaskEvent(models.Model):
    EVENT_CHOICES = [
        ('CREATED', 'Created'), ('ASSIGNED', 'Assigned'),
        ('STATUS_CHANGED', 'Status Changed'), ('COMMENTED', 'Commented'),
    ]
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationPreference(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=20, choices=TaskEvent.EVENT_CHOICES)
    channel = models.CharField(max_length=20, choices=[
        ('EMAIL', 'Email'), ('PUSH', 'Push'), ('IN_APP', 'In-App')
    ])
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'event_type', 'channel')


class NotificationDelivery(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE,
                                      related_name='delivery_attempts')
    attempt_number = models.IntegerField()
    status = models.CharField(max_length=20)  # SENT / FAILED
    error_message = models.TextField(null=True, blank=True)
    attempted_at = models.DateTimeField(auto_now_add=True)
