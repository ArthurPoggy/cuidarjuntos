from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Profile
from care.models import CareRecord


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
        # Fallback transitorio (tarefa #38): primeiro grupo do usuario.
        # Ver `api.views.care._get_patient` para o racional completo.
        try:
            memberships = sorted(obj.group_memberships.all(), key=lambda m: m.id)
            return memberships[0].group.name if memberships else ""
        except Exception:
            return ""


class AdminRecordSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_type_display", read_only=True)
    patient = serializers.CharField(source="patient.name", read_only=True)
    group = serializers.SerializerMethodField()
    author_name = serializers.CharField(read_only=True)

    class Meta:
        model = CareRecord
        fields = [
            "id", "type", "label", "status", "date", "time",
            "patient", "group", "caregiver", "author_name",
        ]
        read_only_fields = fields

    def get_group(self, obj):
        group = getattr(obj.patient, "care_group", None)
        return group.name if group else ""
