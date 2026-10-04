# notifications/tests/test_regression.py

from .base import BaseSetup
from notifications.tasks import process_task_event


class RegressionTest(BaseSetup):

    def test_process_task_event_does_not_raise_field_error(self):
        """
        Regression: pehle 'assignee' field name galat tha (asli field assigned_to hai),
        jo FieldError raise karta tha select_related() me. Yeh test crash na hona confirm karta hai.
        """
        try:
            process_task_event(str(self.task.id), 'CREATED')
        except Exception as e:
            self.fail(f"process_task_event raised unexpectedly: {e}")