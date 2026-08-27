"""Testes do card #50 (pre-requisito do epico de integracao de calendarios).

Garante que as bibliotecas necessarias para a integracao com Google Calendar
(google-auth-oauthlib, google-api-python-client), Microsoft/Outlook (msal) e
para o cliente HTTP do Microsoft Graph (requests) estao instaladas e
importaveis no ambiente -- equivalente a `pip install -r requirements.txt`
ter rodado sem conflitos.

Nao ha teste sobre o CONTEUDO do requirements.txt: um assert de que o arquivo
contem `pacote==versao` nao verifica comportamento nenhum e vira alarme falso
no primeiro bump de versao por seguranca. Se a lib nao estiver instalada, os
testes abaixo falham -- que e o sinal util.

Nenhuma chamada de rede real e feita as APIs do Google/Microsoft aqui.
"""
from django.test import SimpleTestCase


class CalendarIntegrationDependenciesTest(SimpleTestCase):
    def test_google_auth_oauthlib_esta_instalado_e_importavel(self):
        try:
            from google_auth_oauthlib.flow import Flow  # noqa: F401
        except ImportError as exc:
            self.fail(
                "google-auth-oauthlib nao esta instalado/importavel: "
                f"{exc}. Rode pip install -r requirements.txt."
            )

    def test_google_api_python_client_esta_instalado_e_importavel(self):
        try:
            from googleapiclient.discovery import build  # noqa: F401
        except ImportError as exc:
            self.fail(
                "google-api-python-client nao esta instalado/importavel: "
                f"{exc}. Rode pip install -r requirements.txt."
            )

    def test_msal_esta_instalado_e_importavel(self):
        try:
            from msal import ConfidentialClientApplication  # noqa: F401
        except ImportError as exc:
            self.fail(
                f"msal nao esta instalado/importavel: {exc}. "
                "Rode pip install -r requirements.txt."
            )

    def test_requests_esta_instalado_e_importavel(self):
        try:
            import requests  # noqa: F401
        except ImportError as exc:
            self.fail(
                f"requests nao esta instalado/importavel: {exc}. "
                "Rode pip install -r requirements.txt."
            )
