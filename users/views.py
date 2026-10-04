"""
users/views.py — All auth + RBAC endpoints using APIView.
"""

import logging
from django.db import transaction
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from .core import send_welcome_notification
from .models import Role, UserRole
from .serializers import (RegisterSerializer, UserProfileSerializer, RoleSerializer, AssignRoleSerializer)
from .permissions import (HasPerm, IsAdminRole, invalidate_user_permission_cache, get_user_permissions, user_has_role_id)
from .constant import DEFAULT_ROLE
User   = get_user_model()
logger = logging.getLogger("app")


# ─────────────────────────────────────────────
# Auth Endpoints
# ─────────────────────────────────────────────

class RegisterView(APIView):
    """
    POST /api/auth/register/
    Public endpoint. Creates user, assigns default 'member' role,
    fires welcome notification via Celery, returns JWT tokens.
    """
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():

                user = serializer.save()
                default_role = Role.objects.get(name=DEFAULT_ROLE)
                UserRole.objects.create(
                    user        = user,
                    role        = default_role,
                    assigned_by = None
                )

                invalidate_user_permission_cache(user.id)
                refresh = RefreshToken.for_user(user)
                logger.info(f"New user registered: {user.email} | role: {DEFAULT_ROLE}")
            transaction.on_commit(lambda: send_welcome_notification(user.id))

            return Response({
                    "message" : "Registration successful.",
                    "user"    : {
                        "id"    : str(user.id),
                        "name"  : user.name,
                        "email" : user.email,
                        "role"  : default_role.name,
                        "role_id": default_role.id,
                    },
                    "tokens"  : {
                        "access"  : str(refresh.access_token),
                        "refresh" : str(refresh),
                    }
                }, status=status.HTTP_201_CREATED)

        except Role.DoesNotExist:
            logger.error("Default role 'member' missing. Run: python manage.py seed_roles")
            return Response(
                {"error": "System configuration error. Contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            return Response(
                {"error": "Registration failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully."})
        except TokenError:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )


# ─────────────────────────────────────────────
# User Profile
# ─────────────────────────────────────────────

class UserProfileView(APIView):
    """
    GET  /api/users/me/        — get own profile
    PUT  /api/users/me/        — update name only
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        name = request.data.get("name", "").strip()
        if not name:
            return Response(
                {"error": "Name cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.name = name
        user.save(update_fields=["name", "updated_at"])
        return Response({"message": "Profile updated.", "name": user.name})


# ─────────────────────────────────────────────
# Role Check Endpoints
# ─────────────────────────────────────────────

class CheckUserRoleByIdView(APIView):
    """
    GET /api/users/check-role/<int:role_id>/
    Returns whether the current user has this role + its permissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, role_id):
        try:
            user_role = UserRole.objects.select_related("role").get(
                user    = request.user,
                role__id = role_id
            )
            perms = list(
                user_role.role.permissions.values_list("codename", flat=True)
            )
            return Response({
                "has_role"    : True,
                "role_id"     : role_id,
                "role_name"   : user_role.role.name,
                "permissions" : perms,
            })
        except UserRole.DoesNotExist:
            return Response({
                "has_role"    : False,
                "role_id"     : role_id,
                "role_name"   : None,
                "permissions" : [],
            })


class MyPermissionsView(APIView):
    """
    GET /api/users/my-permissions/
    Returns all permissions of the current user across all roles.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        perms = get_user_permissions(request.user)
        roles = request.user.get_role_names()
        return Response({
            "roles"       : roles,
            "permissions" : sorted(perms),
        })


# ─────────────────────────────────────────────
# Admin — Role Management
# ─────────────────────────────────────────────

class RoleListView(APIView):
    """
    GET /api/admin/roles/
    Returns all roles with their permissions.
    Admin only.
    """
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        roles      = Role.objects.prefetch_related("permissions").all()
        serializer = RoleSerializer(roles, many=True)
        return Response(serializer.data)


class AssignRoleView(APIView):
    """
    POST /api/admin/assign-role/
    Admin assigns a role to any user.
    Replaces existing roles (single-role model).

    Body: { "user_id": "<uuid>", "role_id": <int> }
    """
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = "user:manage"

    def post(self, request):
        serializer = AssignRoleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = serializer.validated_data["user_id"]
        role_id = serializer.validated_data["role_id"]

        target_user = User.objects.get(id=user_id)
        new_role    = Role.objects.get(id=role_id)

        with transaction.atomic():
            # Remove existing roles then assign new one
            UserRole.objects.filter(user=target_user).delete()
            UserRole.objects.create(
                user        = target_user,
                role        = new_role,
                assigned_by = request.user
            )
        transaction.on_commit(
            lambda: invalidate_user_permission_cache(target_user.id)
        )

        logger.info(
            f"Role changed --> user: {target_user.email} | "
            f"new role: {new_role.name} | by: {request.user.email}"
        )

        return Response({
            "message"  : f"Role '{new_role.name}' assigned successfully.",
            "user_id"  : str(target_user.id),
            "role"     : new_role.name,
            "role_id"  : new_role.id,
        })


class RemoveRoleView(APIView):
    """
    DELETE /api/admin/remove-role/
    Admin removes a specific role from a user.

    Body: { "user_id": "<uuid>", "role_id": <int> }
    """
    permission_classes = [IsAuthenticated, HasPerm]
    required_permission = "user:manage"

    def delete(self, request):
        user_id = request.data.get("user_id")
        role_id = request.data.get("role_id")

        if not user_id or not role_id:
            return Response(
                {"error": "user_id and role_id are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted, _ = UserRole.objects.filter(
            user__id = user_id,
            role__id = role_id
        ).delete()

        if not deleted:
            return Response(
                {"error": "Role assignment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        invalidate_user_permission_cache(user_id)

        return Response({"message": "Role removed successfully."})

class CustomLoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer