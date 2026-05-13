"""
logs/utils.py

log_activity() — one-liner helper used in every view/service.

Usage:
    from logs.utils import log_activity, audit_logger

    log_activity(
        user=request.user,
        action="task.created",
        resource_type="Task",
        resource_id=task.pk,
        metadata={"title": task.title, "priority": task.priority},
        request=request,      # optional — auto-extracts IP + UA
    )
"""

import logging

audit_logger = logging.getLogger("audit")


def log_activity(
    user=None,
    action: str = "",
    resource_type: str = "",
    resource_id=None,
    metadata: dict = None,
    request=None,
) -> None:
    """
    Writes one row to ActivityLog (DB) and one line to audit.log (file).
    Both writes happen synchronously — if you need async, wrap in a Celery task.
    """
    from logs.models import ActivityLog   # late import avoids circular deps

    ip_address = None
    user_agent = ""

    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:300]

    # 1. Persist to DB
    ActivityLog.objects.create(
        user          = user if user and getattr(user, "is_authenticated", False) else None,
        action        = action,
        resource_type = resource_type,
        resource_id   = str(resource_id) if resource_id is not None else "",
        metadata      = metadata or {},
        ip_address    = ip_address,
        user_agent    = user_agent,
    )

    # 2. Write to audit.log file
    audit_logger.info(
        "audit_event",
        extra={
            "user":          getattr(user, "email", "anonymous"),
            "user_id":       str(getattr(user, "pk", "")) if user else None,
            "action":        action,
            "resource_type": resource_type,
            "resource_id":   str(resource_id) if resource_id is not None else "",
            "metadata":      metadata or {},
            "ip_address":    ip_address,
        },
    )