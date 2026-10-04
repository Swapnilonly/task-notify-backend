"""
tasks/core.py

Business logic layer for Task CRUD + assignment.
Views stay thin — they only extract request data and call these functions.
"""

import logging

from django.core.cache import cache
from django.conf import settings
from django.db import transaction, IntegrityError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination
from notifications.tasks import process_task_event
from .models import Task
from .serializers import TaskSerializer
from logs.utils import log_activity

logger = logging.getLogger("app")
CACHE_TTL = settings.CACHE_TTL

DETAIL_CACHE_KEY = "tnb:task_detail:{pk}"


class TaskPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


FILTER_BACKENDS = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]


def get_task_queryset(user):
    """Base queryset scoped by permission: admins see all, others see own."""
    qs = Task.objects.select_related("assigned_to", "created_by")
    if not user.is_admin:
        qs = qs.filter(assigned_to=user) | qs.filter(created_by=user)
    return qs.distinct()


def list_tasks(request, view):
    """
    Applies filter_backends + pagination.
    `view` needs: filter_backends, filterset_fields, search_fields,
    ordering_fields, ordering (read by the backends via getattr).
    """
    queryset = get_task_queryset(request.user)
    for backend in FILTER_BACKENDS:
        queryset = backend().filter_queryset(request, queryset, view)

    paginator = TaskPagination()
    page = paginator.paginate_queryset(queryset, request, view=view)
    serializer = TaskSerializer(page, many=True, context={"request": request})
    return paginator.get_paginated_response(serializer.data)


# def create_task(request):
#     """
#     Returns (response_data, http_status).
#     Raises nothing to the view — all exceptions handled here.
#     """
#     serializer = TaskSerializer(data=request.data, context={"request": request})
#     if not serializer.is_valid():
#         return {"errors": serializer.errors}, 400
#
#     try:
#         with transaction.atomic():
#             task = serializer.save(created_by=request.user)
#             logger.info(f"Task created: {task.id} by {request.user.email}")
#         return {"status": True, "message": "Task created successfully.", "data": serializer.data}, 201
#
#     except Exception as e:
#         logger.error(f"Task creation failed: {e}")
#         return {"status": False, "error": "Task creation failed. Please try again."}, 500


def create_task(request) -> tuple[dict, int]:
    """
    Returns (response_data, http_status).
    Raises nothing to the view — all exceptions handled here.
    Idempotent: a repeated request with the same Idempotency-Key header
    returns the original task (200) instead of creating a duplicate (201).
    """
    idempotency_key = request.headers.get("Idempotency-Key")

    if idempotency_key:
        existing_task = Task.objects.filter(idempotency_key=idempotency_key).first()
        if existing_task is not None:
            return _existing_task_response(existing_task), 200

    serializer = TaskSerializer(data=request.data, context={"request": request})
    if not serializer.is_valid():
        return {"errors": serializer.errors}, 400

    try:
        with transaction.atomic():
            task = serializer.save(created_by=request.user, idempotency_key=idempotency_key)
        logger.info(f"Task created: {task.id} by {request.user.email}")
        return {"status": True, "message": "Task created successfully.", "data": TaskSerializer(task).data}, 201

    except IntegrityError:
        # A concurrent request with the same key won the insert race.
        existing_task = Task.objects.filter(idempotency_key=idempotency_key).first()
        if existing_task is not None:
            logger.info(f"Duplicate task creation avoided for idempotency_key={idempotency_key}")
            return _existing_task_response(existing_task), 200
        logger.error(f"Task creation integrity error for key={idempotency_key}", exc_info=True)
        return {"status": False, "error": "Task creation failed due to a data conflict."}, 500

    except Exception as e:
        logger.error(f"Unexpected error creating task: {e}", exc_info=True)
        raise


def _existing_task_response(task: Task) -> dict:
    """Build the response body for a replayed (already-created) task."""
    return {"status": True, "message": "Task already exists.", "data": TaskSerializer(task).data}


def get_task_detail(pk):
    cache_key = DETAIL_CACHE_KEY.format(pk=pk)
    try:
        cached = cache.get(cache_key)
        if cached:
            logger.debug("task_cache_hit", extra={"key": cache_key})
            return cached, 200

        task = Task.objects.select_related("assigned_to", "created_by").filter(pk=pk).first()
        if task is None:
            return {"error": "Task not found."}, 404

        serializer = TaskSerializer(task)
        cache.set(cache_key, serializer.data, timeout=CACHE_TTL["USER_PROFILE"])
        return serializer.data, 200

    except Exception as e:
        logger.error(f"Task detail fetch failed for pk={pk}: {e}")
        return {"error": "Could not fetch task. Please try again."}, 500


def update_task(request, pk, partial):
    task = Task.objects.select_related("assigned_to", "created_by").filter(pk=pk).first()
    if task is None:
        return {"error": "Task not found."}, 404

    serializer = TaskSerializer(task, data=request.data, partial=partial)
    if not serializer.is_valid():
        return {"errors": serializer.errors}, 400

    old_status = task.status

    try:
        with transaction.atomic():
            task = serializer.save()
            new_status = task.status

            if old_status != new_status:
                log_activity(
                    user          = request.user,
                    action        = "task.status_changed",
                    resource_type = "Task",
                    resource_id   = task.pk,
                    metadata      = {"old": old_status, "new": new_status},
                    request       = request,
                )

            cache.delete(DETAIL_CACHE_KEY.format(pk=pk))
            logger.info(f"Task updated: {task.id} by {request.user.email}")

        if old_status != task.status and task.status == Task.Status.COMPLETED and task.assigned_to:
            from notifications.tasks import send_notification_task
            send_notification_task.delay(
                user_id    = task.assigned_to.pk,
                message    = f"Task '{task.title}' has been marked as completed.",
                notif_type = "task",
            )

        return {"message": "Task updated successfully.", "task": serializer.data}, 200

    except Exception as e:
        logger.error(f"Task update failed for pk={pk}: {e}")
        return {"error": "Task update failed. Please try again."}, 500


def delete_task(request, pk):
    task = Task.objects.filter(pk=pk).first()
    if task is None:
        return {"error": "Task not found."}, 404

    try:
        with transaction.atomic():
            task.delete()
            cache.delete(DETAIL_CACHE_KEY.format(pk=pk))
            logger.info(f"Task deleted: {pk} by {request.user.email}")
        return None, 204

    except Exception as e:
        logger.error(f"Task deletion failed for pk={pk}: {e}")
        return {"error": "Task deletion failed. Please try again."}, 500


def assign_task(request, pk):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    task = Task.objects.filter(pk=pk).first()
    if task is None:
        return {"error": "Task not found."}, 404

    assigned_to_id = request.data.get("assigned_to")
    if not assigned_to_id:
        return {"error": "assigned_to is required."}, 400

    try:
        with transaction.atomic():
            user = User.objects.filter(pk=assigned_to_id, is_active=True).first()
            if user is None:
                return {"error": "User not found or inactive."}, 400

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

            cache.delete(DETAIL_CACHE_KEY.format(pk=pk))
            logger.info(f"Task {task.id} assigned to {user.email} by {request.user.email}")

        from notifications.tasks import send_notification_task
        send_notification_task.delay(
            user_id    = user.pk,
            message    = f"You have been assigned task: '{task.title}'.",
            notif_type = "task",
        )

        return {"message": "Task assigned successfully.", "task": TaskSerializer(task).data}, 200

    except Exception as e:
        logger.error(f"Task assignment failed for pk={pk}: {e}")
        return {"error": "Task assignment failed. Please try again."}, 500

def send_task_creation_notification(data):
    try:
        title = data["title"]
        user_id = data["assigned_to"]
        task_id = data["id"]
        process_task_event.delay(task_id=task_id, event_type="CREATED")
        logger.info(
            "task_assigned_notification_queued",
            extra={"task_id": str(data["id"]), "user_id": str(user_id)},
        )
    except Exception as e:
        logger.info(
            "Task creation notification failed",
            extra={"task_id": str(data["id"]), "user_id": str(data["assigned_to"])},
        )