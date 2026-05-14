"""
Stub de envio push — será substituído pela implementação completa do PR #5
(feature/push-service), que inclui o modelo PushToken e integração com a
Expo Push API.
"""
import logging

logger = logging.getLogger(__name__)


def send_push(user_ids, title, body, data=None):
    """Envia notificação push para os usuários informados.

    Stub: apenas loga. A implementação real (PR #5) busca PushTokens ativos,
    envia em lotes de 100 via Expo Push API e realiza soft-delete de tokens
    inválidos (DeviceNotRegistered).
    """
    logger.debug(
        "send_push (stub): user_ids=%s title=%r body=%r data=%r",
        user_ids, title, body, data,
    )
