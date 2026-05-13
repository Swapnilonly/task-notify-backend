"""
notifications/views.py

GET  /api/notifications/             — paginated list (cached per user)
PUT  /api/notifications/{id}/read/   — mark single as read
POST /api/notifications/read-all/    — mark all as read
GET  /api/notifications/unread-count/— returns {"count": N} (cached 60 s)
"""

import logging

from django.core.cache import cache
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from logs.utils import log_activity

logger   = logging.getLogger("app")
CACHE_TTL = settings.CACHE_TTL


def _notif_list_key(user_id):
    return f"tnb:notif_list:{user_id}"

def _unread_count_key(user_id):
    return f"tnb:unread_count:{user_id}"

def _bust_notif_cache(user_id):
    cache.delete_many([_notif_list_key(user_id), _unread_count_key(user_id)])


class NotificationListView(generics.ListAPIView):
    serializer_class   = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        cache_key = _notif_list_key(request.user.pk)
        cached    = cache.get(cache_key)
        if cached:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=CACHE_TTL["NOTIFICATION_LIST"])
        return response


class MarkNotificationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, pk):
        try:
            notif = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        notif.is_read = True
        notif.save(update_fields=["is_read"])
        _bust_notif_cache(request.user.pk)

        log_activity(
            user          = request.user,
            action        = "notification.read",
            resource_type = "Notification",
            resource_id   = notif.pk,
            request       = request,
        )
        return Response(NotificationSerializer(notif).data)


class MarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        _bust_notif_cache(request.user.pk)
        logger.info("mark_all_read", extra={"user_id": str(request.user.pk), "count": updated})
        return Response({"marked_read": updated})


class UnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cache_key = _unread_count_key(request.user.pk)
        count     = cache.get(cache_key)
        if count is None:
            count = Notification.objects.filter(user=request.user, is_read=False).count()
            cache.set(cache_key, count, timeout=CACHE_TTL["UNREAD_COUNT"])
        return Response({"count": count})