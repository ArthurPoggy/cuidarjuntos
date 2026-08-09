"""
Django settings for cuidarjuntos project — PRODUÇÃO (PythonAnywhere)
"""

import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Obrigatorio via env var (sem fallback): a chave anterior era o placeholder
# "django-insecure-..." gerado pelo scaffold do Django, igual ao de
# desenvolvimento, e ficou exposta no historico do repositorio — deve ser
# tratada como comprometida. Gere uma nova com
# `python -c "import secrets; print(secrets.token_hex(50))"` e defina
# DJANGO_SECRET_KEY no ambiente do servidor (nunca em codigo/commit).
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# DJANGO_DEBUG permite religar DEBUG explicitamente (ex.: diagnostico
# temporario em producao), mas o default sem a env var e sempre False.
DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"

# Dominio real de producao (custom domain no PythonAnywhere).
PRODUCTION_DOMAIN = "app.cuidarjuntos.com.br"

# Dominio unico do app (Vercel), que faz proxy do acesso desktop para este
# backend (ver frontend/middleware.ts). Configuravel via env var para poder
# trocar sem precisar editar codigo quando o dominio for atualizado.
UNIFIED_WEB_DOMAIN = os.environ.get("UNIFIED_WEB_DOMAIN", "cuidarjuntos.vercel.app")

ALLOWED_HOSTS = [
    PRODUCTION_DOMAIN,
    "tuzinhorisonho.pythonanywhere.com",
    UNIFIED_WEB_DOMAIN,
    "localhost",
    "127.0.0.1",
    "testserver",
]

# DJANGO_ALLOWED_HOSTS permite acrescentar hosts adicionais (ex.: o dominio
# padrao *.onrender.com de um servico Render, usado antes de um dominio
# customizado apontar pra ele) sem precisar editar codigo. Formato: lista
# separada por virgula. Sem a env var, mantem so os hosts fixos acima.
_extra_allowed_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
for _host in _extra_allowed_hosts.split(","):
    _host = _host.strip()
    if _host and _host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_host)

# E-mail: por padrao usa o backend de console (nenhum e-mail e enviado de
# fato) ate que credenciais SMTP reais sejam configuradas via env vars. Isso
# evita "credenciais mortas": se EMAIL_HOST_USER/EMAIL_HOST_PASSWORD forem
# preenchidas no ambiente, o backend passa a ser SMTP de verdade.
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "arthur.poggy2005@gmail.com")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True") == "True"

if EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = f"CuidarJuntos <{EMAIL_HOST_USER}>"
SERVER_EMAIL = EMAIL_HOST_USER
EMAIL_SUBJECT_PREFIX = "[CuidarJuntos] "
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "care",
    "accounts",
    # DRF + API
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "api",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cuidarjuntos.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "care.context_processors.current_group",
            ],
        },
    },
]

WSGI_APPLICATION = "cuidarjuntos.wsgi.application"

CSRF_TRUSTED_ORIGINS = [
    f"https://{PRODUCTION_DOMAIN}",
    "https://tuzinhorisonho.pythonanywhere.com",
    f"https://{UNIFIED_WEB_DOMAIN}",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            "timeout": 20,
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "care:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "api.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        # Rate limit do endpoint de chat com IA (por usuário autenticado).
        "chat": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CuidarJuntos API",
    "DESCRIPTION": "API REST para o app mobile CuidarJuntos",
    "VERSION": "1.0.0",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# CORS_ALLOWED_ORIGINS (lista separada por virgula) restringe as origens
# aceitas quando definida. Sem a env var, mantem o comportamento atual
# (libera todas as origens) para nao quebrar o deploy real existente que
# ainda nao define essa variavel.
_cors_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _cors_allowed_origins:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [
        origin.strip() for origin in _cors_allowed_origins.split(",") if origin.strip()
    ]
else:
    CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
from celery.schedules import crontab  # noqa: E402

_REDIS_URL = os.environ.get(
    "CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://localhost:6379/0")
)
CELERY_BROKER_URL = _REDIS_URL
CELERY_RESULT_BACKEND = _REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = False

CELERY_BEAT_SCHEDULE = {
    "notify-upcoming-records": {
        "task": "api.tasks.notify_upcoming_records",
        "schedule": 30 * 60,  # a cada 30 minutos
    },
    "notify-weekly-summary": {
        "task": "api.tasks.notify_weekly_summary",
        # Segunda-feira às 09:00 (fuso do projeto: America/Sao_Paulo)
        "schedule": crontab(hour=9, minute=0, day_of_week=1),
    },
}

# ---------------------------------------------------------------------------
# Anthropic (assistente de IA)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
CHAT_ASSISTANT_ENABLED = os.environ.get("CHAT_ASSISTANT_ENABLED", "0") == "1"
