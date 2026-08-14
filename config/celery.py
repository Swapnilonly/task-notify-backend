"""
config/celery.py

Celery application entry point.
Auto-discovers tasks from every INSTALLED_APP.

Start workers:
  celery -A config worker -l info -c 4
  celery -A config beat   -l info
  celery -A config flower                    (monitoring UI)
  celery -A config worker -l info -P solo
"""

import os
import logging

from celery import Celery
from celery.signals import task_failure, task_retry, task_success

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("task_notify")

# Pull all CELERY_* keys from Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")
app.conf.worker_hijack_root_logger = False

# Auto-discover tasks.py in every installed app
app.autodiscover_tasks()

celery_logger = logging.getLogger("celery")


# ─── Signal hooks for centralised Celery logging ──────────────────────────────

@task_success.connect
def on_task_success(sender=None, result=None, **kwargs):
    celery_logger.info(
        "celery_task_success",
        extra={"task": sender.name, "result": str(result)[:200]},
    )


@task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, traceback=None, **kwargs):
    celery_logger.error(
        "celery_task_failed",
        extra={"task": sender.name, "task_id": task_id, "error": str(exception)},
        exc_info=True,
    )
    # Write failure to ActivityLog so admins can see it in /api/activity-logs/
    try:
        from logs.utils import log_activity
        log_activity(
            action="celery.task_failed",
            resource_type="CeleryTask",
            resource_id=task_id,
            metadata={"task": sender.name, "error": str(exception)},
        )
    except Exception:
        pass  # Never let signal handler crash the worker


@task_retry.connect
def on_task_retry(sender=None, reason=None, **kwargs):
    celery_logger.warning(
        "celery_task_retry",
        extra={"task": sender.name, "reason": str(reason)},
    )