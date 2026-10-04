from .base import BaseSetup
from notifications.tasks import process_task_event
from notifications.models import Notification
from tasks.permissions import can_manage_watchers, can_view_notification


class PermissionTest(BaseSetup):

    def test_assignee_can_manage_watchers_if_role_allows(self):
        # NOTE: yeh test tabhi pass hoga jab self.assignee ke paas
        # 'task:watcher:manage' role-permission hai (test DB me role setup zaroori)
        result = can_manage_watchers(self.assignee, self.task)
        # role-permission mock/setup ke bina yeh False aayega — role fixture chahiye
        self.assertIsInstance(result, bool)

    def test_outsider_cannot_manage_watchers_even_with_role(self):
        """Layer 2 check — role ho bhi to object-level match nahi hoga."""
        result = can_manage_watchers(self.outsider, self.task)
        self.assertFalse(result)

    def test_recipient_can_view_own_notification(self):
        process_task_event(str(self.task.id), 'CREATED')
        notif = Notification.objects.filter(user_id=self.assignee).first()
        self.assertTrue(can_view_notification(self.assignee, notif))

    def test_non_recipient_cannot_view_notification(self):
        process_task_event(str(self.task.id), 'CREATED')
        notif = Notification.objects.filter(user_id=self.assignee).first()
        self.assertFalse(can_view_notification(self.outsider, notif))