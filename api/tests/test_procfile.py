"""Garante que o Procfile de producao sobe worker e scheduler do Celery.

Sem essas entradas, o Celery beat nunca dispara as tarefas periodicas
(ex.: notificacoes de cuidado) e nenhum worker consome a fila em producao.
"""
import os

from django.test import SimpleTestCase


class ProcfileCeleryEntriesTests(SimpleTestCase):
    def setUp(self):
        procfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "Procfile"
        )
        self.assertTrue(
            os.path.isfile(procfile_path),
            f"Procfile nao encontrado em {procfile_path}",
        )
        with open(procfile_path, encoding="utf-8") as fh:
            self.lines = [line.rstrip("\n") for line in fh]

    def test_worker_process_definido(self):
        self.assertIn(
            "worker: celery -A cuidarjuntos worker --concurrency=2 -l info",
            self.lines,
        )

    def test_beat_process_definido(self):
        self.assertIn(
            "beat: celery -A cuidarjuntos beat -l info "
            "--scheduler django_celery_beat.schedulers:DatabaseScheduler",
            self.lines,
        )
