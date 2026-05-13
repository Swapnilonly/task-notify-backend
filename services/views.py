# This should contain:
#
# Shared utilities
#
# Common reusable services
#
# Email service
#
# Background jobs
#
# But avoid duplicating app-level services.


"""
services/views.py

GET /api/dashboard/summary      — task counts + completion rate (cached)
GET /api/reports/               — filter-based task report (cached, rate-limited)
"""

import logging

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from services.dashboard_service import get_dashboard_summary, get_report_data

logger = logging.getLogger("app")


class ReportThrottle(UserRateThrottle):
    scope = "report"    # maps to "report": "20/hour" in settings


class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        summary = get_dashboard_summary(user=request.user)
        logger.info("dashboard_accessed", extra={"user_id": str(request.user.pk)})
        return Response(summary)


class ReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes   = [ReportThrottle]

    def get(self, request):
        start_date     = request.query_params.get("start_date")
        end_date       = request.query_params.get("end_date")
        assigned_to_id = request.query_params.get("user_id")

        data = get_report_data(
            user           = request.user,
            start_date     = start_date,
            end_date       = end_date,
            assigned_to_id = assigned_to_id,
        )
        logger.info(
            "report_accessed",
            extra={"user_id": str(request.user.pk), "params": request.query_params},
        )
        return Response(data)