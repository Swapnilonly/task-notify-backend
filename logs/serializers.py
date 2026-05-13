"""
logs/serializers.py
"""

from rest_framework import serializers
from .models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True, default=None)

    class Meta:
        model  = ActivityLog
        fields = [
            "id", "user_email", "action",
            "resource_type", "resource_id",
            "metadata", "ip_address", "created_at",
        ]
        read_only_fields = fields