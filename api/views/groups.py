from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from care.models import Patient, CareGroup, GroupMembership
from api.serializers.auth import UserSerializer
from api.serializers.care import CareGroupSerializer, CareGroupPublicSerializer


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

    # Política de "1 grupo por vez" na API (tarefa #38). O schema agora
    # permite N GroupMembership por usuário, mas a aplicação ainda não tem
    # o conceito de grupo ativo (cards #32/#33): todo acesso resolve para
    # `group_memberships.order_by("id").first()`, então quem entrasse num
    # segundo grupo continuaria vendo o primeiro. Até essa tela existir, a
    # API segue barrando -- e a regra passou a viver AQUI, não no banco.
    #
    # Consequência da remoção da `unique_user_one_group`: a checagem
    # `.exists()` acima é a única barreira para grupos DIFERENTES, e ela é
    # otimista -- duas requisições concorrentes passam juntas e criam dois
    # vínculos. A janela é estreita e o estado resultante é recuperável
    # (basta sair de um dos grupos), então aceitamos o risco em vez de
    # segurar um lock de escrita durante a criação de paciente + grupo.
    # Reavaliar quando o grupo ativo existir: aí o cenário deixa de ser
    # um erro e vira o comportamento normal.
    #
    # A `IntegrityError` abaixo continua sendo capturada: a constraint
    # `(user, group)` ainda barra o mesmo usuário no MESMO grupo, e sem o
    # try/except ela vazaria como 500.
    try:
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
    except IntegrityError:
        return Response(
            {"detail": "Voce ja esta em um grupo. Saia primeiro."},
            status=status.HTTP_400_BAD_REQUEST,
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

    # Mesma política de "1 grupo por vez" do group_create (tarefa #38): a
    # checagem `.exists()` acima é otimista e, sem a antiga constraint
    # `unique_user_one_group`, é a única barreira para grupos diferentes.
    # O `except IntegrityError` cobre a constraint `(user, group)`, que
    # hoje só dispara em tentativa de entrar duas vezes no MESMO grupo --
    # é justamente o caso coberto por
    # `test_concurrent_group_join_never_returns_500_and_creates_single_membership`.
    # `transaction.atomic()` aqui isola a tentativa de escrita numa
    # savepoint, então capturar a IntegrityError não deixa a transação
    # ambiente (ex.: a transação de teste) num estado inválido.
    try:
        with transaction.atomic():
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                relation_to_patient=relation,
            )
    except IntegrityError:
        return Response(
            {"detail": "Voce ja esta atrelado a um grupo."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(CareGroupSerializer(group).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def group_leave(request):
    """Delete the user's membership.

    Fallback transitorio (tarefa #38): com N grupos possiveis por
    usuario, sai do PRIMEIRO grupo (por id) -- esta API ainda so
    oferece o fluxo de "1 grupo por vez" (troca/selecao explicita de
    grupo e escopo de outra tarefa).
    """
    mem = GroupMembership.objects.filter(user=request.user).order_by("id").first()
    if mem is None:
        return Response(
            {"detail": "Voce nao esta em nenhum grupo."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    mem.delete()
    return Response({"detail": "Voce saiu do grupo."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def group_current(request):
    """Return the user's current group + patient info.

    Fallback transitorio (tarefa #38): retorna o PRIMEIRO grupo do
    usuario (por id). Ver `api.views.care._get_patient` para o
    racional completo.
    """
    mem = (
        GroupMembership.objects
        .select_related("group", "group__patient")
        .filter(user=request.user)
        .order_by("id")
        .first()
    )
    if mem is None:
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
    """List all groups (for joining).

    This endpoint is reachable by any authenticated user, including those
    who are not members of the listed groups yet (they need to browse
    groups in order to join one). It must therefore never expose
    sensitive patient data such as `Patient.notes` -- only the minimal
    fields required to identify and join a group.
    """
    groups = CareGroup.objects.select_related("patient").all()
    return Response(CareGroupPublicSerializer(groups, many=True).data)
