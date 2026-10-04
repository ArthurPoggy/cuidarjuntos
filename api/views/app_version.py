"""Versão do sistema e política de atualização do app.

Fonte única da versão: arquivo `VERSION` na raiz do repositório (atualizado por
`scripts/bump-version.mjs` junto com os package.json e o app.json do frontend).

O app consulta este endpoint (público, sem login) ao abrir e compara com a sua
própria versão:
- app < `min_supported_version`  -> atualização obrigatória (`update_required`);
- app < `version`                -> atualização recomendada.

`MIN_SUPPORTED_APP_VERSION` e `APP_UPDATE_URL` vêm do ambiente, para subir a
versão mínima sem novo deploy de código quando a API quebrar compatibilidade.
Lê direto de `os.environ` para funcionar em settings.py e settings_production.py.
"""
import os
from pathlib import Path

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION"
FALLBACK_VERSION = "0.0.0"


def read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or FALLBACK_VERSION
    except OSError:
        return FALLBACK_VERSION


@api_view(["GET"])
@permission_classes([AllowAny])
def app_version_view(request):
    version = read_version()
    return Response({
        "version": version,
        "min_supported_version": os.environ.get("MIN_SUPPORTED_APP_VERSION", "1.0.0"),
        "update_url": os.environ.get("APP_UPDATE_URL", ""),
    })
