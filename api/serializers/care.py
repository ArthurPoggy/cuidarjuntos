from django.db.models import Sum, F, Q, Value, IntegerField, OuterRef, Subquery, Count
from django.db.models.functions import Coalesce
from rest_framework import serializers

from care.models import (
    Patient,
    CareGroup,
    GroupMembership,
    Medication,
    MedicationStockEntry,
    CareRecord,
    RecordReaction,
    RecordComment,
)


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = ["id", "name", "birth_date", "notes"]
        read_only_fields = ["id"]


class CareGroupSerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = CareGroup
        fields = ["id", "name", "patient", "member_count", "created_at"]
        read_only_fields = fields

    def get_member_count(self, obj):
        return obj.members.count()


class GroupMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "username", "group_name", "relation_to_patient"]
        read_only_fields = fields


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = ["id", "name", "dosage", "created_at"]
        read_only_fields = ["id", "created_at"]


class MedicationStockEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicationStockEntry
        fields = ["id", "medication", "quantity", "created_at"]
        read_only_fields = ["id", "created_at"]


class MedicationWithStockSerializer(serializers.ModelSerializer):
    current_stock = serializers.IntegerField(read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = Medication
        fields = ["id", "name", "dosage", "created_at", "current_stock", "status"]
        read_only_fields = fields

    def get_status(self, obj):
        stock = getattr(obj, "current_stock", 0) or 0
        if stock <= 0:
            return "danger"
        if stock <= 5:
            return "warn"
        return "ok"


class SocialSummarySerializer(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    user_reaction = serializers.CharField(allow_blank=True)
    comments_count = serializers.IntegerField()


class RecordReactionSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = RecordReaction
        fields = ["id", "reaction", "username", "created_at"]
        read_only_fields = fields


class RecordCommentSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()

    class Meta:
        model = RecordComment
        fields = ["id", "text", "author", "created_at"]
        read_only_fields = ["id", "author", "created_at"]

    def get_author(self, obj):
        user = obj.user
        profile = getattr(user, "profile", None)
        if profile and profile.full_name:
            return profile.full_name
        full = (user.get_full_name() or "").strip()
        return full or user.username


class CareRecordSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(read_only=True)
    medication_detail = serializers.CharField(read_only=True)
    is_from_series = serializers.BooleanField(read_only=True)
    social = serializers.SerializerMethodField()

    # Write fields for type-specific data
    medication_id = serializers.IntegerField(
        write_only=True, required=False, allow_null=True,
    )
    # Sub-fields for composing `what` (write-only)
    vital_kind = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vital_status = serializers.CharField(write_only=True, required=False, allow_blank=True)
    bathroom_type = serializers.CharField(write_only=True, required=False, allow_blank=True)
    bathroom_no_occurrence = serializers.BooleanField(write_only=True, required=False, default=False)
    meal_type = serializers.CharField(write_only=True, required=False, allow_blank=True)
    meal_acceptance = serializers.CharField(write_only=True, required=False, allow_blank=True)
    sleep_event = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = CareRecord
        fields = [
            "id", "patient", "type", "what", "description",
            "medication", "capsule_quantity",
            "progress_trend", "missed_reason",
            "is_exception", "date", "time",
            "recurrence", "repeat_until",
            "status", "caregiver", "created_by",
            "timestamp", "recurrence_group",
            # computed
            "author_name", "medication_detail", "is_from_series", "social",
            # write-only sub-fields
            "medication_id",
            "vital_kind", "vital_status",
            "bathroom_type", "bathroom_no_occurrence",
            "meal_type", "meal_acceptance",
            "sleep_event",
        ]
        read_only_fields = [
            "id", "timestamp", "recurrence_group", "created_by", "caregiver",
            "author_name", "medication_detail", "is_from_series", "social",
            "patient",
        ]

    def get_social(self, obj):
        request = self.context.get("request")
        user = request.user if request else None
        record_id = obj.pk
        if not record_id:
            return {"counts": {}, "user_reaction": "", "comments_count": 0}

        counts = {}
        for row in (
            RecordReaction.objects
            .filter(record_id=record_id)
            .values("reaction")
            .annotate(total=Count("id"))
        ):
            counts[row["reaction"]] = row["total"]

        user_reaction = ""
        if user and user.is_authenticated:
            ur = RecordReaction.objects.filter(record_id=record_id, user=user).first()
            if ur:
                user_reaction = ur.reaction

        comments_count = RecordComment.objects.filter(record_id=record_id).count()

        return {
            "counts": counts,
            "user_reaction": user_reaction,
            "comments_count": comments_count,
        }

    def _compose_what(self, validated_data, record_type):
        """Build the `what` field from sub-fields based on record type."""
        if record_type == CareRecord.Type.VITAL:
            kind = validated_data.pop("vital_kind", "") or ""
            status = validated_data.pop("vital_status", "") or ""
            if kind and status:
                return f"{kind} \u2022 {status}"
            return kind or status or ""

        if record_type == CareRecord.Type.BATHROOM:
            validated_data.pop("vital_kind", None)
            validated_data.pop("vital_status", None)
            no_occ = validated_data.pop("bathroom_no_occurrence", False)
            if no_occ:
                validated_data.pop("bathroom_type", None)
                return "Sem ocorrencia"
            return validated_data.pop("bathroom_type", "") or ""

        if record_type == CareRecord.Type.MEAL:
            meal = validated_data.pop("meal_type", "") or ""
            acceptance = validated_data.pop("meal_acceptance", "") or ""
            if meal and acceptance:
                return f"{meal} \u2022 {acceptance}"
            return meal or acceptance or ""

        if record_type == CareRecord.Type.SLEEP:
            return validated_data.pop("sleep_event", "") or ""

        if record_type == CareRecord.Type.PROGRESS:
            # what is empty for progress, description carries the text
            return ""

        # Clean up unused sub-fields
        for key in ("vital_kind", "vital_status", "bathroom_type",
                     "bathroom_no_occurrence", "meal_type", "meal_acceptance", "sleep_event"):
            validated_data.pop(key, None)

        return validated_data.get("what", "")

    def _resolve_medication(self, validated_data, record_type):
        med_id = validated_data.pop("medication_id", None)
        if record_type == CareRecord.Type.MEDICATION and med_id:
            try:
                return Medication.objects.get(pk=med_id)
            except Medication.DoesNotExist:
                pass
        return None

    def create(self, validated_data):
        record_type = validated_data.get("type", CareRecord.Type.OTHER)
        medication = self._resolve_medication(validated_data, record_type)

        what = self._compose_what(validated_data, record_type)
        if record_type == CareRecord.Type.MEDICATION and medication:
            what = str(medication).strip()
        elif record_type == CareRecord.Type.MEDICATION:
            what = validated_data.get("what", what)

        validated_data["what"] = what
        validated_data["medication"] = medication

        if record_type != CareRecord.Type.MEDICATION:
            validated_data["medication"] = None
            validated_data["capsule_quantity"] = None

        if record_type != CareRecord.Type.PROGRESS:
            validated_data["progress_trend"] = ""

        return super().create(validated_data)

    def update(self, instance, validated_data):
        record_type = validated_data.get("type", instance.type)
        medication = self._resolve_medication(validated_data, record_type)

        if any(k in validated_data for k in ("vital_kind", "vital_status", "bathroom_type",
                                              "bathroom_no_occurrence", "meal_type",
                                              "meal_acceptance", "sleep_event")):
            what = self._compose_what(validated_data, record_type)
            if record_type == CareRecord.Type.MEDICATION and medication:
                what = str(medication).strip()
            validated_data["what"] = what

        if medication is not None:
            validated_data["medication"] = medication
        elif record_type != CareRecord.Type.MEDICATION:
            validated_data["medication"] = None
            validated_data["capsule_quantity"] = None

        if record_type != CareRecord.Type.PROGRESS:
            validated_data["progress_trend"] = ""

        return super().update(instance, validated_data)
