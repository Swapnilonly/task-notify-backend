from django.shortcuts import render

# Create your views here.
"""
logs/views.py
GET /api/activity-logs/   — admin only, supports ?user_id=&action=&start=&end=
"""

import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics
from rest_framework.permissions import IsAdminUser

from .models import ActivityLog
from .serializers import ActivityLogSerializer

logger = logging.getLogger("app")


class ActivityLogListView(generics.ListAPIView):
    """
    Read-only list of all audit log entries.
    Access: Admin only.

    Query params:
      user_id       — filter by user pk
      action        — filter by action string (exact)
      resource_type — filter by resource type
      start         — created_at >= (ISO date)
      end           — created_at <= (ISO date)
      search        — full-text on action, resource_type
      ordering      — default: -created_at
    """

    serializer_class   = ActivityLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = {
        "user":          ["exact"],
        "action":        ["exact", "icontains"],
        "resource_type": ["exact"],
        "created_at":    ["gte", "lte", "date"],
    }
    search_fields  = ["action", "resource_type", "metadata"]
    ordering_fields = ["created_at", "action"]
    ordering        = ["-created_at"]

    def get_queryset(self):
        qs = ActivityLog.objects.select_related("user").all()

        # Optional ?start=YYYY-MM-DD &end=YYYY-MM-DD convenience params
        start = self.request.query_params.get("start")
        end   = self.request.query_params.get("end")
        if start:
            qs = qs.filter(created_at__date__gte=start)
        if end:
            qs = qs.filter(created_at__date__lte=end)

        logger.info(
            "activity_log_query",
            extra={"admin": self.request.user.email, "filters": self.request.query_params},
        )
        return qs