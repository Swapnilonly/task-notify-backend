"""
tasks/views.py — thin HTTP layer. All logic lives in core.py.
"""

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from .core import list_tasks, create_task, get_task_detail, update_task, assign_task, delete_task, send_task_creation_notification
import logging
logger = logging.getLogger("app")

class TaskListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    # read by DjangoFilterBackend / SearchFilter / OrderingFilter inside core.list_tasks
    filterset_fields = {
        "status":      ["exact"],
        "priority":    ["exact"],
        "assigned_to": ["exact"],
        "due_date":    ["gte", "lte", "date"],
    }
    search_fields   = ["title", "description"]
    ordering_fields = ["created_at", "due_date", "priority"]
    ordering        = ["-created_at"]

    def get(self, request):
        return list_tasks(request, self)

    def post(self, request):
        data, code = create_task(request)
        if code == 201:
            send_task_creation_notification(data["data"])

        return Response(data, status=code)


class TaskDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        data, code = get_task_detail(pk)
        return Response(data, status=code)

    def put(self, request, pk):
        data, code = update_task(request, pk, partial=False)
        return Response(data, status=code)

    def patch(self, request, pk):
        data, code = update_task(request, pk, partial=True)
        return Response(data, status=code)

    def delete(self, request, pk):
        data, code = delete_task(request, pk)
        return Response(data, status=code)


class AssignTaskView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        data, code = assign_task(request, pk)
        return Response(data, status=code)