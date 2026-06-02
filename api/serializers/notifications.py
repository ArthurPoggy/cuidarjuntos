from rest_framework import serializers

from care.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "title", "body", "data", "read", "created_at"]
        read_only_fields = ["id", "title", "body", "data", "created_at"]
