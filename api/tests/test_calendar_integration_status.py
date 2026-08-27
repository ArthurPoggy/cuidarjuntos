"""Testes do card #41 -- toggle "Sincronizar com calendário" no registro.

Cobre o endpoint de status das integrações e o campo `sync_to_calendar`
no `CareRecord`/serializer.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from care.models import (
    CareGroup, CareRecord, ExternalCalendarToken, GroupMembership, Patient,
)

STATUS_URL = "/api/v1/integrations/calendar/status/"


class CalendarIntegrationStatusTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer41", password="pass1234")
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        resp = self.client.get(STATUS_URL)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sem_integracao_responde_desconectado(self):
        resp = self.client.get(STATUS_URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data["connected"])
        self.assertEqual(resp.data["providers"], [])

    def test_lista_os_provedores_conectados(self):
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="a",
        )
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.MICROSOFT,
            access_token="b",
        )

        resp = self.client.get(STATUS_URL)

        self.assertTrue(resp.data["connected"])
        self.assertEqual(resp.data["providers"], ["google", "microsoft"])

    def test_vinculo_inativo_nao_conta(self):
        ExternalCalendarToken.objects.create(
            user=self.user,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="a",
            is_active=False,
        )

        resp = self.client.get(STATUS_URL)

        self.assertFalse(resp.data["connected"])
        self.assertEqual(resp.data["providers"], [])

    def test_nao_vaza_integracao_de_outro_usuario(self):
        outro = User.objects.create_user("outro41", password="pass1234")
        ExternalCalendarToken.objects.create(
            user=outro,
            provider=ExternalCalendarToken.Provider.GOOGLE,
            access_token="a",
        )

        resp = self.client.get(STATUS_URL)

        self.assertFalse(resp.data["connected"])


class CareRecordSyncToCalendarFieldTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("carer41b", password="pass1234")
        self.patient = Patient.objects.create(name="Paciente Sync")
        self.group = CareGroup.objects.create(name="GrupoSync", patient=self.patient)
        GroupMembership.objects.create(
            user=self.user, group=self.group, relation_to_patient="FAMILY"
        )
        self.client.force_authenticate(user=self.user)

    def test_campo_tem_default_false(self):
        record = CareRecord.objects.create(
            patient=self.patient,
            type="medication",
            what="Remédio",
            date=timezone.localdate() + timedelta(days=1),
            caregiver="Cuidador",
        )
        self.assertFalse(record.sync_to_calendar)
        self.assertIsNone(record.synced_to_external_at)

    def test_serializer_expoe_o_campo(self):
        record = CareRecord.objects.create(
            patient=self.patient,
            type="medication",
            what="Remédio",
            date=timezone.localdate() + timedelta(days=1),
            caregiver="Cuidador",
            sync_to_calendar=True,
        )

        resp = self.client.get(f"/api/v1/records/{record.id}/")

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["sync_to_calendar"])

    def test_pode_ser_definido_na_criacao_via_api(self):
        resp = self.client.post(
            "/api/v1/records/",
            {
                "type": "medication",
                "what": "Remédio da noite",
                "date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "time": "20:00",
                "sync_to_calendar": True,
            },
            format="json",
        )

        self.assertIn(resp.status_code, (200, 201), resp.data)
        record = CareRecord.objects.get(id=resp.data["id"])
        self.assertTrue(record.sync_to_calendar)

    def test_synced_to_external_at_nao_e_exposto_na_api(self):
        """E controle interno da task diaria (card #45), nao do cliente."""
        record = CareRecord.objects.create(
            patient=self.patient,
            type="medication",
            what="Remédio",
            date=timezone.localdate() + timedelta(days=1),
            caregiver="Cuidador",
        )

        resp = self.client.get(f"/api/v1/records/{record.id}/")

        self.assertNotIn("synced_to_external_at", resp.data)
