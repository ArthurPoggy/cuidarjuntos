import json
import logging
import urllib.error
import urllib.request
from itertools import islice
from typing import Any

from django.utils import timezone

from care.models import PushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
BATCH_SIZE = 100


def _batched(iterable, size: int):
    it = iter(iterable)
    while batch := list(islice(it, size)):
        yield batch


def _post_expo(messages: list[dict]) -> list[dict]:
    """Envia um lote à Expo Push API e devolve a lista de tickets."""
    payload = json.dumps(messages).encode()
    req = urllib.request.Request(
        EXPO_PUSH_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            return body.get("data", [])
    except urllib.error.URLError as exc:
        logger.error("Expo Push API — erro de rede: %s", exc)
        return []
    except Exception as exc:
        logger.error("Expo Push API — erro inesperado: %s", exc)
        return []


def _invalidate_token(token_str: str) -> None:
    """Soft-deleta um token recusado como DeviceNotRegistered pela Expo."""
    updated = PushToken.objects.filter(
        token=token_str,
        deleted_at__isnull=True,
    ).update(deleted_at=timezone.now())
    if updated:
        logger.info("Token invalidado (DeviceNotRegistered): %.20s…", token_str)


def send_push(
    user_ids: list[int],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, int]:
    """
    Envia notificações push para todos os tokens ativos dos usuários informados.

    Processa em lotes de até 100 mensagens (limite da Expo Push API).
    Tokens com erro DeviceNotRegistered são soft-deletados automaticamente.

    Retorna: {"sent": int, "failed": int, "invalidated": int}
    """
    if not user_ids:
        return {"sent": 0, "failed": 0, "invalidated": 0}

    tokens = list(
        PushToken.objects.filter(
            user_id__in=user_ids,
            deleted_at__isnull=True,
        ).values_list("token", flat=True)
    )

    if not tokens:
        return {"sent": 0, "failed": 0, "invalidated": 0}

    summary: dict[str, int] = {"sent": 0, "failed": 0, "invalidated": 0}

    for batch in _batched(tokens, BATCH_SIZE):
        messages = [
            {
                "to": token,
                "title": title,
                "body": body,
                **({"data": data} if data else {}),
            }
            for token in batch
        ]

        tickets = _post_expo(messages)

        # Se a API não respondeu, conta tudo como falha sem invalidar
        if not tickets:
            summary["failed"] += len(batch)
            continue

        for token, ticket in zip(batch, tickets):
            if ticket.get("status") == "ok":
                summary["sent"] += 1
            else:
                error = ticket.get("details", {}).get("error", "")
                if error == "DeviceNotRegistered":
                    _invalidate_token(token)
                    summary["invalidated"] += 1
                else:
                    logger.warning(
                        "Push falhou — token %.20s…: %s", token, ticket.get("message", error)
                    )
                    summary["failed"] += 1

    return summary
