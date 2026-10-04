"""Endpoint público de versão do sistema (GET /api/v1/app-version/)."""
import os
from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from api.views.app_version import VERSION_FILE, read_version


class AppVersionEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()

    def test_publico_sem_autenticacao(self):
        resp = self.client.get("/api/v1/app-version/")
        self.assertEqual(resp.status_code, 200)

    def test_devolve_versao_do_arquivo_version(self):
        resp = self.client.get("/api/v1/app-version/")
        self.assertEqual(resp.json()["version"], read_version())
        self.assertRegex(read_version(), r"^\d+\.\d+\.\d+$")

    def test_politica_vem_do_ambiente(self):
        env = {"MIN_SUPPORTED_APP_VERSION": "1.2.0", "APP_UPDATE_URL": "https://x.test/app"}
        with mock.patch.dict(os.environ, env):
            data = self.client.get("/api/v1/app-version/").json()
        self.assertEqual(data["min_supported_version"], "1.2.0")
        self.assertEqual(data["update_url"], "https://x.test/app")

    def test_arquivo_ausente_cai_no_fallback(self):
        with mock.patch.object(type(VERSION_FILE), "read_text", side_effect=OSError):
            self.assertEqual(read_version(), "0.0.0")
