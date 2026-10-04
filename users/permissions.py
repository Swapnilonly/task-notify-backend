"""
users/permissions.py — RBAC permission utilities + DRF permission classes.
"""

from django.core.cache import cache
from rest_framework.permissions import BasePermission

from .models import Permission, UserRole
from .constant import PERMISSION_CACHE_TTL



# ─────────────────────────────────────────────
# Cache Helpers
# ─────────────────────────────────────────────

def _cache_key(user_id):
    return f"user_perms:{user_id}"


def get_user_permissions(user) -> set:
    """
    Returns flat set of permission codenames for the user.
    Redis-cached for 5 minutes to avoid repeated DB joins.
    """
    cache_key = _cache_key(user.id)
    cached    = cache.get(cache_key)
    if cached is not None:
        return set(cached)

    perms = list(
        Permission.objects.filter(
            roles__user_roles__user=user
        ).values_list("codename", flat=True).distinct()
    )
    cache.set(cache_key, perms, PERMISSION_CACHE_TTL)
    return set(perms)


def invalidate_user_permission_cache(user_id):
    """Call this whenever a role is assigned or removed."""
    cache.delete(_cache_key(user_id))


def user_has_permission(user, codename: str) -> bool:
    return codename in get_user_permissions(user)


def user_has_role_id(user, role_id: int) -> bool:
    return UserRole.objects.filter(user=user, role__id=role_id).exists()


# ─────────────────────────────────────────────
# DRF Permission Classes
# ─────────────────────────────────────────────

class HasPerm(BasePermission):
    """
    Check permission by codename.

    Usage:
        class MyView(APIView):
            permission_classes    = [IsAuthenticated, HasPerm]
            required_permission   = "task:delete"
    """
    def has_permission(self, request, view):
        perm = getattr(view, "required_permission", None)
        if not perm:
            return True
        return user_has_permission(request.user, perm)


class HasRoleId(BasePermission):
    """
    Check permission by role ID.

    Usage:
        class MyView(APIView):
            permission_classes = [IsAuthenticated, HasRoleId]
            required_role_id   = 1
    """
    def has_permission(self, request, view):
        role_id = getattr(view, "required_role_id", None)
        if not role_id:
            return True
        return user_has_role_id(request.user, role_id)


class IsAdminRole(BasePermission):
    """Shortcut — only users with 'admin' role pass."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin