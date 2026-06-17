"""
Webhook de auto-deploy disparado pelo GitHub.

Fluxo:
    GitHub (push na branch main) -> POST /deploy-hook/
        -> valida a assinatura HMAC-SHA256 (X-Hub-Signature-256)
        -> confere se o push foi na branch alvo (DEPLOY_BRANCH, default "main")
        -> dispara deploy.sh de forma DESACOPLADA do worker web

O deploy roda em um processo próprio (start_new_session=True) justamente
porque o passo final do deploy.sh recarrega o web app — se rodasse dentro
do worker, ele se mataria no meio do caminho. A view responde 200 na hora
e o trabalho pesado segue em background, com log em deploy.log.
"""
import hashlib
import hmac
import json
import os
import subprocess
from pathlib import Path

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

BASE_DIR = Path(__file__).resolve().parent.parent
DEPLOY_SCRIPT = BASE_DIR / "deploy.sh"
DEPLOY_LOG = BASE_DIR / "deploy.log"
TARGET_BRANCH = os.environ.get("DEPLOY_BRANCH", "main")


def _valid_signature(secret: bytes, payload: bytes, header: str) -> bool:
    """Compara, em tempo constante, a assinatura enviada pelo GitHub."""
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@csrf_exempt
@require_POST
def github_deploy_hook(request):
    secret = os.environ.get("DEPLOY_WEBHOOK_SECRET", "")
    if not secret:
        # Sem segredo configurado no servidor, o hook fica inativo de propósito.
        return HttpResponse("Deploy hook nao configurado.", status=503)

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _valid_signature(secret.encode(), request.body, signature):
        return HttpResponseForbidden("Assinatura invalida.")

    event = request.headers.get("X-GitHub-Event", "")
    if event == "ping":
        # GitHub envia um "ping" ao criar o webhook.
        return JsonResponse({"ok": True, "pong": True})
    if event != "push":
        return JsonResponse({"ok": True, "ignored_event": event})

    try:
        ref = json.loads(request.body.decode()).get("ref", "")
    except (ValueError, UnicodeDecodeError):
        ref = ""
    if ref != f"refs/heads/{TARGET_BRANCH}":
        return JsonResponse({"ok": True, "ignored_ref": ref})

    if not DEPLOY_SCRIPT.exists():
        return HttpResponse("deploy.sh nao encontrado.", status=500)

    # Dispara o deploy desacoplado do worker (sobrevive ao reload do WSGI).
    log = open(DEPLOY_LOG, "ab")
    subprocess.Popen(
        ["bash", str(DEPLOY_SCRIPT)],
        stdout=log,
        stderr=log,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(BASE_DIR),
    )
    return JsonResponse({"ok": True, "deploying": TARGET_BRANCH})
