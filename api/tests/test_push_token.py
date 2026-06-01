from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

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

    # ------------------------------------------------------------------
    # Soft delete (campos deleted_at / deleted_by)
    # ------------------------------------------------------------------

    def test_soft_delete_fields_default_null(self):
        pt = self._make_token()
        self.assertIsNone(pt.deleted_at)
        self.assertIsNone(pt.deleted_by)
        self.assertTrue(pt.is_active)

    def test_is_active_false_when_soft_deleted(self):
        pt = self._make_token()
        pt.deleted_at = timezone.now()
        pt.deleted_by = self.user
        pt.save(update_fields=["deleted_at", "deleted_by"])
        pt.refresh_from_db()
        self.assertFalse(pt.is_active)


# ======================================================================
# Testes de API — POST e DELETE /api/v1/push-tokens/
# ======================================================================

URL = "/api/v1/push-tokens/"


class PushTokenPostTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer_api", password="pass1234")
        self.client.force_authenticate(user=self.user)

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    def test_post_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.post(URL, {"token": "ABC", "platform": "android"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Validação de payload (400)
    # ------------------------------------------------------------------

    def test_post_missing_token_returns_400(self):
        resp = self.client.post(URL, {"platform": "android"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_missing_platform_returns_400(self):
        resp = self.client.post(URL, {"token": "SomeToken[001]"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_invalid_platform_returns_400(self):
        resp = self.client.post(URL, {"token": "T", "platform": "windows"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_post_empty_token_returns_400(self):
        resp = self.client.post(URL, {"token": "", "platform": "ios"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Criação (201)
    # ------------------------------------------------------------------

    def test_post_creates_token_returns_201(self):
        resp = self.client.post(URL, {"token": "NewToken[abc]", "platform": "ios"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["token"], "NewToken[abc]")
        self.assertEqual(resp.data["platform"], "ios")
        self.assertTrue(resp.data["is_active"])
        self.assertEqual(PushToken.objects.count(), 1)

    def test_post_android_platform(self):
        resp = self.client.post(URL, {"token": "AndroidToken", "platform": "android"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["platform"], "android")

    # ------------------------------------------------------------------
    # Upsert — token existente (200)
    # ------------------------------------------------------------------

    def test_post_existing_token_returns_200(self):
        PushToken.objects.create(user=self.user, token="ExistingToken", platform="android")
        resp = self.client.post(URL, {"token": "ExistingToken", "platform": "ios"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.count(), 1)  # não criou duplicata
        self.assertEqual(PushToken.objects.first().platform, "ios")  # plataforma atualizada

    def test_post_reactivates_soft_deleted_token(self):
        pt = PushToken.objects.create(user=self.user, token="DeletedToken", platform="android")
        pt.deleted_at = timezone.now()
        pt.deleted_by = self.user
        pt.save(update_fields=["deleted_at", "deleted_by"])

        resp = self.client.post(URL, {"token": "DeletedToken", "platform": "android"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["is_active"])
        pt.refresh_from_db()
        self.assertIsNone(pt.deleted_at)

    def test_post_reassigns_token_to_new_user(self):
        """Token de outro usuário é reatribuído ao usuário que faz o POST (troca de aparelho)."""
        other = User.objects.create_user("other_api", password="pass1234")
        PushToken.objects.create(user=other, token="SharedDevice", platform="ios")

        resp = self.client.post(URL, {"token": "SharedDevice", "platform": "ios"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(PushToken.objects.get(token="SharedDevice").user, self.user)


class PushTokenDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer_del", password="pass1234")
        self.client.force_authenticate(user=self.user)

    def _create(self, token="DeviceToken[del]", platform="android"):
        return PushToken.objects.create(user=self.user, token=token, platform=platform)

    # ------------------------------------------------------------------
    # Autenticação
    # ------------------------------------------------------------------

    def test_delete_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        resp = self.client.delete(URL, {"token": "Any"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Validação (400 / 404)
    # ------------------------------------------------------------------

    def test_delete_missing_token_returns_400(self):
        resp = self.client.delete(URL, {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_nonexistent_token_returns_404(self):
        resp = self.client.delete(URL, {"token": "DoesNotExist"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_token_of_other_user_returns_404(self):
        other = User.objects.create_user("other_del", password="pass1234")
        PushToken.objects.create(user=other, token="OtherUserToken", platform="ios")
        resp = self.client.delete(URL, {"token": "OtherUserToken"}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_already_deleted_returns_400(self):
        pt = self._create()
        pt.deleted_at = timezone.now()
        pt.deleted_by = self.user
        pt.save(update_fields=["deleted_at", "deleted_by"])
        resp = self.client.delete(URL, {"token": pt.token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Soft delete (204)
    # ------------------------------------------------------------------

    def test_delete_valid_token_returns_204(self):
        pt = self._create()
        resp = self.client.delete(URL, {"token": pt.token}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_sets_deleted_at(self):
        pt = self._create()
        self.client.delete(URL, {"token": pt.token}, format="json")
        pt.refresh_from_db()
        self.assertIsNotNone(pt.deleted_at)

    def test_delete_sets_deleted_by(self):
        pt = self._create()
        self.client.delete(URL, {"token": pt.token}, format="json")
        pt.refresh_from_db()
        self.assertEqual(pt.deleted_by, self.user)

    def test_delete_keeps_record_in_database(self):
        """Soft delete não remove o registro — apenas marca como inativo."""
        pt = self._create()
        self.client.delete(URL, {"token": pt.token}, format="json")
        self.assertTrue(PushToken.objects.filter(pk=pt.pk).exists())
