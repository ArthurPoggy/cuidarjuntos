# api/tests/test_calendar_integration_deps.py
"""
Testes do card #50 (pre-requisito do epico de integracao de calendarios):

Garante que as bibliotecas necessarias para a futura integracao com
Google Calendar (google-auth-oauthlib, google-api-python-client) e
Microsoft/Outlook (msal) estao:

(a) declaradas em requirements.txt nas versoes combinadas pelo card;
(b) de fato instaladas e importaveis no ambiente (equivalente a
    `pip install -r requirements.txt` sem conflitos);
(c) nao quebram `python manage.py check` (coberto indiretamente: o
    settings/apps do projeto continuam carregando normalmente com os
    pacotes presentes no ambiente).

Nenhuma chamada de rede real e feita a APIs do Google/Microsoft aqui --
apenas verificacao de que os pacotes existem e sao importaveis.
"""
import pathlib

from django.test import SimpleTestCase


REQUIREMENTS_PATH = pathlib.Path(__file__).resolve().parents[2] / "requirements.txt"

EXPECTED_PINS = {
    "google-auth-oauthlib": "1.2.1",
    "google-api-python-client": "2.158.0",
    "msal": "1.31.0",
}


class CalendarIntegrationDependenciesTest(SimpleTestCase):
    def test_requirements_txt_declara_as_libs_com_as_versoes_do_card(self):
        conteudo = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        linhas = {
            linha.strip()
            for linha in conteudo.splitlines()
            if linha.strip() and not linha.strip().startswith("#")
        }
        for pacote, versao in EXPECTED_PINS.items():
            esperado = f"{pacote}=={versao}"
            self.assertIn(
                esperado,
                linhas,
                msg=(
                    f"requirements.txt deve conter '{esperado}' "
                    "(pre-requisito do epico de integracao de calendarios)"
                ),
            )

    def test_google_auth_oauthlib_esta_instalado_e_importavel(self):
        try:
            import google_auth_oauthlib  # noqa: F401
            from google_auth_oauthlib.flow import Flow  # noqa: F401
        except ImportError as exc:
            self.fail(
                "google-auth-oauthlib nao esta instalado/importavel: "
                f"{exc}. Rode pip install -r requirements.txt."
            )

    def test_google_api_python_client_esta_instalado_e_importavel(self):
        try:
            import googleapiclient  # noqa: F401
            from googleapiclient.discovery import build  # noqa: F401
        except ImportError as exc:
            self.fail(
                "google-api-python-client nao esta instalado/importavel: "
                f"{exc}. Rode pip install -r requirements.txt."
            )

    def test_msal_esta_instalado_e_importavel(self):
        try:
            import msal  # noqa: F401
            from msal import ConfidentialClientApplication  # noqa: F401
        except ImportError as exc:
            self.fail(
                f"msal nao esta instalado/importavel: {exc}. "
                "Rode pip install -r requirements.txt."
            )
