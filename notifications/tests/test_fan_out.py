from .base import BaseSetup
from notifications.tasks import process_task_event
from notifications.models import Notification, TaskEvent, NotificationPreference
from tasks.models import TaskWatcher
from django.contrib.auth import get_user_model
User = get_user_model()

class FanOutTest(BaseSetup):

    def test_notification_created_for_assignee_creator_and_watcher(self):
        process_task_event(str(self.task.id), 'CREATED')

        recipients = set(Notification.objects.values_list('user_id', flat=True))
        expected = {self.assignee.id, self.creator.id, self.watcher.id}
        self.assertEqual(recipients, expected)

    def test_outsider_does_not_get_notified(self):
        process_task_event(str(self.task.id), 'CREATED')
        self.assertFalse(
            Notification.objects.filter(user=self.outsider).exists()
        )

    def test_task_event_row_created(self):
        process_task_event(str(self.task.id), 'CREATED')
        self.assertEqual(TaskEvent.objects.filter(task=self.task).count(), 1)
        event = TaskEvent.objects.first()
        self.assertEqual(event.event_type, 'CREATED')
        self.assertEqual(event.actor_id, self.creator.id)

    def test_disabled_preference_is_excluded(self):
        # watcher apna preference off kar deta hai
        NotificationPreference.objects.filter(
            user=self.watcher, event_type='CREATED'
        ).update(enabled=False)

        process_task_event(str(self.task.id), 'CREATED')

        self.assertFalse(
            Notification.objects.filter(user=self.watcher).exists()
        )
        # baaki dono ko phir bhi milna chahiye
        self.assertTrue(Notification.objects.filter(user=self.assignee).exists())

    def test_no_preference_means_no_notification(self):
        # naya user jiska koi preference row hi nahi hai
        new_watcher = User.objects.create(email='new@example.com')
        NotificationPreference.objects.filter(user=new_watcher).delete()
        TaskWatcher.objects.create(task=self.task, user=new_watcher)

        process_task_event(str(self.task.id), 'CREATED')

        self.assertFalse(
            Notification.objects.filter(user=new_watcher).exists()
        )

    def test_required_fields_are_populated(self):
        """Issue #11 regression test — event_id, message, event_type, title."""
        process_task_event(str(self.task.id), 'CREATED')
        notif = Notification.objects.first()

        self.assertTrue(notif.event_id)
        self.assertTrue(notif.message)
        self.assertEqual(notif.event_type, 'CREATED')
        self.assertIn(self.task.title, notif.title)
        self.assertEqual(notif.channel, 'IN_APP')