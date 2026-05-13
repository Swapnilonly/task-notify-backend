"""
users/views.py
POST /api/auth/register  — public
GET  /api/auth/me        — authenticated
PUT  /api/auth/me        — authenticated
POST /api/auth/logout    — blacklists refresh token
"""

import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import AnonRateThrottle

from .models import User
from .serializers import RegisterSerializer, UserSerializer
from logs.utils import log_activity

logger = logging.getLogger("app")


class AuthRateThrottle(AnonRateThrottle):
    rate = "10/minute"


class RegisterView(generics.CreateAPIView):
    serializer_class   = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes   = [AuthRateThrottle]

    def perform_create(self, serializer):
        user = serializer.save()
        log_activity(
            user          = user,
            action        = "user.registered",
            resource_type = "User",
            resource_id   = user.pk,
            metadata      = {"email": user.email, "name": user.name},
            request       = self.request,
        )
        logger.info("new_user_registered", extra={"user_id": str(user.pk), "email": user.email})


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class   = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        serializer.save()
        log_activity(
            user          = self.request.user,
            action        = "user.updated",
            resource_type = "User",
            resource_id   = self.request.user.pk,
            metadata      = serializer.validated_data,
            request       = self.request,
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            log_activity(
                user    = request.user,
                action  = "user.logout",
                request = request,
            )
            return Response({"detail": "Logged out successfully."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as exc:
            logger.warning("logout_failed", extra={"error": str(exc), "user": str(request.user.pk)})
            return Response({"detail": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)