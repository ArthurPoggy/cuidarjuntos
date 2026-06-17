#!/usr/bin/env bash
#
# Deploy automatico do CuidarJuntos no PythonAnywhere.
# Disparado pelo webhook do GitHub (ver cuidarjuntos/deploy_webhook.py).
#
# Roda DESACOPLADO do worker web e loga em deploy.log. O passo final
# "toca" o arquivo WSGI, que e como o PythonAnywhere recarrega o web app.
#
set -euo pipefail

# ---------------------------------------------------------------------------
# CONFIG — confirme/ajuste para o seu ambiente no PythonAnywhere.
# Pode sobrescrever via variaveis de ambiente sem editar este arquivo.
# ---------------------------------------------------------------------------
PROJECT_DIR="${PROJECT_DIR:-/home/tuzinhorisonho/cuidarjuntos}"
VENV_DIR="${VENV_DIR:-/home/tuzinhorisonho/.virtualenvs/cuidarjuntos}"
BRANCH="${DEPLOY_BRANCH:-main}"
WSGI_FILE="${WSGI_FILE:-/var/www/tuzinhorisonho_pythonanywhere_com_wsgi.py}"
# ---------------------------------------------------------------------------

ts() { date "+%Y-%m-%d %H:%M:%S"; }
echo "===== [$(ts)] Iniciando deploy (branch $BRANCH) ====="

cd "$PROJECT_DIR"

# Busca o que ha de novo na branch alvo.
git fetch --prune origin "$BRANCH"
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [ "$LOCAL" = "$REMOTE" ]; then
  echo "[$(ts)] Nada novo (HEAD ja em $REMOTE). Encerrando."
  exit 0
fi

# Alinha o codigo local exatamente ao remoto.
# O db.sqlite3 esta no .gitignore, entao o reset NAO toca no banco de producao.
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"
echo "[$(ts)] Codigo atualizado: ${LOCAL:0:8} -> ${REMOTE:0:8}"

# Ativa o virtualenv.
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Dependencias (idempotente; rapido quando nada mudou).
pip install -r requirements.txt

# Migracoes e arquivos estaticos.
python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Recarrega o web app: o PythonAnywhere recarrega ao "tocar" o WSGI.
touch "$WSGI_FILE"

echo "===== [$(ts)] Deploy concluido. Web app recarregado. ====="
