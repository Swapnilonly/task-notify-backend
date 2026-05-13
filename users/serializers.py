"""
users/serializers.py
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model  = User
        fields = ["id", "name", "email", "password", "role"]
        extra_kwargs = {"role": {"read_only": True}}   # role set internally

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["id", "name", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at", "role"]


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds user info to the login token response."""

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {
            "id":    str(self.user.pk),
            "name":  self.user.name,
            "email": self.user.email,
            "role":  self.user.role,
        }
        return data