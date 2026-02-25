from django.contrib.auth.models import User
from rest_framework import serializers

from accounts.models import Profile
from care.models import GroupMembership


def _digits_only(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ["role", "full_name", "birth_date", "cpf"]
        read_only_fields = ["cpf"]


class MembershipBriefSerializer(serializers.ModelSerializer):
    group_id = serializers.IntegerField(source="group.id")
    group_name = serializers.CharField(source="group.name")
    patient_name = serializers.CharField(source="group.patient.name")

    class Meta:
        model = GroupMembership
        fields = ["group_id", "group_name", "patient_name", "relation_to_patient"]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)
    membership = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "profile", "membership"]
        read_only_fields = fields

    def get_membership(self, obj):
        try:
            mem = obj.group_membership
        except GroupMembership.DoesNotExist:
            return None
        return MembershipBriefSerializer(mem).data


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    cpf = serializers.CharField(max_length=14)
    birth_date = serializers.DateField(required=False, allow_null=True)
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        value = value.strip()
        if " " in value:
            raise serializers.ValidationError("O nome de usuario nao pode conter espacos.")
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Este nome de usuario ja esta em uso.")
        return value

    def validate_email(self, value):
        value = (value or "").lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Ja existe um usuario com este e-mail.")
        return value

    def validate_cpf(self, value):
        digits = _digits_only(value)
        if len(digits) != 11:
            raise serializers.ValidationError("CPF deve ter 11 digitos.")
        if Profile.objects.filter(cpf=digits).exists():
            raise serializers.ValidationError("Ja existe uma conta com este CPF.")
        return digits

    def create(self, validated_data):
        full_name = validated_data["full_name"].strip()
        parts = full_name.split(" ", 1)
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=parts[0],
            last_name=parts[1] if len(parts) > 1 else "",
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.full_name = full_name
        profile.birth_date = validated_data.get("birth_date")
        profile.cpf = validated_data["cpf"]
        profile.save()
        return user
