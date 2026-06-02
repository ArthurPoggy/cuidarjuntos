from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care.models import PushToken


class PushTokenSerializer(serializers.ModelSerializer):
    # Remove o UniqueValidator automático do token para permitir upsert na view.
    token = serializers.CharField(max_length=512)

    class Meta:
        model = PushToken
        fields = ["id", "token", "platform", "created_at", "last_used_at", "is_active"]
        read_only_fields = ["id", "created_at", "last_used_at", "is_active"]

    def validate_token(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Token não pode ser vazio.")
        return value

    def validate_platform(self, value):
        valid = {c[0] for c in PushToken.Platform.choices}
        if value not in valid:
            raise serializers.ValidationError(f"Plataforma inválida. Use: {', '.join(sorted(valid))}.")
        return value


class PushTokenView(APIView):
    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------
    # POST /api/v1/push-tokens/
    # Upsert para o próprio usuário: cria ou reativa um token. Se o token
    # já existir vinculado a outro usuário, retorna 409 — a transferência
    # de token entre contas não é permitida automaticamente.
    # ------------------------------------------------------------------
    def post(self, request):
        serializer = PushTokenSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token_str = serializer.validated_data["token"]
        platform  = serializer.validated_data["platform"]

        with transaction.atomic():
            existing = (
                PushToken.objects
                .select_for_update()
                .filter(token=token_str)
                .first()
            )
            if existing and existing.user_id != request.user.id:
                return Response(
                    {"detail": "Este token já está registrado para outro usuário."},
                    status=status.HTTP_409_CONFLICT,
                )

            push_token, created = PushToken.objects.update_or_create(
                token=token_str,
                defaults={
                    "user": request.user,
                    "platform": platform,
                    "deleted_at": None,
                    "deleted_by": None,
                    "last_used_at": timezone.now(),
                },
            )

        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(PushTokenSerializer(push_token).data, status=http_status)

    # ------------------------------------------------------------------
    # DELETE /api/v1/push-tokens/
    # Soft delete: registra deleted_at e deleted_by sem remover do banco.
    # Body: { "token": "<token_string>" }
    # ------------------------------------------------------------------
    def delete(self, request):
        token_str = (request.data.get("token") or "").strip()
        if not token_str:
            return Response(
                {"detail": "Campo 'token' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            push_token = PushToken.objects.get(token=token_str, user=request.user)
        except PushToken.DoesNotExist:
            return Response(
                {"detail": "Token não encontrado para este usuário."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if push_token.deleted_at is not None:
            return Response(
                {"detail": "Token já foi removido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        push_token.deleted_at = timezone.now()
        push_token.deleted_by = request.user
        push_token.save(update_fields=["deleted_at", "deleted_by"])

        return Response(status=status.HTTP_204_NO_CONTENT)
