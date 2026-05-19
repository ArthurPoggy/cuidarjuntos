import json
import urllib.error
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from api.services.push import BATCH_SIZE, send_push
from care.models import PushToken


def _expo_response(tickets: list[dict]) -> MagicMock:
    """Simula a resposta HTTP da Expo Push API."""
    body = json.dumps({"data": tickets}).encode()
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


def _ticket_ok() -> dict:
    return {"status": "ok", "id": "some-ticket-id"}


def _ticket_device_not_registered(message: str = "…") -> dict:
    return {
        "status": "error",
        "message": message,
        "details": {"error": "DeviceNotRegistered"},
    }


def _ticket_other_error(error: str = "MessageRateExceeded") -> dict:
    return {
        "status": "error",
        "message": "Too many messages",
        "details": {"error": error},
    }


PATCH_TARGET = "api.services.push.urllib.request.urlopen"


class SendPushBaseTests(TestCase):
    """Setup compartilhado: dois usuários com tokens."""

    def setUp(self):
        self.user1 = User.objects.create_user("user1", password="pass")
        self.user2 = User.objects.create_user("user2", password="pass")

        self.token1 = PushToken.objects.create(
            user=self.user1, token="ExponentPushToken[user1]", platform="android"
        )
        self.token2 = PushToken.objects.create(
            user=self.user2, token="ExponentPushToken[user2]", platform="ios"
        )


# ----------------------------------------------------------------------
# Casos sem chamada à API
# ----------------------------------------------------------------------

class SendPushEarlyReturnTests(TestCase):
    def test_empty_user_ids_returns_zeros(self):
        result = send_push([], "Título", "Corpo")
        self.assertEqual(result, {"sent": 0, "failed": 0, "invalidated": 0})

    def test_users_with_no_tokens_returns_zeros(self):
        user = User.objects.create_user("notoken", password="pass")
        result = send_push([user.id], "Título", "Corpo")
        self.assertEqual(result, {"sent": 0, "failed": 0, "invalidated": 0})

    def test_only_soft_deleted_tokens_returns_zeros(self):
        user = User.objects.create_user("softdel", password="pass")
        pt = PushToken.objects.create(user=user, token="SoftToken", platform="android")
        pt.deleted_at = timezone.now()
        pt.save(update_fields=["deleted_at"])

        result = send_push([user.id], "Título", "Corpo")
        self.assertEqual(result, {"sent": 0, "failed": 0, "invalidated": 0})


# ----------------------------------------------------------------------
# Envio bem-sucedido
# ----------------------------------------------------------------------

class SendPushSuccessTests(SendPushBaseTests):
    @patch(PATCH_TARGET)
    def test_single_user_single_token_sent(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_ok()])

        result = send_push([self.user1.id], "Olá", "Mensagem")

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["invalidated"], 0)

    @patch(PATCH_TARGET)
    def test_multiple_users_all_sent(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_ok(), _ticket_ok()])

        result = send_push([self.user1.id, self.user2.id], "Título", "Corpo")

        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["failed"], 0)

    @patch(PATCH_TARGET)
    def test_payload_includes_title_body_data(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_ok()])

        send_push([self.user1.id], "Meu Título", "Meu Corpo", data={"chave": "valor"})

        call_args = mock_urlopen.call_args[0][0]
        payload = json.loads(call_args.data)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["title"], "Meu Título")
        self.assertEqual(payload[0]["body"], "Meu Corpo")
        self.assertEqual(payload[0]["data"], {"chave": "valor"})
        self.assertEqual(payload[0]["to"], self.token1.token)

    @patch(PATCH_TARGET)
    def test_payload_without_data_field_omitted(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_ok()])

        send_push([self.user1.id], "Título", "Corpo")

        payload = json.loads(mock_urlopen.call_args[0][0].data)
        self.assertNotIn("data", payload[0])


# ----------------------------------------------------------------------
# DeviceNotRegistered — invalidação automática
# ----------------------------------------------------------------------

class SendPushInvalidationTests(SendPushBaseTests):
    @patch(PATCH_TARGET)
    def test_device_not_registered_soft_deletes_token(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response(
            [_ticket_device_not_registered()]
        )

        result = send_push([self.user1.id], "Título", "Corpo")

        self.assertEqual(result["invalidated"], 1)
        self.assertEqual(result["sent"], 0)

        self.token1.refresh_from_db()
        self.assertIsNotNone(self.token1.deleted_at)

    @patch(PATCH_TARGET)
    def test_device_not_registered_does_not_hard_delete(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response(
            [_ticket_device_not_registered()]
        )

        send_push([self.user1.id], "Título", "Corpo")

        self.assertTrue(PushToken.objects.filter(pk=self.token1.pk).exists())

    @patch(PATCH_TARGET)
    def test_mixed_ok_and_invalid(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response(
            [_ticket_ok(), _ticket_device_not_registered()]
        )

        result = send_push([self.user1.id, self.user2.id], "Título", "Corpo")

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["invalidated"], 1)
        self.assertEqual(result["failed"], 0)


# ----------------------------------------------------------------------
# Outros erros da API
# ----------------------------------------------------------------------

class SendPushFailureTests(SendPushBaseTests):
    @patch(PATCH_TARGET)
    def test_other_error_increments_failed(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_other_error()])

        result = send_push([self.user1.id], "Título", "Corpo")

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["invalidated"], 0)

    @patch(PATCH_TARGET)
    def test_other_error_does_not_invalidate_token(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_other_error()])

        send_push([self.user1.id], "Título", "Corpo")

        self.token1.refresh_from_db()
        self.assertIsNone(self.token1.deleted_at)

    @patch(PATCH_TARGET)
    def test_network_error_increments_failed(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        result = send_push([self.user1.id], "Título", "Corpo")

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["sent"], 0)

    @patch(PATCH_TARGET)
    def test_network_error_does_not_invalidate_token(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.URLError("timeout")

        send_push([self.user1.id], "Título", "Corpo")

        self.token1.refresh_from_db()
        self.assertIsNone(self.token1.deleted_at)


# ----------------------------------------------------------------------
# Resposta parcial / inconsistente da Expo
# ----------------------------------------------------------------------

class SendPushPartialResponseTests(SendPushBaseTests):
    @patch(PATCH_TARGET)
    def test_fewer_tickets_than_messages_counts_missing_as_failed(self, mock_urlopen):
        # Lote tem 2 tokens, Expo devolve apenas 1 ticket (ok).
        mock_urlopen.return_value = _expo_response([_ticket_ok()])

        result = send_push([self.user1.id, self.user2.id], "Título", "Corpo")

        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["invalidated"], 0)

    @patch(PATCH_TARGET)
    def test_fewer_tickets_does_not_invalidate_missing_tokens(self, mock_urlopen):
        mock_urlopen.return_value = _expo_response([_ticket_ok()])

        send_push([self.user1.id, self.user2.id], "Título", "Corpo")

        self.token1.refresh_from_db()
        self.token2.refresh_from_db()
        self.assertIsNone(self.token1.deleted_at)
        self.assertIsNone(self.token2.deleted_at)

    @patch(PATCH_TARGET)
    def test_more_tickets_than_messages_ignored(self, mock_urlopen):
        # Caso patológico: Expo devolve mais tickets do que mensagens enviadas.
        # Tickets extras são ignorados; ninguém é marcado como falha além do batch.
        mock_urlopen.return_value = _expo_response([_ticket_ok(), _ticket_ok(), _ticket_ok()])

        result = send_push([self.user1.id, self.user2.id], "Título", "Corpo")

        self.assertEqual(result["sent"], 2)
        self.assertEqual(result["failed"], 0)


# ----------------------------------------------------------------------
# Batching — lotes de até 100
# ----------------------------------------------------------------------

class SendPushBatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("batcher", password="pass")
        for i in range(BATCH_SIZE + 10):
            PushToken.objects.create(
                user=self.user,
                token=f"ExponentPushToken[batch{i:04d}]",
                platform="android",
            )

    @patch(PATCH_TARGET)
    def test_110_tokens_sends_two_batches(self, mock_urlopen):
        first_batch  = [_ticket_ok()] * BATCH_SIZE
        second_batch = [_ticket_ok()] * 10
        mock_urlopen.side_effect = [
            _expo_response(first_batch),
            _expo_response(second_batch),
        ]

        result = send_push([self.user.id], "Título", "Corpo")

        self.assertEqual(mock_urlopen.call_count, 2)
        self.assertEqual(result["sent"], BATCH_SIZE + 10)

    @patch(PATCH_TARGET)
    def test_first_batch_max_size(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _expo_response([_ticket_ok()] * BATCH_SIZE),
            _expo_response([_ticket_ok()] * 10),
        ]

        send_push([self.user.id], "Título", "Corpo")

        first_call_payload = json.loads(mock_urlopen.call_args_list[0][0][0].data)
        self.assertEqual(len(first_call_payload), BATCH_SIZE)

    @patch(PATCH_TARGET)
    def test_second_batch_has_remainder(self, mock_urlopen):
        mock_urlopen.side_effect = [
            _expo_response([_ticket_ok()] * BATCH_SIZE),
            _expo_response([_ticket_ok()] * 10),
        ]

        send_push([self.user.id], "Título", "Corpo")

        second_call_payload = json.loads(mock_urlopen.call_args_list[1][0][0].data)
        self.assertEqual(len(second_call_payload), 10)
