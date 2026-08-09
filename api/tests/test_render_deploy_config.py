"""
Testes de configuracao de deploy (render.yaml).

Garante que o Redis e os workers do Celery (worker + beat) estao
declarados corretamente para producao, conforme card #59
("Configurar Redis em producao").
"""

import os
import unittest

import yaml

RENDER_YAML_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "render.yaml",
)


def _load_render_config():
    with open(RENDER_YAML_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _services_by_type(config, service_type):
    return [s for s in config["services"] if s.get("type") == service_type]


class RenderYamlRedisCeleryTests(unittest.TestCase):
    def test_render_yaml_existe(self):
        self.assertTrue(
            os.path.isfile(RENDER_YAML_PATH), "render.yaml deve existir na raiz do repo"
        )

    def test_declara_servico_redis(self):
        config = _load_render_config()
        redis_services = _services_by_type(config, "redis")

        self.assertEqual(
            len(redis_services), 1, "deve haver exatamente um servico type: redis"
        )

        redis_service = redis_services[0]
        self.assertEqual(redis_service["name"], "cuidarjuntos-redis")
        self.assertEqual(redis_service["plan"], "free")

    def test_declara_dois_workers_celery(self):
        config = _load_render_config()
        workers = _services_by_type(config, "worker")

        self.assertEqual(
            len(workers), 2, "deve haver dois servicos type: worker (celery worker e beat)"
        )

        start_commands = [w.get("startCommand", "") for w in workers]

        self.assertTrue(
            any("celery" in cmd and "worker" in cmd for cmd in start_commands),
            "um worker deve rodar 'celery ... worker'",
        )
        self.assertTrue(
            any("celery" in cmd and "beat" in cmd for cmd in start_commands),
            "um worker deve rodar 'celery ... beat'",
        )

    def test_workers_apontam_celery_broker_url_para_redis_declarado(self):
        config = _load_render_config()
        workers = _services_by_type(config, "worker")
        self.assertTrue(workers)

        for worker in workers:
            env_vars = {ev["key"]: ev for ev in worker.get("envVars", [])}
            self.assertIn(
                "CELERY_BROKER_URL",
                env_vars,
                f"worker {worker.get('name')} precisa de CELERY_BROKER_URL",
            )

            broker_env = env_vars["CELERY_BROKER_URL"]
            from_service = broker_env.get("fromService")
            self.assertIsNotNone(
                from_service,
                f"CELERY_BROKER_URL de {worker.get('name')} deve usar fromService",
            )
            self.assertEqual(from_service.get("type"), "redis")
            self.assertEqual(from_service.get("name"), "cuidarjuntos-redis")

    def test_web_service_tambem_usa_celery_broker_url_do_redis(self):
        config = _load_render_config()
        web_services = _services_by_type(config, "web")
        self.assertTrue(web_services, "deve existir um servico type: web")

        for web in web_services:
            env_vars = {ev["key"]: ev for ev in web.get("envVars", [])}
            self.assertIn("CELERY_BROKER_URL", env_vars)
            from_service = env_vars["CELERY_BROKER_URL"].get("fromService")
            self.assertIsNotNone(from_service)
            self.assertEqual(from_service.get("type"), "redis")
            self.assertEqual(from_service.get("name"), "cuidarjuntos-redis")
