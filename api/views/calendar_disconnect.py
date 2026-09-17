"""Desconexão de um calendário externo (card #44)."""
import logging

import requests
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care.models import ExternalCalendarToken

logger = logging.getLogger(__name__)

GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
REVOKE_TIMEOUT_SECONDS = 5


def _revoke_at_provider(token) -> bool:
    """Tenta revogar a autorização no provedor. Best-effort.

    Apagar o `ExternalCalendarToken` remove a credencial do nosso lado, mas
    o `refresh_token` continua válido no Google/Microsoft até o usuário
    revogar manualmente na conta dele. Como o usuário clicou em
    "desconectar" e o app responde que desconectou, deixar a autorização de
    pé contraria o que ele pediu -- e, num app de dados de saúde, o direito
    à revogação não é bem servido por um DELETE local.

    Falha aqui não impede a desconexão: o token pode já estar expirado, ou
    o provedor fora do ar. Nesses casos logamos e seguimos apagando
    localmente, mantendo a idempotência do endpoint.

    A Microsoft não expõe um endpoint equivalente de revogação por token
    (a revogação é feita pelo usuário no portal da conta), então só o
    Google é tratado aqui.
    """
    if token.provider != ExternalCalendarToken.Provider.GOOGLE:
        return False

    secret = token.refresh_token or token.access_token
    if not secret:
        return False

    try:
        response = requests.post(
            GOOGLE_REVOKE_URL,
            data={"token": secret},
            timeout=REVOKE_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.warning(
            "Falha ao revogar o token Google do usuário %s no provedor; "
            "seguindo com a remoção local.",
            token.user_id,
            exc_info=True,
        )
        return False

    return True


class CalendarDisconnectSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=ExternalCalendarToken.Provider.choices)


class CalendarDisconnectView(APIView):
    """POST /api/v1/calendar/disconnect/

    Remove a credencial (`ExternalCalendarToken`) do usuário autenticado
    para o provedor informado, tentando antes revogar a autorização no
    próprio provedor.

    Idempotente: devolve 200 tanto se havia um token quanto se não havia.
    Não remove eventos já criados no calendário externo -- apenas a
    credencial de sincronização. (Isso é intencional: apagar compromissos
    que a pessoa já viu na agenda dela seria mais surpreendente do que
    deixá-los. Quando o `event_id` dos eventos passar a ser guardado, este
    endpoint é o lugar natural para oferecer a limpeza dos futuros.)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CalendarDisconnectSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        provider = serializer.validated_data["provider"]

        token = ExternalCalendarToken.objects.filter(
            user=request.user, provider=provider
        ).first()
        if token is None:
            return Response({"disconnected": False}, status=status.HTTP_200_OK)

        revoked = _revoke_at_provider(token)
        token.delete()
        logger.info(
            "Calendario %s desconectado para o usuario %s (revogado no provedor: %s).",
            provider,
            request.user.id,
            revoked,
        )

        return Response(
            {"disconnected": True, "revoked_at_provider": revoked},
            status=status.HTTP_200_OK,
        )
