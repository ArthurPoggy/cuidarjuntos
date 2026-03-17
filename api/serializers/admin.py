from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Profile


class AdminUserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    group_name = serializers.SerializerMethodField()
    records_total = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "is_active", "is_staff", "is_superuser",
            "date_joined", "full_name", "role", "group_name", "records_total",
        ]
        read_only_fields = fields

    def get_role(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile:
            try:
                profile = obj.profile
            except Profile.DoesNotExist:
                return ""
        return profile.get_role_display() if profile else ""

    def get_full_name(self, obj):
        profile = getattr(obj, "profile", None)
        if not profile:
            try:
                profile = obj.profile
            except Profile.DoesNotExist:
                return obj.get_full_name()
        if profile and profile.full_name:
            return profile.full_name
        return obj.get_full_name()

    def get_group_name(self, obj):
        try:
            mem = obj.group_membership
            return mem.group.name
        except Exception:
            return ""
