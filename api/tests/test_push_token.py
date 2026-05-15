from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from care.models import PushToken


class PushTokenModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("carer", password="pass1234")

    def _make_token(self, user=None, token="ExponentPushToken[abc123]", platform="android"):
        return PushToken.objects.create(
            user=user or self.user,
            token=token,
            platform=platform,
        )

    # ------------------------------------------------------------------
    # Criação e campos
    # ------------------------------------------------------------------

    def test_create_push_token(self):
        pt = self._make_token()
        self.assertEqual(pt.user, self.user)
        self.assertEqual(pt.token, "ExponentPushToken[abc123]")
        self.assertEqual(pt.platform, "android")
        self.assertIsNotNone(pt.created_at)
        self.assertIsNone(pt.last_used_at)

    def test_platform_choices_ios(self):
        pt = self._make_token(platform="ios")
        self.assertEqual(pt.platform, PushToken.Platform.IOS)

    def test_platform_choices_android(self):
        pt = self._make_token(platform="android")
        self.assertEqual(pt.platform, PushToken.Platform.ANDROID)

    def test_str_representation(self):
        pt = self._make_token()
        s = str(pt)
        self.assertIn("android", s)
        self.assertIn("ExponentPushToken", s)

    def test_last_used_at_nullable(self):
        pt = self._make_token()
        self.assertIsNone(pt.last_used_at)

    def test_last_used_at_can_be_set(self):
        pt = self._make_token()
        now = timezone.now()
        pt.last_used_at = now
        pt.save(update_fields=["last_used_at"])
        pt.refresh_from_db()
        self.assertIsNotNone(pt.last_used_at)

    # ------------------------------------------------------------------
    # Unicidade do token
    # ------------------------------------------------------------------

    def test_token_must_be_unique(self):
        self._make_token(token="UniqueToken[xyz]")
        with self.assertRaises(IntegrityError):
            self._make_token(token="UniqueToken[xyz]")

    def test_same_user_can_have_multiple_different_tokens(self):
        self._make_token(token="TokenA")
        self._make_token(token="TokenB")
        self.assertEqual(PushToken.objects.filter(user=self.user).count(), 2)

    def test_different_users_cannot_share_same_token(self):
        other = User.objects.create_user("other_user", password="pass1234")
        self._make_token(user=self.user, token="SharedToken")
        with self.assertRaises(IntegrityError):
            self._make_token(user=other, token="SharedToken")

    # ------------------------------------------------------------------
    # Cascata de deleção
    # ------------------------------------------------------------------

    def test_tokens_deleted_when_user_deleted(self):
        self._make_token(token="WillBeGone")
        self.assertEqual(PushToken.objects.count(), 1)
        self.user.delete()
        self.assertEqual(PushToken.objects.count(), 0)

    # ------------------------------------------------------------------
    # Consultas por usuário (índice)
    # ------------------------------------------------------------------

    def test_filter_by_user(self):
        other = User.objects.create_user("other_user2", password="pass1234")
        self._make_token(user=self.user, token="UserToken")
        self._make_token(user=other, token="OtherToken")

        user_tokens = PushToken.objects.filter(user=self.user)
        self.assertEqual(user_tokens.count(), 1)
        self.assertEqual(user_tokens.first().token, "UserToken")

    def test_get_by_token_value(self):
        self._make_token(token="LookupToken[001]")
        pt = PushToken.objects.get(token="LookupToken[001]")
        self.assertEqual(pt.user, self.user)

    # ------------------------------------------------------------------
    # Remoção de token inválido (comportamento esperado pela regra de negócio)
    # ------------------------------------------------------------------

    def test_delete_invalid_token(self):
        """Tokens com DeviceNotRegistered devem poder ser removidos pelo token string."""
        self._make_token(token="InvalidDevice[xxx]")
        deleted, _ = PushToken.objects.filter(token="InvalidDevice[xxx]").delete()
        self.assertEqual(deleted, 1)
        self.assertEqual(PushToken.objects.count(), 0)

    def test_bulk_delete_tokens_for_user(self):
        """Todos os tokens de um usuário podem ser removidos de uma vez."""
        self._make_token(token="T1")
        self._make_token(token="T2")
        self._make_token(token="T3")
        deleted, _ = PushToken.objects.filter(user=self.user).delete()
        self.assertEqual(deleted, 3)
