"""Sincronização de `CareRecord`s com calendários externos (card #46).

Cria um evento no Google Calendar / Microsoft Outlook a partir de um
`CareRecord`, usando as credenciais salvas em `ExternalCalendarToken`
(model do card #49).

Funções expostas:

- `sync_record_to_google(record, user)` / `sync_record_to_microsoft(...)`:
  criam o evento no provedor correspondente, renovando o `access_token` via
  `refresh_token` quando necessário. Devolvem `True`/`False`.
- `sync_record(record, user)`: sincroniza com **todos** os provedores que o
  usuário tiver conectado, e devolve `True` só se todos tiverem sucesso.

Política de renovação: se o refresh falha, o `ExternalCalendarToken` é
removido (o usuário precisará reconectar) e um warning é logado.

IMPORTANTE: nenhuma chamada HTTP real ao Google/Microsoft acontece nos
testes automatizados -- tudo é mockado. As credenciais de app OAuth só
existem de verdade em produção.

Sobre privacidade: o título e a descrição do evento carregam dados de saúde
do paciente para servidores de terceiros, sob a conta pessoal do cuidador.
`EVENT_DETAIL_LEVEL` permite manter o evento discreto (só o horário, sem o
quê nem a descrição), que é o default. Ver o card de consentimento aberto
na revisão do lote -- o padrão a seguir é o do `ChatConsent`.
"""
import logging
from datetime import datetime, time as time_cls, timedelta, timezone as dt_timezone

import msal
import requests
from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials as GoogleCredentials
from googleapiclient.discovery import build as build_google_service

from care.models import ExternalCalendarToken

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
MICROSOFT_GRAPH_EVENTS_URL = "https://graph.microsoft.com/v1.0/me/events"
MICROSOFT_SCOPES = ["Calendars.ReadWrite"]
EVENT_TITLE_PREFIX = "[CuidarJuntos]"
DEFAULT_EVENT_DURATION = timedelta(minutes=30)
GRAPH_TIMEOUT_SECONDS = 10


def _detail_level() -> str:
    """'full' inclui o que/descrição no evento; 'discreet' omite ambos."""
    return getattr(settings, "CALENDAR_EVENT_DETAIL_LEVEL", "discreet")


def _event_title(record) -> str:
    if _detail_level() == "full":
        return f"{EVENT_TITLE_PREFIX} {record.what}"
    return f"{EVENT_TITLE_PREFIX} Cuidado agendado"


def _event_description(record) -> str:
    if _detail_level() == "full":
        return record.description or ""
    return ""


def _event_datetimes(record):
    """Devolve (início, fim) timezone-aware para o `CareRecord`."""
    naive_start = datetime.combine(record.date, record.time or time_cls(0, 0))
    start = (
        timezone.make_aware(naive_start)
        if timezone.is_naive(naive_start)
        else naive_start
    )
    return start, start + DEFAULT_EVENT_DURATION


def _microsoft_authority():
    return f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}"


# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------
def _get_google_service(user):
    """Client autenticado da API do Google Calendar para `user`.

    Renova o `access_token` se `expires_at` já passou (ou é nulo -- ver
    `ExternalCalendarToken.is_expired`). Sem token salvo, devolve `None`.
    Se a renovação falhar, remove o vínculo, loga e devolve `None`.
    """
    token = ExternalCalendarToken.objects.filter(
        user=user, provider=ExternalCalendarToken.Provider.GOOGLE, is_active=True
    ).first()
    if token is None:
        return None

    credentials = GoogleCredentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri=GOOGLE_TOKEN_URI,
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    if token.is_expired:
        try:
            credentials.refresh(GoogleAuthRequest())
        except Exception:
            logger.warning(
                "Falha ao renovar token Google do usuário %s; removendo vínculo.",
                user.id,
                exc_info=True,
            )
            token.delete()
            return None

        expiry = credentials.expiry
        if expiry is not None and timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry, dt_timezone.utc)

        token.access_token = credentials.token
        if credentials.refresh_token:
            token.refresh_token = credentials.refresh_token
        token.expires_at = expiry
        token.save(update_fields=["access_token", "refresh_token", "expires_at"])

    return build_google_service(
        "calendar", "v3", credentials=credentials, cache_discovery=False
    )


def sync_record_to_google(record, user) -> bool:
    """Cria um evento no Google Calendar ("primary") a partir do `record`."""
    service = _get_google_service(user)
    if service is None:
        return False

    start, end = _event_datetimes(record)
    # A API do Google aceita `dateTime` com offset e infere o fuso dele.
    event_body = {
        "summary": _event_title(record),
        "description": _event_description(record),
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }

    try:
        service.events().insert(calendarId="primary", body=event_body).execute()
    except Exception:
        logger.warning(
            "Falha ao criar evento no Google Calendar para o registro %s.",
            record.id,
            exc_info=True,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Microsoft Outlook (Graph)
# ---------------------------------------------------------------------------
def _get_microsoft_access_token(user):
    """Access token Microsoft válido para `user`, renovando se preciso.

    Mesma política do `_get_google_service`.
    """
    token = ExternalCalendarToken.objects.filter(
        user=user, provider=ExternalCalendarToken.Provider.MICROSOFT, is_active=True
    ).first()
    if token is None:
        return None

    if not token.is_expired:
        return token.access_token

    app = msal.ConfidentialClientApplication(
        client_id=settings.MICROSOFT_CLIENT_ID,
        client_credential=settings.MICROSOFT_CLIENT_SECRET,
        authority=_microsoft_authority(),
    )
    result = app.acquire_token_by_refresh_token(
        token.refresh_token, scopes=MICROSOFT_SCOPES
    ) or {}
    access_token = result.get("access_token")

    if not access_token:
        logger.warning(
            "Falha ao renovar token Microsoft do usuário %s (%s); removendo vínculo.",
            user.id,
            result.get("error_description", "resposta vazia"),
        )
        token.delete()
        return None

    token.access_token = access_token
    if result.get("refresh_token"):
        token.refresh_token = result["refresh_token"]
    token.expires_at = timezone.now() + timedelta(
        seconds=result.get("expires_in", 3600)
    )
    token.save(update_fields=["access_token", "refresh_token", "expires_at"])
    return access_token


def sync_record_to_microsoft(record, user) -> bool:
    """Cria um evento no Outlook (Microsoft Graph API) a partir do `record`."""
    access_token = _get_microsoft_access_token(user)
    if not access_token:
        return False

    start, end = _event_datetimes(record)
    # O Graph espera `dateTime` SEM offset, com o fuso dado em `timeZone`.
    # Mandar os dois (ex.: "...-03:00" junto de timeZone "UTC") faz o evento
    # aparecer deslocado -- num lembrete de medicação isso tem consequência
    # clínica. Convertemos para UTC e removemos o tzinfo.
    start_utc = start.astimezone(dt_timezone.utc).replace(tzinfo=None)
    end_utc = end.astimezone(dt_timezone.utc).replace(tzinfo=None)
    event_body = {
        "subject": _event_title(record),
        "body": {"contentType": "text", "content": _event_description(record)},
        "start": {"dateTime": start_utc.isoformat(), "timeZone": "UTC"},
        "end": {"dateTime": end_utc.isoformat(), "timeZone": "UTC"},
    }

    try:
        response = requests.post(
            MICROSOFT_GRAPH_EVENTS_URL,
            json=event_body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            timeout=GRAPH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.warning(
            "Falha ao criar evento no Outlook para o registro %s.",
            record.id,
            exc_info=True,
        )
        return False

    return True


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------
def _handler_for(provider):
    """Resolve a função de sync do provedor em tempo de chamada.

    De propósito não é um dict montado no import: assim o despacho enxerga
    substituições feitas depois (mocks nos testes, por exemplo) em vez de
    ficar preso às referências capturadas na definição do módulo.
    """
    if provider == ExternalCalendarToken.Provider.GOOGLE:
        return sync_record_to_google
    if provider == ExternalCalendarToken.Provider.MICROSOFT:
        return sync_record_to_microsoft
    return None


def sync_record(record, user) -> bool:
    """Sincroniza `record` com TODOS os calendários conectados por `user`.

    Um usuário pode ter Google e Outlook conectados ao mesmo tempo (a
    unicidade do vínculo é por `(user, provider)`). Escolher um dos dois
    arbitrariamente -- o que um `.first()` sem ordenação faria -- mandaria o
    evento para um calendário imprevisível, sem o usuário saber qual.

    Devolve `True` se havia ao menos um provedor conectado e todos tiveram
    sucesso; `False` se não havia nenhum ou se algum falhou (o chamador
    trata isso como "reprocessar depois", ver `api.tasks`).
    """
    providers = list(
        ExternalCalendarToken.objects.filter(user=user, is_active=True)
        .order_by("provider")
        .values_list("provider", flat=True)
    )
    if not providers:
        return False

    results = []
    for provider in providers:
        handler = _handler_for(provider)
        if handler is None:
            logger.warning("Provedor de calendário desconhecido: %r", provider)
            results.append(False)
            continue
        results.append(handler(record, user))

    return all(results)
