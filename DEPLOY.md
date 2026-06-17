# Auto-deploy no PythonAnywhere (webhook do GitHub → branch `main`)2

Sempre que algo entra na branch `main`, o GitHub chama um webhook no próprio
Django, que valida a assinatura e dispara o `deploy.sh`. O script faz
`git reset --hard origin/main`, instala dependências, roda `migrate` +
`collectstatic` e recarrega o web app.

## Peças

| Arquivo | Papel |
|---|---|
| `cuidarjuntos/deploy_webhook.py` | View que recebe o webhook, valida HMAC e dispara o deploy desacoplado do worker |
| `cuidarjuntos/urls.py` | Rota `POST /deploy-hook/` |
| `deploy.sh` | Faz o deploy de fato; "toca" o WSGI para recarregar |

> O banco `db.sqlite3` está no `.gitignore`, então o `git reset --hard` do
> deploy **não sobrescreve os dados de produção**.

---

## 1. Configurar o `deploy.sh` no servidor

Confirme os caminhos no topo do `deploy.sh` (ou defina via variáveis de
ambiente). Os defaults assumem o usuário `tuzinhorisonho`:

```bash
PROJECT_DIR=/home/tuzinhorisonho/cuidarjuntos
VENV_DIR=/home/tuzinhorisonho/.virtualenvs/cuidarjuntos
BRANCH=main
WSGI_FILE=/var/www/tuzinhorisonho_pythonanywhere_com_wsgi.py
```

Descubra os valores reais num console Bash do PythonAnywhere:

```bash
ls ~                              # nome da pasta do projeto
echo $VIRTUAL_ENV                 # caminho do virtualenv (com ele ativado)
ls /var/www/                      # nome exato do arquivo _wsgi.py
```

## 2. Definir o segredo do webhook (no servidor)

Gere um segredo forte e deixe-o disponível **para o processo do web app** e
**para o seu shell**. No PythonAnywhere, a forma mais simples é exportá-lo no
arquivo WSGI de `/var/www/..._wsgi.py`, **antes** de `get_wsgi_application()`:

```python
import os
os.environ["DEPLOY_WEBHOOK_SECRET"] = "COLE_AQUI_UM_SEGREDO_LONGO"
# os.environ["DEPLOY_BRANCH"] = "main"   # opcional (default já é main)
```

Gere um segredo, por exemplo:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

> Guarde esse valor — você vai colá-lo igual no GitHub no passo 4.

## 3. Recarregar o web app uma vez

Depois de subir esses arquivos para a `main` e fazer um `git pull` manual
inicial no servidor, clique em **Reload** no painel Web do PythonAnywhere
para que a rota `/deploy-hook/` e o segredo passem a valer.

## 4. Criar o webhook no GitHub

No repositório → **Settings → Webhooks → Add webhook**:

- **Payload URL:** `https://tuzinhorisonho.pythonanywhere.com/deploy-hook/`
- **Content type:** `application/json`
- **Secret:** o mesmo valor do passo 2
- **SSL verification:** Enable
- **Which events:** *Just the push event*
- **Active:** ✓

O GitHub envia um `ping` na criação — a resposta deve ser **200** com
`{"ok": true, "pong": true}`.

## 5. Testar

```bash
git checkout main && git commit --allow-empty -m "test deploy" && git push
```

Acompanhe no servidor:

```bash
tail -f /home/tuzinhorisonho/cuidarjuntos/deploy.log
```

Você deve ver o ciclo `Iniciando deploy ... Deploy concluido`.

---

## Comportamento e segurança

- **Só a branch `main` dispara deploy.** Pushes em outras branches recebem
  `200 {"ignored_ref": ...}` e são ignorados.
- **Assinatura obrigatória.** Sem o header `X-Hub-Signature-256` válido, a
  resposta é `403`. Sem segredo configurado no servidor, é `503` (hook inativo).
- **Sem segredo no repositório.** O segredo vive só em variável de ambiente
  no servidor e nas configurações do webhook no GitHub.
- **Deploy desacoplado.** A view responde na hora; o `deploy.sh` roda em
  processo próprio e sobrevive ao reload do WSGI.

## Solução de problemas

| Sintoma | Causa provável |
|---|---|
| Webhook retorna 503 | `DEPLOY_WEBHOOK_SECRET` não está no ambiente do web app (revise o WSGI e dê Reload) |
| Webhook retorna 403 | Segredo do GitHub ≠ segredo do servidor |
| 200 mas nada acontece | Push não foi na `main`, ou `deploy.sh` falhou — veja `deploy.log` |
| `deploy.log` mostra erro de path | Ajuste `PROJECT_DIR` / `VENV_DIR` / `WSGI_FILE` no `deploy.sh` |
| App não recarrega | `WSGI_FILE` errado, ou sem permissão de `touch` nele |
