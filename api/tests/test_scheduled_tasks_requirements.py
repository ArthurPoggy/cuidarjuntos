"""Testes para o card #69: instalar bibliotecas de tarefas agendadas.

Garante que o requirements.txt declara as versoes esperadas de celery,
redis, django-celery-beat e django-celery-results, e que os pacotes
django-celery-beat/django-celery-results estao de fato instalados no
ambiente (pre-requisito para as tarefas de Celery Beat que virao a
seguir).
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements.txt"

EXPECTED_PINS = {
    "celery": "5.4.0",
    "redis": "5.2.1",
    "django-celery-beat": "2.7.0",
    "django-celery-results": "2.5.1",
}


class RequirementsScheduledTasksTests(SimpleTestCase):
    def _read_requirements(self):
        self.assertTrue(
            REQUIREMENTS_PATH.exists(),
            f"requirements.txt nao encontrado em {REQUIREMENTS_PATH}",
        )
        return REQUIREMENTS_PATH.read_text(encoding="utf-8")

    def test_celery_pin_com_extra_redis(self):
        content = self._read_requirements()
        match = re.search(
            r"^celery(\[[\w,]+\])?==([\d.]+)\s*$", content, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "celery nao encontrado (ou sem pin de versao) em requirements.txt"
        )
        extra, version = match.group(1), match.group(2)
        self.assertEqual(
            version,
            EXPECTED_PINS["celery"],
            f"celery deveria estar pinado em {EXPECTED_PINS['celery']}, encontrado {version}",
        )
        self.assertEqual(
            extra,
            "[redis]",
            "celery deveria ser instalado com o extra [redis] (celery[redis])",
        )

    def test_redis_pin(self):
        content = self._read_requirements()
        match = re.search(r"^redis==([\d.]+)\s*$", content, re.MULTILINE)
        self.assertIsNotNone(
            match, "redis nao encontrado (ou sem pin de versao) em requirements.txt"
        )
        self.assertEqual(match.group(1), EXPECTED_PINS["redis"])

    def test_django_celery_beat_pin(self):
        content = self._read_requirements()
        match = re.search(
            r"^django-celery-beat==([\d.]+)\s*$", content, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "django-celery-beat nao encontrado em requirements.txt"
        )
        self.assertEqual(match.group(1), EXPECTED_PINS["django-celery-beat"])

    def test_django_celery_results_pin(self):
        content = self._read_requirements()
        match = re.search(
            r"^django-celery-results==([\d.]+)\s*$", content, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "django-celery-results nao encontrado em requirements.txt"
        )
        self.assertEqual(match.group(1), EXPECTED_PINS["django-celery-results"])

    def test_pacotes_instalaveis_no_ambiente(self):
        """Confirma que os pacotes novos foram de fato instalados (pip install
        -r requirements.txt rodou sem conflito neste ambiente)."""
        import django_celery_beat  # noqa: F401
        import django_celery_results  # noqa: F401
