"""Status das integrações de calendário externo (card #41)."""
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care.models import ExternalCalendarToken


class CalendarIntegrationStatusView(APIView):
    """
    GET /api/v1/integrations/calendar/status/

    Diz se o usuário logado tem ao menos uma integração de calendário
    externo (Google/Outlook) conectada e ativa, e quais são.

    Consumido pelo frontend para decidir se mostra o controle "Sincronizar
    com calendário" no formulário de registro. O contrato inclui
    `providers` (e não só o booleano) para que a tela possa dizer *qual*
    calendário receberá o evento em vez de um genérico "seu calendário".
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        providers = sorted(
            ExternalCalendarToken.objects.filter(
                user=request.user, is_active=True
            )
            .values_list("provider", flat=True)
            .distinct()
        )
        return Response({
            "connected": bool(providers),
            "providers": providers,
        })
