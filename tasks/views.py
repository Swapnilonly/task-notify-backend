"""
tasks/views.py

CRUD + filters + Redis cache + audit logging.

GET  /api/tasks/              — list (paginated, filterable)
POST /api/tasks/              — create
GET  /api/tasks/{id}/         — retrieve (cached)
PUT  /api/tasks/{id}/         — update
PATCH /api/tasks/{id}/        — partial update
DELETE /api/tasks/{id}/       — delete
PATCH /api/tasks/{id}/assign/ — assign to user
"""

import logging

from django.core.cache import cache
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Task
from .serializers import TaskSerializer
from logs.utils import log_activity

logger = logging.getLogger("app")

CACHE_TTL = settings.CACHE_TTL


class TaskListCreateView(generics.ListCreateAPIView):
    serializer_class   = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = {
        "status":      ["exact"],
        "priority":    ["exact"],
        "assigned_to": ["exact"],
        "due_date":    ["gte", "lte", "date"],
    }
    search_fields  = ["title", "description"]
    ordering_fields = ["created_at", "due_date", "priority"]
    ordering        = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        qs   = Task.objects.select_related("assigned_to", "created_by")
        # Regular users only see their own tasks; admins see all
        if not user.is_admin:
            qs = qs.filter(assigned_to=user) | qs.filter(created_by=user)
        return qs.distinct()

    def perform_create(self, serializer):
        # audit + cache busting are handled by Task post_save signal
        serializer.save(created_by=self.request.user)


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class   = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Task.objects.select_related("assigned_to", "created_by")

    def retrieve(self, request, *args, **kwargs):
        cache_key = f"tnb:task_detail:{kwargs['pk']}"
        cached    = cache.get(cache_key)
        if cached:
            logger.debug("task_cache_hit", extra={"key": cache_key})
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=CACHE_TTL["USER_PROFILE"])
        return response

    def perform_update(self, serializer):
        old_status = serializer.instance.status
        task       = serializer.save()
        new_status = task.status

        if old_status != new_status:
            log_activity(
                user          = self.request.user,
                action        = "task.status_changed",
                resource_type = "Task",
                resource_id   = task.pk,
                metadata      = {"old": old_status, "new": new_status},
                request       = self.request,
            )
            # Notify assignee on completion
            if new_status == Task.Status.COMPLETED and task.assigned_to:
                from notifications.tasks import send_notification_task
                send_notification_task.delay(
                    user_id    = task.assigned_to.pk,
                    message    = f"Task '{task.title}' has been marked as completed.",
                    notif_type = "task",
                )

    def perform_destroy(self, instance):
        # audit is handled by Task post_delete signal
        instance.delete()


class AssignTaskView(APIView):
    """PATCH /api/tasks/{pk}/assign/  body: {"assigned_to": <user_id>}"""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return Response({"detail": "Task not found."}, status=status.HTTP_404_NOT_FOUND)

        assigned_to_id = request.data.get("assigned_to")
        if not assigned_to_id:
            return Response({"detail": "assigned_to is required."}, status=status.HTTP_400_BAD_REQUEST)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(pk=assigned_to_id, is_active=True)
        except User.DoesNotExist:
            return Response({"detail": "User not found or inactive."}, status=status.HTTP_400_BAD_REQUEST)

        old_assignee = str(task.assigned_to_id) if task.assigned_to_id else None
        task.assigned_to = user
        task.save(update_fields=["assigned_to"])

        log_activity(
            user          = request.user,
            action        = "task.assigned",
            resource_type = "Task",
            resource_id   = task.pk,
            metadata      = {"old_assignee": old_assignee, "new_assignee": str(user.pk)},
            request       = request,
        )

        from notifications.tasks import send_notification_task
        send_notification_task.delay(
            user_id    = user.pk,
            message    = f"You have been assigned task: '{task.title}'.",
            notif_type = "task",
        )

        return Response(TaskSerializer(task).data)