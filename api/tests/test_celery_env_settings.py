"""
Testes para as variáveis de ambiente do Celery (card #67).

Cobrem:
- .env.example documenta CELERY_BROKER_URL apontando para o Redis local.
- settings.py lê CELERY_BROKER_URL/CELERY_RESULT_BACKEND do ambiente, com
  fallback para redis://localhost:6379/0 quando a variável não existe.
- CELERY_RESULT_BACKEND passa a usar "django-db" automaticamente quando o
  pacote django_celery_results estiver instalado (task 69), sem quebrar o
  fallback para Redis quando ele ainda não estiver disponível.
"""

import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _run_settings_snippet(code, extra_env=None):
    """Executa um snippet Python isolado com django.conf.settings carregado."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "cuidarjuntos.settings"
    # Remove variáveis que poderiam vazar do ambiente de teste real.
    env.pop("CELERY_BROKER_URL", None)
    env.pop("CELERY_RESULT_BACKEND", None)
    if extra_env:
        env.update(extra_env)

    full_code = (
        "import django\n"
        "django.setup()\n"
        "from django.conf import settings\n" + code
    )
    result = subprocess.run(
        [sys.executable, "-c", full_code],
        cwd=str(BASE_DIR),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"Snippet falhou.\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    return result.stdout.strip()


class TestEnvExample:
    def test_env_example_documenta_celery_broker_url(self):
        env_example = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
        assert "CELERY_BROKER_URL" in env_example
        assert "CELERY_BROKER_URL=redis://localhost:6379/0" in env_example


class TestCelerySettingsFallback:
    def test_celery_broker_url_usa_fallback_local_sem_env(self):
        out = _run_settings_snippet("print(settings.CELERY_BROKER_URL)")
        assert out == "redis://localhost:6379/0"

    def test_celery_broker_url_le_do_ambiente(self):
        out = _run_settings_snippet(
            "print(settings.CELERY_BROKER_URL)",
            extra_env={"CELERY_BROKER_URL": "redis://minha-fila:6380/2"},
        )
        assert out == "redis://minha-fila:6380/2"

    def test_celery_result_backend_le_do_ambiente(self):
        out = _run_settings_snippet(
            "print(settings.CELERY_RESULT_BACKEND)",
            extra_env={"CELERY_RESULT_BACKEND": "redis://minha-fila:6380/3"},
        )
        assert out == "redis://minha-fila:6380/3"

    def test_celery_result_backend_fallback_sem_env(self):
        # Sem CELERY_RESULT_BACKEND no ambiente: usa "django-db" se
        # django_celery_results estiver instalado (task 69), ou o Redis
        # local caso contrário.
        try:
            import django_celery_results  # noqa: F401

            esperado = "django-db"
        except ImportError:
            esperado = "redis://localhost:6379/0"

        out = _run_settings_snippet("print(settings.CELERY_RESULT_BACKEND)")
        assert out == esperado


class TestCeleryResultBackendDjangoDb:
    def test_usa_django_db_quando_django_celery_results_instalado(self):
        try:
            import django_celery_results  # noqa: F401
        except ImportError:
            import pytest

            pytest.skip(
                "django_celery_results ainda não instalado (dependência da task 69)"
            )

        out = _run_settings_snippet(
            "print(settings.CELERY_RESULT_BACKEND); "
            "print('django_celery_results' in settings.INSTALLED_APPS)"
        )
        lines = out.splitlines()
        assert lines[0] == "django-db"
        assert lines[1] == "True"
