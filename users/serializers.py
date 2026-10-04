"""
users/serializers.py
"""
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Role, UserRole
from django.contrib.auth.password_validation import validate_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'name', 'password', 'confirm_password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already registered.")
        return value.lower().strip()

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        return user

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds user info + roles + permissions to the login response."""

    def validate(self, attrs):
        data = super().validate(attrs)

        user  = self.user
        roles = user.get_role_names()

        from users.permissions import get_user_permissions
        perms = sorted(get_user_permissions(user))

        data["user"] = {
            "id"          : str(user.pk),
            "name"        : user.name,
            "email"       : user.email,
            "roles"       : roles,
            "permissions" : perms,
        }
        return data


class UserProfileSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ["id", "name", "email", "roles", "is_active", "created_at"]

    def get_roles(self, obj):
        return obj.get_role_names()


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True, read_only=True, slug_field="codename"
    )

    class Meta:
        model  = Role
        fields = ["id", "name", "description", "permissions"]


class AssignRoleSerializer(serializers.Serializer):
    user_id = serializers.UUIDField()
    role_id = serializers.IntegerField()

    def validate_role_id(self, value):
        if not Role.objects.filter(id=value).exists():
            raise serializers.ValidationError("Role not found.")
        return value

    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User not found.")
        return value


class CheckRoleSerializer(serializers.Serializer):
    role_id = serializers.IntegerField()
