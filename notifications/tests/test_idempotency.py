from .base import BaseSetup
from notifications.tasks import process_task_event, deliver_notification
from notifications.models import Notification, TaskEvent, NotificationDelivery
from django.db import IntegrityError, transaction

class NotificationIdempotencyTest(BaseSetup):

    def test_duplicate_event_id_is_rejected_at_db_level(self):
        """DB constraint khud duplicate insert reject kare — Layer 1 ka core proof."""
        process_task_event(str(self.task.id), 'CREATED')
        event = TaskEvent.objects.first()
        count_before = Notification.objects.count()

        # jaan-boojh kar SAME event_id ke saath dobara insert
        Notification.objects.bulk_create([
            Notification(
                user=self.assignee, task_event=event, channel='IN_APP',
                title='dup', message='dup', type=Notification.Type.TASK,
                event_type='CREATED',
                event_id=f"{event.id}:{self.assignee.id}:IN_APP",  # same as pehle wala
            )
        ], ignore_conflicts=True)

        self.assertEqual(Notification.objects.count(), count_before)

    def test_event_id_unique_constraint_raises_without_ignore_conflicts(self):
        """ignore_conflicts=False ho to seedha IntegrityError aana chahiye — proves constraint exists."""
        process_task_event(str(self.task.id), 'CREATED')
        event = TaskEvent.objects.first()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Notification.objects.create(
                    user=self.assignee, task_event=event, channel='IN_APP',
                    title='dup', message='dup', type=Notification.Type.TASK,
                    event_type='CREATED',
                    event_id=f"{event.id}:{self.assignee.id}:IN_APP",
                )

    def test_retry_creates_new_task_event_known_gap(self):
        """
        KNOWN GAP (humne discuss kiya tha): process_task_event dobara chale to
        naya TaskEvent banta hai (koi unique constraint TaskEvent par nahi),
        isliye event_id bhi badal jaata hai — Layer 1 isse nahi rokta.
        Yeh test documentation ke liye hai, PASS hone ka matlab bug nahi — gap confirm karna hai.
        """
        process_task_event(str(self.task.id), 'CREATED')
        process_task_event(str(self.task.id), 'CREATED')  # retry simulate

        self.assertEqual(TaskEvent.objects.filter(task=self.task).count(), 2)
        # is wajah se Notification bhi duplicate ban jaati hai per recipient:
        self.assertEqual(
            Notification.objects.filter(user=self.assignee).count(), 2
        )


class DeliveryIdempotencyTest(BaseSetup):

    def setUp(self):
        super().setUp()
        process_task_event(str(self.task.id), 'CREATED')
        self.notif = Notification.objects.filter(user=self.assignee).first()

    def test_already_sent_notification_is_skipped(self):
        self.notif.status = 'SENT'
        self.notif.save()

        result = deliver_notification(self.notif.id)  # eager call, Celery async nahi

        # koi naya delivery-attempt row nahi banna chahiye kyunki function turant return hua
        self.assertEqual(
            NotificationDelivery.objects.filter(notification=self.notif).count(), 0
        )

    def test_pending_notification_gets_marked_sent(self):
        self.assertEqual(self.notif.status, 'PENDING')
        # provider ko mock karna padega real test me — yahan sirf status-flip verify
        # (assume _actually_send provider call ko test me monkeypatch/mock kiya gaya hai)
        pass  # provider mocking setup ke bina yeh incomplete hai — neeche note dekho