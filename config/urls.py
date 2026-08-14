"""
config/urls.py  — Master URL configuration
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from users.views import (
    RegisterView,
    LogoutView,
    UserProfileView,
    CheckUserRoleByIdView,
    MyPermissionsView,
    RoleListView,
    AssignRoleView,
    RemoveRoleView,
    CustomLoginView
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Auth ──────────────────────────────────────────────────────────────────
    path("api/auth/register/", RegisterView.as_view(),     name="register"),
    path("api/auth/login/",       CustomLoginView.as_view(), name="login"),
    path("api/auth/refresh/",  TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout/",   LogoutView.as_view(),       name="logout"),
    path("api/auth/me/",       UserProfileView.as_view(),      name="profile"),
    path("api/users/my-permissions/", MyPermissionsView.as_view(), name="my-permissions"),
    path("api/users/check-role/<int:role_id>/", CheckUserRoleByIdView.as_view(), name="check-role"),

    # ── Admin ─────────────────────────────────────────
    path("api/admin/roles/", RoleListView.as_view(), name="role-list"),
    path("api/admin/assign-role/", AssignRoleView.as_view(), name="assign-role"),
    path("api/admin/remove-role/", RemoveRoleView.as_view(), name="remove-role"),

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
    path("api/health/", include("utils.health_urls")),
]