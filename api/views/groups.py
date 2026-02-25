from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import Patient, CareGroup, GroupMembership
from api.serializers.auth import UserSerializer
from api.serializers.care import CareGroupSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_create(request):
    """Create Patient + CareGroup + Membership (replicates GroupCreateForm)."""
    data = request.data
    required = ["group_name", "patient_name", "relation_to_patient", "group_pin"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return Response(
            {"detail": f"Campos obrigatorios: {', '.join(missing)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if GroupMembership.objects.filter(user=request.user).exists():
        return Response(
            {"detail": "Voce ja esta em um grupo. Saia primeiro."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    pin = (data.get("group_pin") or "").strip()
    if not pin.isdigit() or len(pin) != 4:
        return Response(
            {"detail": "A senha do grupo deve ter exatamente 4 digitos."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with transaction.atomic():
        patient = Patient.objects.create(
            name=data["patient_name"],
            birth_date=data.get("patient_birth_date"),
            notes=data.get("health_data", ""),
            created_by=request.user,
        )
        group = CareGroup.objects.create(
            name=data["group_name"],
            patient=patient,
            created_by=request.user,
        )
        group.set_join_code(pin)
        group.save(update_fields=["join_code_hash"])

        GroupMembership.objects.create(
            user=request.user,
            group=group,
            relation_to_patient=data["relation_to_patient"],
        )

    return Response(
        CareGroupSerializer(group).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_join(request):
    """Validate PIN and create Membership (replicates GroupJoinForm)."""
    group_id = request.data.get("group_id")
    relation = request.data.get("relation_to_patient")
    pin = (request.data.get("pin") or "").strip()

    if not group_id or not relation:
        return Response(
            {"detail": "group_id e relation_to_patient sao obrigatorios."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if GroupMembership.objects.filter(user=request.user).exists():
        return Response(
            {"detail": "Voce ja esta atrelado a um grupo."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        group = CareGroup.objects.get(pk=group_id)
    except CareGroup.DoesNotExist:
        return Response({"detail": "Grupo nao encontrado."}, status=status.HTTP_404_NOT_FOUND)

    if not group.check_join_code(pin):
        return Response(
            {"detail": "Senha do grupo incorreta."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    GroupMembership.objects.create(
        user=request.user,
        group=group,
        relation_to_patient=relation,
    )

    return Response(CareGroupSerializer(group).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_leave(request):
    """Delete the user's membership."""
    try:
        mem = GroupMembership.objects.get(user=request.user)
        mem.delete()
        return Response({"detail": "Voce saiu do grupo."})
    except GroupMembership.DoesNotExist:
        return Response(
            {"detail": "Voce nao esta em nenhum grupo."},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_current(request):
    """Return the user's current group + patient info."""
    try:
        mem = GroupMembership.objects.select_related(
            "group", "group__patient"
        ).get(user=request.user)
    except GroupMembership.DoesNotExist:
        return Response({"group": None})

    return Response({
        "group": CareGroupSerializer(mem.group).data,
        "membership": {
            "relation_to_patient": mem.relation_to_patient,
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_list(request):
    """List all groups (for joining)."""
    groups = CareGroup.objects.select_related("patient").all()
    return Response(CareGroupSerializer(groups, many=True).data)
