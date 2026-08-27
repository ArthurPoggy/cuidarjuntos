"""Conexão da conta Google Calendar via OAuth (card #48).

Fluxo:

1. `GET /api/v1/calendar/google/auth/` (autenticado via JWT) monta a URL de
   autorização do Google (via `google_auth_oauthlib.flow.Flow`) com o escopo
   `calendar.events` e devolve `{"auth_url": "..."}`. O `state` embute o id
   do usuário logado (assinado com `django.core.signing`), pois o passo 2 é
   um redirect do navegador vindo do Google -- sem header `Authorization`.
2. `GET /api/v1/calendar/google/callback/` (público -- chamado pelo
   navegador, não pelo app) recebe `?code=...&state=...` (ou `?error=...` se
   o usuário negou o consentimento), troca o `code` por
   `access_token`/`refresh_token` e salva/atualiza um `ExternalCalendarToken`
   para o usuário identificado pelo `state`. Sempre termina redirecionando
   para o deep link do app (`CALENDAR_INTEGRATION_DEEP_LINK`), com
   `?connected=google` no sucesso ou `?error=<motivo>` na falha.

As credenciais (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`) só existem de
verdade em produção, depois que alguém criar o app OAuth no Google Cloud
Console. Em dev/teste ficam vazias/fake -- a troca de `code` por token é
sempre mockada nos testes automatizados, nunca chama a API real do Google.

Não pedimos escopo de perfil/e-mail: para criar eventos basta
`calendar.events`, e um dado pessoal a menos é um dado pessoal a menos.
Por isso `account_email` fica vazio no vínculo do Google.
"""

import logging
from datetime import timezone as dt_timezone
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from google_auth_oauthlib.flow import Flow

from care.models import ExternalCalendarToken

logger = logging.getLogger(__name__)

GOOGLE_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
_STATE_SALT = "calendar-google-oauth"
_STATE_MAX_AGE = 600  # 10 minutos para o usuário concluir o consentimento


class DeepLinkRedirect(HttpResponseRedirect):
    # O deep link do app usa o esquema custom "cuidarjuntos://", que não
    # está na allowlist padrão do Django (http/https/ftp). Redirecionar para
    # ele é seguro aqui pois a URL é sempre montada a partir de
    # CALENDAR_INTEGRATION_DEEP_LINK (config do servidor), nunca de input
    # do usuário -- os parâmetros anexados vão url-encoded.
    allowed_schemes = HttpResponseRedirect.allowed_schemes + ["cuidarjuntos"]


def _deep_link(**params):
    base = settings.CALENDAR_INTEGRATION_DEEP_LINK
    query = urlencode(params)
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{query}" if query else base


def _redirect_to_app(**params):
    return DeepLinkRedirect(_deep_link(**params))


def _google_client_config():
    return {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_CALENDAR_REDIRECT_URI],
        }
    }


def _build_flow():
    flow = Flow.from_client_config(_google_client_config(), scopes=GOOGLE_SCOPES)
    flow.redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI
    return flow


def _missing_config():
    """Nomes das settings obrigatórias que estão vazias.

    Sem isso, uma credencial ausente em produção só se manifesta como um
    `redirect_uri_mismatch` ou `invalid_client` do lado do Google -- erro
    que chega ao usuário como uma tela genérica e custa caro para
    diagnosticar. Aqui a falha é nossa, e dizemos isso no log.
    """
    return [
        name
        for name in (
            "GOOGLE_CLIENT_ID",
            "GOOGLE_CLIENT_SECRET",
            "GOOGLE_CALENDAR_REDIRECT_URI",
        )
        if not getattr(settings, name, "")
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/calendar/google/auth/
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def google_auth_url(request):
    missing = _missing_config()
    if missing:
        logger.error(
            "Integracao Google Calendar nao configurada: faltam %s.",
            ", ".join(missing),
        )
        return Response(
            {"detail": "Integracao com o Google Calendar indisponivel."},
            status=503,
        )

    state = signing.dumps({"user_id": request.user.id}, salt=_STATE_SALT)
    flow = _build_flow()
    # O segundo retorno é o state gerado pela própria lib; descartamos
    # porque passamos o nosso, que é assinado e carrega o user_id.
    auth_url, _lib_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return Response({"auth_url": auth_url})


# ---------------------------------------------------------------------------
# GET /api/v1/calendar/google/callback/
# ---------------------------------------------------------------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def google_auth_callback(request):
    error = request.query_params.get("error")
    if error:
        logger.info("Callback Google com erro do provedor: %s", error)
        return _redirect_to_app(error=error)

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        logger.warning("Callback Google sem 'code'/'state'.")
        return _redirect_to_app(error="missing_code")

    try:
        payload = signing.loads(state, salt=_STATE_SALT, max_age=_STATE_MAX_AGE)
        user_id = payload["user_id"]
    except signing.SignatureExpired:
        logger.info("Callback Google com state expirado.")
        return _redirect_to_app(error="expired_state")
    except (signing.BadSignature, KeyError, TypeError):
        logger.warning("Callback Google com state invalido.")
        return _redirect_to_app(error="invalid_state")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        logger.warning("Callback Google para user_id inexistente: %s", user_id)
        return _redirect_to_app(error="invalid_state")

    flow = _build_flow()
    try:
        flow.fetch_token(code=code)
    except Exception:
        logger.exception(
            "Falha ao trocar code por token Google para o usuario %s.", user_id
        )
        return _redirect_to_app(error="token_exchange_failed")

    credentials = flow.credentials

    # O Google só devolve refresh_token na primeira autorização. Com
    # prompt="consent" ele normalmente vem, mas se não vier gravaríamos um
    # vínculo que morre na primeira expiração -- e a renovação (card #46)
    # apaga o vínculo nesse caso, fazendo a integração sumir sozinha sem o
    # usuário entender. Melhor recusar agora, com um motivo que o app pode
    # explicar ("revogue o acesso na sua conta Google e tente de novo").
    refresh_token = credentials.refresh_token or ""
    if not refresh_token:
        existente = ExternalCalendarToken.objects.filter(
            user=user, provider=ExternalCalendarToken.Provider.GOOGLE
        ).first()
        refresh_token = existente.refresh_token if existente else ""
    if not refresh_token:
        logger.warning(
            "Google nao devolveu refresh_token para o usuario %s; "
            "vinculo nao sera salvo.",
            user_id,
        )
        return _redirect_to_app(error="no_refresh_token")

    # `credentials.expiry` vem naive e em UTC (contrato da google-auth).
    # `django.utils.timezone.utc` foi removido no Django 5.0, então usamos
    # `datetime.timezone.utc` para não travar o upgrade.
    expiry = credentials.expiry
    if expiry is not None and timezone.is_naive(expiry):
        expiry = timezone.make_aware(expiry, dt_timezone.utc)

    ExternalCalendarToken.objects.update_or_create(
        user=user,
        provider=ExternalCalendarToken.Provider.GOOGLE,
        defaults={
            "access_token": credentials.token or "",
            "refresh_token": refresh_token,
            "scope": " ".join(credentials.scopes or []),
            "expires_at": expiry,
            "is_active": True,
        },
    )
    logger.info("Calendario Google conectado para o usuario %s.", user_id)

    return _redirect_to_app(connected="google")
