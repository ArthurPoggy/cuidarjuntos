# Guia de Testes — CuidarJuntos

> Documento vivo: a cada lote de tarefas concluído (ver `PRIORIDADES_TODO.md`), adicione uma nova seção aqui seguindo o mesmo padrão. Não apague seções antigas — isso é o histórico de como verificar cada entrega.
>
> Última atualização: 2026-08-09 — lote P1 (15 tarefas, PRs #44–#58, todas mescladas em `desenvolvimento`).

---

## Como usar este guia

Cada tarefa tem duas formas de verificação:

1. **Automatizada** — o comando exato de teste (backend Django ou frontend Jest) que cobre aquela tarefa especificamente. Rode isso primeiro; é rápido e não depende de configurar dados manualmente.
2. **Manual** — passo a passo na interface (app mobile/web ou admin) pra ver a funcionalidade funcionando de verdade, do jeito que um usuário real usaria.

Rode a automatizada sempre. A manual vale a pena principalmente quando: (a) é a primeira vez que você olha aquela feature, (b) a automatizada passou mas você quer confirmar visualmente, ou (c) está investigando um bug relatado.

### Setup local (backend)

```bash
cd C:\programation\cuidarjuntos
python manage.py migrate
python manage.py createsuperuser   # se ainda não tiver um usuário admin
python manage.py runserver
```

### Setup local (frontend)

```bash
cd C:\programation\cuidarjuntos\frontend
npm install
npm start          # abre o menu do Expo — aperte "w" pra web, ou escaneie o QR com o Expo Go
```

Variáveis de ambiente: copie `frontend/.env.example` para `frontend/.env` e ajuste `EXPO_PUBLIC_API_URL` se o backend não estiver em `http://localhost:8000`.

### Rodando toda a suíte de uma vez

```bash
# Backend — tudo
python manage.py test

# Backend — só as áreas tocadas no lote P1
python manage.py test care.tests api.tests.test_care api.tests.test_admin_records

# Frontend — tudo
cd frontend && npx jest

# Frontend — typecheck (gate obrigatório antes de qualquer PR)
cd frontend && npx tsc --noEmit -p tsconfig.json
```

**Gotcha conhecido:** rodando a suíte completa do backend localmente (Python 3.14 + Django 5.1), ~13 testes que renderizam template HTML server-rendered falham com `AttributeError: 'super' object has no attribute 'dicts'`. Isso é uma incompatibilidade do ambiente local, não uma regressão — não é sobre o código que você acabou de mexer. Se o número de erros bater com esse baseline (13), está tudo certo.

---

## Lote P1 — Exclusão de registros / auditoria admin

### #92 — Excluir registro mantendo histórico para auditoria (soft delete)
**O quê:** `CareRecord` ganhou `deleted_at`/`deleted_by`; excluir um registro (por qualquer via) marca esses campos em vez de apagar a linha do banco. `CareRecord.objects` (manager padrão) esconde os deletados automaticamente; `CareRecord.all_objects` dá acesso a todos, incluindo deletados.

- **PR:** [#46](https://github.com/ArthurPoggy/cuidarjuntos/pull/46)
- **Automatizado:**
  ```bash
  python manage.py test care.tests.CareRecordSoftDeleteTests
  ```
- **Manual:**
  1. Faça login no app, crie um registro qualquer (ex.: um remédio).
  2. Exclua o registro pela tela de detalhe.
  3. Confirme que ele some da lista/dashboard imediatamente.
  4. No Django Admin (`/admin/`), abra `Care records`, filtre/procure pelo registro — ele deve aparecer lá com `Removido em` e `Removido por` preenchidos (o admin usa `all_objects`, então mostra os deletados para auditoria).

### #93 — API: superuser pode excluir qualquer registro (cross-group)
**O quê:** `CareRecordViewSet.destroy`/`cancel_following` passam a buscar em `CareRecord.objects.all()` quando `request.user.is_superuser`, em vez de restringir ao grupo do usuário.

- **PR:** [#47](https://github.com/ArthurPoggy/cuidarjuntos/pull/47)
- **Automatizado:**
  ```bash
  python manage.py test api.tests.test_cross_group_isolation
  ```
- **Manual:** precisa de 2 grupos/pacientes diferentes.
  1. Crie um registro no Grupo A (usuário comum).
  2. Faça login como superuser (`is_superuser=True`, via `createsuperuser` ou Django Admin).
  3. Pela API (`DELETE /api/v1/records/{id}/`) ou pela aba Registros do admin (ver #90), exclua o registro do Grupo A mesmo sem pertencer a ele.
  4. Um usuário comum de outro grupo, sem ser superuser, deve continuar recebendo 403 ao tentar o mesmo.

### #90 — Aba "Registros" na tela do admin
**O quê:** `AdminOverviewScreen` ganhou um tab switcher (Usuários / Registros). A aba Registros lista todos os registros do sistema com opção de excluir cada um.

- **PR:** [#48](https://github.com/ArthurPoggy/cuidarjuntos/pull/48)
- **Automatizado:**
  ```bash
  cd frontend && npx jest src/screens/__tests__/AdminOverviewScreen.records.test.tsx
  ```
- **Manual:**
  1. Login como superuser no app.
  2. Abra a tela de Admin → deve aparecer duas abas no topo: "Usuários" e "Registros".
  3. Toque em "Registros" — deve listar registros de todos os grupos (paciente, tipo, status, data).
  4. Toque em excluir num item — deve pedir confirmação (ver #89) e, ao confirmar, sumir da lista sem fechar a tela.

### #91 — Testes da exclusão de registros pelo admin
**O quê:** cobertura fim a fim (permissão + soft delete + visibilidade) do fluxo de exclusão administrativa.

- **PR:** [#49](https://github.com/ArthurPoggy/cuidarjuntos/pull/49)
- **Automatizado:**
  ```bash
  python manage.py test api.tests.test_admin_records
  ```
- **Manual:** não há UI própria — é cobertura de teste. Rodar o comando acima com `-v 2` mostra cada cenário coberto (superuser exclui alheio, usuário comum não pode, dono pode, 401/403 sem login, etc.).

### #88 — Integrar exclusão de registros no app
**O quê:** botão "Excluir" na tela de detalhe do registro, visível só para o dono do registro ou usuário com `profile.role === 'ADMIN'`.

- **PR:** [#44](https://github.com/ArthurPoggy/cuidarjuntos/pull/44)
- **Automatizado:**
  ```bash
  cd frontend && npx jest src/screens/__tests__/RecordDetailScreen.test.tsx
  ```
- **Manual:**
  1. Login como usuário comum, abra um registro que você mesmo criou → botão "Excluir" deve aparecer.
  2. Abra um registro criado por outra pessoa (sem ser ADMIN) → botão não deve aparecer.
  3. Login como usuário com `role=ADMIN` → botão deve aparecer em qualquer registro, mesmo não sendo o dono.

### #89 — Modal de confirmação para ações destrutivas
**O quê:** `ConfirmModal`, componente reutilizável que substitui o `Alert.alert` nativo para pedir confirmação antes de excluir.

- **PR:** [#45](https://github.com/ArthurPoggy/cuidarjuntos/pull/45)
- **Automatizado:**
  ```bash
  cd frontend && npx jest src/components/__tests__/ConfirmModal.test.tsx src/screens/__tests__/RecordDetailScreen.test.tsx
  ```
- **Manual:**
  1. Toque em "Excluir" em qualquer registro (tela de detalhe ou aba Registros do admin).
  2. Deve aparecer um modal centralizado (não o alerta nativo do sistema) perguntando "Tem certeza que deseja excluir este registro?", com botões vermelho (confirmar) e secundário (cancelar).
  3. Cancelar deve fechar o modal sem excluir nada. Confirmar deve excluir e remover o item da lista.

---

## Lote P1 — Exportação: filtros e melhorias

> Todos os itens abaixo mexem em `care/exporters.py`, `api/views/care.py::export_csv` e/ou `frontend/src/screens/ExportScreen.tsx`. Pra testar manualmente qualquer exportação: app → menu → Exportar.

### #82 — API: filtrar exportação por cuidador
- **PR:** [#50](https://github.com/ArthurPoggy/cuidarjuntos/pull/50)
- **Automatizado:** `python manage.py test api.tests.test_care.ExportCSVTests` (métodos `test_export_filtra_por_assigned_to*`)
- **Manual:** `GET /api/v1/export/csv/?assigned_to=<id>` deve retornar só registros atribuídos àquele cuidador.

### #83 — API: filtrar exportação por status
- **PR:** [#51](https://github.com/ArthurPoggy/cuidarjuntos/pull/51)
- **Automatizado:** `python manage.py test api.tests.test_care.ExportCSVTests` (métodos `test_export_*status*`)
- **Manual:** `GET /api/v1/export/csv/?status=done` (ou `pending`/`missed`) filtra corretamente; valor inválido ou vazio retorna tudo, sem quebrar.

### #79 — Filtrar exportação por categoria de cuidado (UI)
- **PR:** [#52](https://github.com/ArthurPoggy/cuidarjuntos/pull/52)
- **Automatizado:** `cd frontend && npx jest src/screens/__tests__/ExportScreen.test.tsx`
- **Manual:** na tela Exportar, toque em 2+ categorias (chips) — só elas devem entrar no CSV gerado. Sem nenhuma selecionada, todas entram.

### #80 — Filtrar exportação por status (UI)
- **PR:** [#53](https://github.com/ArthurPoggy/cuidarjuntos/pull/53)
- **Automatizado:** `cd frontend && npx jest src/screens/__tests__/ExportScreen.test.tsx`
- **Manual:** na tela Exportar, toque num status (pill "Pendente"/"Realizada"/"Não realizado") — exportação reflete o filtro. Tocar de novo volta pra "Todos".

### #78 — Corrigir filtro de datas no Exportar
**O quê:** bug real de off-by-one em `_resolve_export_period` — períodos predefinidos ("últimos 7 dias" etc.) incluíam um dia a mais que o anunciado.

- **PR:** [#54](https://github.com/ArthurPoggy/cuidarjuntos/pull/54)
- **Automatizado:** `python manage.py test care.tests.ExportPeriodFilterTests`
- **Manual:** exporte com "Últimos 7 dias" e confira manualmente que o intervalo tem exatamente 7 dias (hoje até 6 dias atrás), não 8.

### #81 — Testes dos novos filtros de exportação
- **PR:** [#55](https://github.com/ArthurPoggy/cuidarjuntos/pull/55)
- **Automatizado:** `python manage.py test api.tests.test_care.ExportCSVTests` (cobre combinações de status + cuidador + categoria + data)
- **Manual:** não há UI própria — cobertura de teste combinando os filtros acima.

### #84 — Rodapé com metadados no DOCX exportado
**O quê:** rodapé real de página (via `section.footer`) no DOCX, com data/hora de geração e quem gerou.

- **PR:** [#56](https://github.com/ArthurPoggy/cuidarjuntos/pull/56)
- **Automatizado:** `python manage.py test care.tests.DocxPageFooterMetadataTests`
- **Manual:** exporte em DOCX, abra o arquivo no Word/LibreOffice, role até o fim de qualquer página — deve ter um rodapé com "Geração: DD/MM/AAAA HH:MM" e "Gerado por: <seu nome>".

### #86 — Resumo estatístico no início dos exports
**O quê:** bloco de estatísticas (totais por status, por categoria) antes da tabela de registros, em todos os formatos.

- **PR:** [#57](https://github.com/ArthurPoggy/cuidarjuntos/pull/57)
- **Automatizado:** `python manage.py test care.tests.ExportMetadataSummaryCountsTests care.tests.ExportSummarySectionRenderingTests care.tests.AdminExportSummaryCountsIntegrationTests care.tests.AdminExportConsolidatedSummaryCountsIntegrationTests`
- **Manual:**
  - **CSV:** abra em editor de texto — as primeiras linhas começam com `#` (comentário) com o resumo; a tabela de dados vem depois.
  - **XLSX:** deve ter uma aba **"Resumo"** (além de "Registros") com as contagens.
  - **PDF/DOCX (múltiplos tipos selecionados):** deve ter uma seção "Resumo Geral da Exportação" com quebra por tipo e por status, antes das seções individuais.

### #87 — Capa com paciente e período nos exports
**O quê:** título do documento, nome do paciente e período aparecem antes da tabela — **unificado no mesmo formato do #86** (mesma seção de resumo, sem aba/seção duplicada — ver nota de resolução de conflito abaixo).

- **PR:** [#58](https://github.com/ArthurPoggy/cuidarjuntos/pull/58)
- **Automatizado:** `python manage.py test care.tests.CsvXlsxExportCoverPageTests`
- **Manual:**
  - **CSV:** a primeira linha de comentário (`#`) deve ser `# Título do documento: Relatório de registros de cuidado`, seguida das demais linhas de resumo (paciente, período, etc.).
  - **XLSX:** aba "Resumo" deve ter o título em destaque (negrito, fonte maior) na primeira linha, mesclado nas colunas A e B.
  - **PDF/DOCX:** título e "Cuidar Juntos" já apareciam no topo antes desta tarefa — confirme que não duplicou.

> **Nota de integração #86 + #87:** os dois PRs implementaram formatos incompatíveis de resumo/capa (um-coluna-comentário vs. duas-colunas). Resolvido mantendo o formato do #86 (já mesclado) e adaptando o #87 pra usar a mesma seção (`ExportMetadata.summary_rows()`, agora com parâmetro `include_title`). Se no futuro alguém for mexer em `summary_rows()` ou nas funções `export_as_*`, vale rodar `care.tests.CsvXlsxExportCoverPageTests` **junto** com os testes do #86 pra não reabrir esse conflito.

---

## Lote P2 — Automação e agendamento

### #62 — Agendar envio do relatório toda segunda às 08h
**O quê:** management command `setup_schedules` (`python manage.py setup_schedules`) que cria/atualiza, de forma idempotente, o agendamento do relatório semanal via `django-celery-beat`: um único `CrontabSchedule` (toda segunda-feira às 08h, fuso `America/Sao_Paulo`) e, para cada `CareGroup` existente, um `PeriodicTask` (`send-weekly-report-group-<id>`) apontando para a task `api.tasks.send_weekly_report` com `args=[group_id]`. A nova task `send_weekly_report(group_id)` envia o resumo semanal (realizados/não realizados dos últimos 7 dias) só para os membros daquele grupo.

  **Substitui** o agendamento fixo antigo `notify-weekly-summary` (segunda às 09h, em `CELERY_BEAT_SCHEDULE`, chamando `api.tasks.notify_weekly_summary` para todos os grupos de uma vez): essa entrada foi removida das configurações do Celery Beat para não duplicar a notificação semanal do usuário. A função `notify_weekly_summary` e seus testes continuam no código por ora, só deixaram de ser agendados automaticamente.

- **Automatizado:** `python manage.py test api.tests.test_setup_schedules api.tests.test_send_weekly_report`
- **Manual:**
  1. Rode `python manage.py migrate` (aplica as migrations do `django_celery_beat`, agora em `INSTALLED_APPS`).
  2. Rode `python manage.py setup_schedules` — deve imprimir quantas `PeriodicTask`s foram criadas/atualizadas.
  3. No Django Admin, em **Periodic Tasks**, confira que existe um `PeriodicTask` por grupo de cuidado, todos usando o mesmo `Crontab Schedule` (segunda-feira, 08:00, America/Sao_Paulo) e apontando para `api.tasks.send_weekly_report`.
  4. Rode o comando de novo — a lista de `PeriodicTask`s não deve duplicar (mesma contagem).
  5. Crie um novo grupo e rode o comando outra vez — o novo grupo deve ganhar seu próprio `PeriodicTask`.

---

## Checklist rápido pós-merge (rodar sempre, qualquer lote)

```bash
# 1. Migrações em dia
python manage.py makemigrations --check --dry-run

# 2. Backend
python manage.py test

# 3. Frontend — tipos
cd frontend && npx tsc --noEmit -p tsconfig.json

# 4. Frontend — testes
cd frontend && npx jest
```

Se os 4 passarem (ou só falharem no gotcha conhecido do Python 3.14, ver acima), está seguro pra considerar o lote validado.

---

## Como adicionar o próximo lote a este guia

1. Copie o padrão de uma tarefa acima (O quê / PR / Automatizado / Manual).
2. Um bloco por tarefa do Trello, agrupado pelo mesmo "grupo de contexto" usado em `PRIORIDADES_TODO.md`.
3. Sempre que resolver um conflito de merge não-trivial entre duas tarefas do mesmo lote (como o #86/#87), documente como nota — evita reabrir o mesmo problema depois.
4. Atualize a data em "Última atualização" no topo.
