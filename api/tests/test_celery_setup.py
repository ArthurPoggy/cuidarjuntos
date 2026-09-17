from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase


class CelerySetupTests(SimpleTestCase):
    """Cobre os critérios de aceitação do agendador de tarefas (Celery)."""

    def test_celery_app_configurado_corretamente(self):
        from cuidarjuntos.celery import app

        self.assertEqual(app.main, "cuidarjuntos")
        # app.conf.namespace guarda o namespace usado no config_from_object
        self.assertEqual(app.namespace, "CELERY")

    def test_celery_app_e_importado_no_init_do_projeto(self):
        import cuidarjuntos

        self.assertTrue(hasattr(cuidarjuntos, "celery_app"))
        self.assertIn("celery_app", cuidarjuntos.__all__)

    def test_django_celery_beat_instalado(self):
        self.assertIn("django_celery_beat", settings.INSTALLED_APPS)
        self.assertTrue(apps.is_installed("django_celery_beat"))

    def test_django_celery_results_instalado(self):
        self.assertIn("django_celery_results", settings.INSTALLED_APPS)
        self.assertTrue(apps.is_installed("django_celery_results"))
