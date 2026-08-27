"""Conexão da conta Microsoft Outlook via OAuth/MSAL (card #47).

Fluxo (espelha o do Google em `api/views/calendar_google.py`):

1. `GET /api/v1/calendar/microsoft/auth/` (autenticado) devolve a URL de
   autorização da Microsoft. O usuário vai embutido de forma assinada no
   parâmetro `state`, para podermos identificá-lo no callback -- que é uma
   requisição de navegador, sem header `Authorization`.
2. A Microsoft redireciona para
   `GET /api/v1/calendar/microsoft/callback/` com `code` + `state`.
   Trocamos o code por token (`acquire_token_by_authorization_code`) e
   salvamos em `ExternalCalendarToken` (upsert).
3. Sempre terminamos redirecionando para o deep link do app
   (`CALENDAR_INTEGRATION_DEEP_LINK`), com `?connected=microsoft` no
   sucesso ou `?error=<motivo>` na falha -- o app precisa do motivo para
   dizer ao usuário se ele deve tentar de novo ou não.

IMPORTANTE: as credenciais (MICROSOFT_CLIENT_ID/SECRET/TENANT_ID) só
existem de verdade em produção depois que alguém cadastrar o app OAuth no
Azure/Entra. Em dev/testes usamos valores fake e mockamos `msal`.
"""
import datetime
import logging
from urllib.parse import urlencode

import msal
from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from care.models import ExternalCalendarToken

logger = logging.getLogger(__name__)

MICROSOFT_SCOPES = ["Calendars.ReadWrite"]
_STATE_SALT = "api.views.calendar.microsoft-oauth-state"
_STATE_MAX_AGE = 600  # 10 minutos para completar o fluxo de login


class DeepLinkRedirect(HttpResponseRedirect):
    """Redirect que aceita o esquema de deep link do app (cuidarjuntos://).

    O HttpResponseRedirect padrão do Django só permite http/https/ftp; aqui
    o destino final é o app mobile, não um site. A URL é sempre montada a
    partir de uma setting do servidor, nunca de input do usuário, e os
    parâmetros vão url-encoded.
    """

    allowed_schemes = HttpResponseRedirect.allowed_schemes + ["cuidarjuntos"]


def _deep_link(**params):
    base = settings.CALENDAR_INTEGRATION_DEEP_LINK
    query = urlencode(params)
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{query}" if query else base


def _redirect_to_app(**params):
    return DeepLinkRedirect(_deep_link(**params))


def _microsoft_authority():
    return f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}"


def _build_msal_app():
    return msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        authority=_microsoft_authority(),
    )


def _missing_config():
    """Nomes das settings obrigatórias que estão vazias.

    Sem isso, credencial ausente em produção só aparece como um erro opaco
    da Microsoft depois do redirect -- caro de diagnosticar, e a culpa é
    nossa. Ver o equivalente em `calendar_google._missing_config`.
    """
    return [
        name
        for name in (
            "MICROSOFT_CLIENT_ID",
            "MICROSOFT_CLIENT_SECRET",
            "MICROSOFT_TENANT_ID",
            "MICROSOFT_REDIRECT_URI",
        )
        if not getattr(settings, name, "")
    ]


def _normalize_scope(result):
    """A Microsoft devolve `scope` ora como lista, ora como string."""
    scope = result.get("scope")
    if isinstance(scope, (list, tuple)):
        return " ".join(scope)
    return scope or ""


# ---------------------------------------------------------------------------
# GET /api/v1/calendar/microsoft/auth/
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def microsoft_auth(request):
    """Devolve a URL de autorização OAuth da Microsoft para o usuário logado."""
    missing = _missing_config()
    if missing:
        logger.error(
            "Integracao Microsoft Outlook nao configurada: faltam %s.",
            ", ".join(missing),
        )
        return Response(
            {"detail": "Integracao com o Outlook indisponivel."}, status=503
        )

    state = signing.dumps({"user_id": request.user.id}, salt=_STATE_SALT)

    app = _build_msal_app()
    auth_url = app.get_authorization_request_url(
        MICROSOFT_SCOPES,
        state=state,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    )

    return Response({"auth_url": auth_url})


# ---------------------------------------------------------------------------
# GET /api/v1/calendar/microsoft/callback/
# ---------------------------------------------------------------------------
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def microsoft_callback(request):
    """Recebe o redirect da Microsoft, troca o code por token e salva.

    Esta é uma requisição de navegador (sem JWT no header), então o usuário
    é recuperado a partir do `state` assinado gerado em `microsoft_auth`.
    `authentication_classes([])` evita que o SessionAuthentication do
    DEFAULT_AUTHENTICATION_CLASSES entre em jogo com um cookie de sessão
    que porventura acompanhe o redirect.
    """
    error = request.GET.get("error")
    if error:
        logger.info("Callback Microsoft com erro do provedor: %s", error)
        return _redirect_to_app(error=error)

    code = request.GET.get("code")
    state = request.GET.get("state")

    if not code or not state:
        logger.warning("Callback Microsoft sem 'code'/'state'.")
        return _redirect_to_app(error="missing_code")

    try:
        payload = signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
        user_id = payload["user_id"]
    except signing.SignatureExpired:
        logger.info("Callback Microsoft com state expirado.")
        return _redirect_to_app(error="expired_state")
    except (signing.BadSignature, KeyError, TypeError):
        logger.warning("Callback Microsoft com state invalido.")
        return _redirect_to_app(error="invalid_state")

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning("Callback Microsoft para user_id inexistente: %s", user_id)
        return _redirect_to_app(error="invalid_state")

    app = _build_msal_app()
    result = app.acquire_token_by_authorization_code(
        code,
        scopes=MICROSOFT_SCOPES,
        redirect_uri=settings.MICROSOFT_REDIRECT_URI,
    ) or {}

    access_token = result.get("access_token")
    if not access_token:
        logger.warning(
            "Falha ao trocar code por token Microsoft (usuario %s): %s",
            user_id,
            result.get("error_description", "resposta vazia"),
        )
        return _redirect_to_app(error="token_exchange_failed")

    # O usuário pode concluir o consentimento concedendo MENOS do que
    # pedimos. Sem esta checagem o vínculo é salvo como bem-sucedido, o app
    # mostra "conectado", e a falha só aparece muito depois -- num 403 ao
    # criar o evento. Escopo ausente na resposta não conta como recusa:
    # nem todo fluxo devolve `scope`.
    granted = _normalize_scope(result)
    if granted and "Calendars.ReadWrite" not in granted.split():
        logger.warning(
            "Consentimento Microsoft sem Calendars.ReadWrite (usuario %s): %r",
            user_id,
            granted,
        )
        return _redirect_to_app(error="insufficient_scope")

    expires_at = None
    expires_in = result.get("expires_in")
    if expires_in:
        expires_at = timezone.now() + datetime.timedelta(seconds=expires_in)

    id_token_claims = result.get("id_token_claims") or {}
    account_email = id_token_claims.get("preferred_username", "")

    ExternalCalendarToken.objects.update_or_create(
        user=user,
        provider=ExternalCalendarToken.Provider.MICROSOFT,
        defaults={
            "access_token": access_token,
            "refresh_token": result.get("refresh_token", ""),
            "scope": granted,
            "expires_at": expires_at,
            "account_email": account_email,
            "is_active": True,
        },
    )
    logger.info("Calendario Microsoft conectado para o usuario %s.", user_id)

    return _redirect_to_app(connected="microsoft")
