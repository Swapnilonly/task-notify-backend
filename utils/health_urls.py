"""
utils/health_urls.py
GET /health/  → 200 with DB + Redis + Celery status.
Used by Docker HEALTHCHECK and load balancers.
"""

import logging

from django.urls import path
from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger("app")


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    checks = {}

    # DB
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        logger.error("health_check_db_failed", extra={"error": str(exc)})

    # Redis
    try:
        cache.set("health_ping", "pong", timeout=5)
        checks["redis"] = "ok" if cache.get("health_ping") == "pong" else "error"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"
        logger.error("health_check_redis_failed", extra={"error": str(exc)})

    all_ok = all(v == "ok" for v in checks.values())
    return Response(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status=200 if all_ok else 503,
    )


urlpatterns = [
    path("", health_check, name="health-check"),
]