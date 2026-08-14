"""
tasks/serializers.py
"""

from rest_framework import serializers
from .models import Task
from users.serializers import UserProfileSerializer


class TaskSerializer(serializers.ModelSerializer):
    assigned_to_detail = UserProfileSerializer(source="assigned_to", read_only=True)
    created_by_detail  = UserProfileSerializer(source="created_by",  read_only=True)

    class Meta:
        model  = Task
        fields = [
            "id", "title", "description", "status", "priority",
            "due_date", "assigned_to", "assigned_to_detail",
            "created_by", "created_by_detail", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_assigned_to(self, user):
        if user and not user.is_active:
            raise serializers.ValidationError("Cannot assign task to inactive user.")
        return user