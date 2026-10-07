# notifications/tests/test_notification_system.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from tasks.models import Task, TaskWatcher
from notifications.models import (
    TaskEvent, Notification, NotificationPreference, NotificationDelivery
)

User = get_user_model()


class BaseSetup(TestCase):
    """Common fixtures — har test class isse inherit karega."""

    def setUp(self):
        self.assignee = User.objects.create(email='assignee@example.com')
        self.creator = User.objects.create(email='creator@example.com')
        self.watcher = User.objects.create(email='watcher@example.com')
        self.outsider = User.objects.create(email='outsider@example.com')

        self.task = Task.objects.create(
            title='Fix login bug',
            created_by=self.creator,
            assigned_to=self.assignee,
        )
        TaskWatcher.objects.create(task_id=self.task.id, user_id=self.watcher.id)

        # teeno recipients (assignee, creator, watcher) ke liye preference enable karo
        # for user in [self.assignee, self.creator, self.watcher]:
        #     NotificationPreference.objects.create(
        #         user=user, event_type='CREATED', channel='IN_APP', enabled=True
        #     )

        for user in [self.assignee, self.creator, self.watcher]:
            NotificationPreference.objects.update_or_create(
                user=user, event_type='CREATED', channel='IN_APP',
                defaults={'enabled': True},
            )