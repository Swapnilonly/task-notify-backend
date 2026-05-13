from django.urls import path
from .views import NotificationListView, MarkNotificationReadView, MarkAllReadView, UnreadCountView

urlpatterns = [
    path("",                    NotificationListView.as_view(),       name="notification-list"),
    path("<uuid:pk>/read/",     MarkNotificationReadView.as_view(),   name="notification-read"),
    path("read-all/",           MarkAllReadView.as_view(),            name="notification-read-all"),
    path("unread-count/",       UnreadCountView.as_view(),            name="notification-unread-count"),
]