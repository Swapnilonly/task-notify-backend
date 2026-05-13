"""
services/dashboard_service.py

All heavy DB queries for dashboard and reporting endpoints.
Results are cached in Redis. Cache is busted by Task signals.
"""

import logging

from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

logger   = logging.getLogger("app")
CACHE_TTL = settings.CACHE_TTL

DASHBOARD_CACHE_KEY = "tnb:dashboard_summary"


def get_dashboard_summary(user=None) -> dict:
    """
    Returns task counts grouped by status.
    Admins see all tasks; regular users see only their tasks.
    Result is cached for CACHE_TTL["DASHBOARD"] seconds.
    """
    cache_key = DASHBOARD_CACHE_KEY if (user and user.is_admin) else f"{DASHBOARD_CACHE_KEY}:{user.pk}"

    cached = cache.get(cache_key)
    if cached:
        logger.debug("dashboard_cache_hit", extra={"user": str(getattr(user, "pk", ""))})
        return cached

    from tasks.models import Task

    qs = Task.objects.all() if (user and user.is_admin) else Task.objects.filter(
        Q(assigned_to=user) | Q(created_by=user)
    )

    counts = qs.aggregate(
        total       = Count("id"),
        pending     = Count("id", filter=Q(status="pending")),
        in_progress = Count("id", filter=Q(status="in_progress")),
        completed   = Count("id", filter=Q(status="completed")),
        overdue     = Count("id", filter=Q(status="overdue")),
    )

    summary = {
        "total":            counts["total"],
        "pending":          counts["pending"],
        "in_progress":      counts["in_progress"],
        "completed":        counts["completed"],
        "overdue":          counts["overdue"],
        "completion_rate":  round(
                                (counts["completed"] / counts["total"] * 100)
                                if counts["total"] else 0,
                                2,
                            ),
        "generated_at": timezone.now().isoformat(),
    }

    cache.set(cache_key, summary, timeout=CACHE_TTL["DASHBOARD"])
    logger.info("dashboard_summary_computed", extra={"user": str(getattr(user, "pk", ""))})
    return summary


def get_report_data(user=None, start_date=None, end_date=None, assigned_to_id=None) -> dict:
    """
    Returns task activity report filtered by date range and/or assignee.
    Cached for CACHE_TTL["REPORT"] seconds.
    """
    from tasks.models import Task

    cache_key = f"tnb:report:{getattr(user,'pk','all')}:{start_date}:{end_date}:{assigned_to_id}"
    cached    = cache.get(cache_key)
    if cached:
        return cached

    qs = Task.objects.all() if (user and user.is_admin) else Task.objects.filter(
        Q(assigned_to=user) | Q(created_by=user)
    )

    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if assigned_to_id:
        qs = qs.filter(assigned_to_id=assigned_to_id)

    # Aggregate by status
    by_status = list(
        qs.values("status").annotate(count=Count("id")).order_by("status")
    )
    # Aggregate by priority
    by_priority = list(
        qs.values("priority").annotate(count=Count("id")).order_by("priority")
    )

    result = {
        "total_tasks":  qs.count(),
        "by_status":    by_status,
        "by_priority":  by_priority,
        "filters": {
            "start_date":     str(start_date) if start_date else None,
            "end_date":       str(end_date)   if end_date   else None,
            "assigned_to_id": str(assigned_to_id) if assigned_to_id else None,
        },
        "generated_at": timezone.now().isoformat(),
    }

    cache.set(cache_key, result, timeout=CACHE_TTL["REPORT"])
    logger.info("report_computed", extra={"user": str(getattr(user, "pk", "")), "filters": result["filters"]})
    return result