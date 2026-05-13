"""
config/urls.py  — Master URL configuration
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.views import RegisterView, ProfileView, LogoutView

urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path("api/auth/register", RegisterView.as_view(),     name="register"),
    path("api/auth/login",    TokenObtainPairView.as_view(), name="login"),
    path("api/auth/refresh",  TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout",   LogoutView.as_view(),       name="logout"),
    path("api/auth/me",       ProfileView.as_view(),      name="profile"),

    # ── Tasks ─────────────────────────────────────────────────────────────────
    path("api/tasks/",       include("tasks.urls")),

    # ── Notifications ─────────────────────────────────────────────────────────
    path("api/notifications/", include("notifications.urls")),

    # ── Dashboard + Reports ───────────────────────────────────────────────────
    path("api/dashboard/", include("services.dashboard_urls")),
    path("api/reports/",   include("services.report_urls")),

    # ── Audit Logs ────────────────────────────────────────────────────────────
    path("api/activity-logs/", include("logs.urls")),

    # ── Health check ──────────────────────────────────────────────────────────
    path("health/", include("utils.health_urls")),
]