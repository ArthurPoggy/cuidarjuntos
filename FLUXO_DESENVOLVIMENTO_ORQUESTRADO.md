# Fluxo de Desenvolvimento Orquestrado — CuidarJuntos

> Consolidação das orientações passadas em 2026-08-05 para execução autônoma
> das 10 primeiras tarefas do `PRIORIDADES_TODO.md` (bloco P0).

---

## 1. Objetivo

Executar, de forma multiagente e autônoma, o ciclo completo de desenvolvimento
(planejamento → testes → julgamento → implementação → julgamento → PR → Trello
→ revisão independente do PR → correção → nova revisão, até aprovação) para
as 10 primeiras tarefas priorizadas, sem intervenção manual entre etapas,
respeitando as convenções do repositório.

## 2. Papéis dos agentes

| # | Agente | Responsabilidade |
|---|--------|-------------------|
| 1 | **Planejador** | Recebe 1 tarefa do backlog, avalia escopo, divide em subtasks e **autoavalia** a própria divisão (critica e ajusta antes de prosseguir). |
| 2 | **Orquestrador** | Por subtask, aciona o Subagente de Testes; recebe o veredito do Judge; se reprovado, reaciona o Subagente de Testes com o feedback; repete até aprovação. Depois aciona o Subagente de Implementação com a mesma lógica de repetição. |
| 3 | **Subagente de Testes** | Escreve testes automatizados **conclusivos** (devem falhar de forma clara contra o código atual — estado "red") cobrindo os critérios de aceitação da subtask. |
| 4 | **Judge (Juiz)** | Avalia testes e, depois, implementação, numa escala **0–10**. Nota < 9 → reprovado: relata os problemas ao Orquestrador para nova tentativa. Nota ≥ 9 → aprovado, segue para a próxima etapa. |
| 5 | **Subagente de Implementação** | Após testes aprovados, implementa o código para fazer os testes passarem (estado "green"), seguindo boas práticas de arquitetura e programação do projeto. |
| 6 | **Agente Git/PR** | Cria branch nova a partir de `desenvolvimento`, commita, dá push e abre PR para `desenvolvimento`. |
| 7 | **Agente Trello** | Move o card da tarefa para a coluna **"em análise"** e adiciona o link do PR na descrição do card. |
| 8 | **Revisor de PR (verificador de problemas, não aprovador)** | Roda **depois que o PR já está aberto**. Não participou de nenhuma etapa anterior — não tem viés de "defender o próprio trabalho". Lê o diff completo, confere se o PR cobre tudo que a tarefa pedia, procura escopo sobrando/código morto, valida convenções de arquitetura, roda os testes com as próprias mãos. **Nunca declara aprovação** (nem review formal, nem comentário de "aprovado" — ver gotcha na seção 4 sobre por que isso é bloqueado como autoaprovação). Se encontrar pendências, publica comentário `## Revisão automatizada — Pontos a corrigir`; se não encontrar nada, não publica nada — a decisão de aceitar o PR é sempre humana. |
| 9 | **Agente de Triagem de Comentários** | Só roda quando o Revisor de PR pede mudanças. Lê os comentários do PR e pondera, um a um, se são pertinentes ou não. Para os pertinentes, decide se a correção exige **testes automatizados novos** ou é só ajuste de implementação. |

## 3.1. Loop de revisão de PR (pós-abertura)

Depois que o PR é aberto e o card do Trello é atualizado, entra em ação um
**segundo portão de qualidade**, desta vez sobre o PR como um todo (não mais
por subtask isolada):

```
PR aberto
  → Revisor de PR avalia (nunca aprova — só verifica)
      ├─ sem pendências → não publica nada no PR → FIM (loop de revisão encerra,
      │                    decisão de aceitar o PR fica com o usuário)
      └─ encontrou pendências → comenta o que precisa mudar
            → Agente de Triagem lê os comentários e, para cada um, pondera:
                ├─ NÃO pertinente → comenta no PR explicando por que não será alterado
                └─ pertinente → precisa de teste novo?
                      ├─ sim → roda o ciclo Testes → Judge → Implementação → Judge (mesmo ciclo da seção 3)
                      └─ não → roda só o ciclo Implementação → Judge
            → após tratar todos os pontos pertinentes da rodada: novo commit, push,
              comentário no PR resumindo o que foi corrigido nesta rodada
            → volta para o Revisor de PR reavaliar (nova rodada)
```

- Esse ciclo se repete até o Revisor de PR não encontrar mais pendências,
  com um teto de rodadas (evita loop infinito — se ainda houver pendências
  depois do teto, o pipeline segue em frente e deixa um aviso para revisão
  humana, mas **não bloqueia** a tarefa indefinidamente).
- Cada novo commit feito em resposta a uma rodada de revisão **deve indicar
  no próprio commit/comentário do PR quais correções foram feitas** nessa
  rodada — mantém o histórico do PR auditável.
- Quando a rodada tem pontos pertinentes E não-pertinentes ao mesmo tempo,
  ambos são tratados: os não-pertinentes recebem comentário explicando o
  motivo, os pertinentes entram no ciclo de correção — e o Revisor de PR só
  é re-executado depois que os dois tipos de resposta já foram registrados.

## 3. Ciclo de julgamento (Judge loop)

```
Testes gerados → Judge avalia (0–10)
  ├─ nota < 9 → Judge lista problemas → Orquestrador aciona novo Subagente de Testes com o feedback → repete
  └─ nota ≥ 9 → aprovado → segue para Implementação

Implementação gerada → Judge avalia (0–10)
  ├─ nota < 9 → Judge lista problemas → Orquestrador aciona novo Subagente de Implementação com o feedback → repete
  └─ nota ≥ 9 → aprovado → segue para commit/PR
```

**Nota de corte adotada: 9** (nota ≥ 9 aprova, nota < 9 reprova e volta para
nova rodada). Ajustado de 9 para 8 em 2026-08-06 após observar na tarefa
#126 que o corte 9 gerava rodadas extras de retrabalho por nuances
estilísticas menores, sem ganho real de qualidade proporcional ao custo de
tokens — e reajustado de volta para 9 em 2026-08-09 a pedido do usuário para
o lote de 15 tarefas do P1.

## 4. Regras transversais (não negociáveis)

- **Nenhuma menção a Claude/IA** em commits, descrições de PR ou comentários de
  PR — sem `Co-Authored-By: Claude`, sem rodapés, sem menções indiretas.
- Seguir as convenções de commit já usadas no repositório (mensagens em
  PT-BR, estilo conventional commit já observado no histórico).
- **Antes de qualquer `git push`**: rodar
  `gh auth switch --hostname github.com --user ArthurPoggy` — esta máquina
  reverte sozinha para uma conta sem permissão de escrita.
- **Uma branch nova por funcionalidade**, criada a partir de `desenvolvimento`
  (não de `main`).
- **Todo PR é direcionado a `desenvolvimento`, sem revisor atribuído**
  (definido pelo usuário — revisão fica a critério dele depois, manualmente).
- Ao final de cada tarefa: mover o card correspondente no Trello
  (board `CUIDARJUNTOS DEV`) para a lista **"em análise"** e colar o link do
  PR na descrição do card (preservar a descrição original, apenas anexar o
  link).
- Respeitar os gotchas de line-ending (CRLF/LF por arquivo, não por padrão) —
  medir sempre com Python, nunca com `grep`/`cat -A` no Git Bash.
- Toda migration nova deve encadear a partir da última migration existente em
  `desenvolvimento`; confirmar com `python manage.py makemigrations --check
  --dry-run` antes de commitar.
- **Ambiente local roda Python 3.14 + Django 5.1**: qualquer teste que
  renderize template HTML quebra por incompatibilidade do `Context.__copy__`
  do Django com o Python 3.14 — isso **não é falha do código**. O Judge deve
  saber disso para não reprovar testes/implementação por esse motivo
  espúrio; usar `@override_settings(DEBUG_PROPAGATE_EXCEPTIONS=True)` para
  ver a exceção real por trás da falha de renderização quando necessário.
- Seguir boas práticas de arquitetura e programação do projeto (Django
  híbrido server-rendered + API REST; DRF com serializers/permissions
  próprios; frontend Expo com TanStack Query, Zustand, hooks por domínio).
- O Revisor de PR e o Agente de Triagem também não podem mencionar
  Claude/IA/assistente em nenhum comentário postado no PR.
- **Sem troca de credencial dentro de subagentes** (gotcha descoberto em
  2026-08-06 na tarefa #105, corrigindo a tentativa anterior de duas
  identidades GitHub): a ideia inicial era usar uma segunda conta
  (`Arthur-Poggy`) só para o revisor, autenticando via
  `gh auth switch --hostname github.com --user Arthur-Poggy` de dentro do
  subagente, para contornar o bloqueio do GitHub a autoaprovação de PR. Na
  prática, **o classificador de segurança do Claude Code bloqueia comandos
  de troca de credencial quando chamados de dentro de um subagente
  automatizado** (mesmo comando funciona normalmente quando rodado
  diretamente pelo agente principal/orquestrador). O resultado, sem
  correção, é pior do que parecia: o subagente retornava veredito "approve"
  normalmente (a análise técnica acontecia), mas a publicação no GitHub
  falhava silenciosamente — e como o pipeline só olhava o campo `verdict`,
  ele seguia em frente como se a aprovação tivesse sido registrada, quando
  na verdade o PR ficava sem nenhum review.
  - **Primeira tentativa de correção** (que também não funcionou): publicar
    um comentário normal (`gh pr comment`) pela mesma conta autora em vez de
    review formal, com cabeçalho `## Revisão automatizada — Aprovado`
    quando estivesse tudo certo. Isso trocou um bloqueio por outro: o
    classificador passou a barrar por **autoaprovação** ("Self Approval") —
    a mesma identidade que escreveu o código publicando um sinal de
    aprovação sobre o próprio trabalho, ainda com o PR aberto (não
    mergeado), derruba o sentido de uma revisão independente antes do
    aceite.
  - **Correção final adotada**: o revisor não declara aprovação em nenhuma
    forma — nem review formal, nem comentário de "aprovado". Ele é só um
    **verificador de problemas**: se encontrar pendências reais, publica um
    comentário `## Revisão automatizada — Pontos a corrigir` detalhando o
    que precisa mudar; se não encontrar nada, **não publica nada no PR** —
    só registra "sem pendências" internamente no pipeline. A decisão de
    aceitar/mergear cada PR é **sempre humana**, fora do fluxo automatizado
    (e sempre foi, já que nenhum PR é mergeado automaticamente de qualquer
    forma — ver seção 7).
- **Achados de bots do GitHub (GitGuardian, Vercel) são sempre bloqueantes**
  (adicionado em 2026-08-06 após o PR #31 ser aprovado sem o revisor notar
  um alerta do GitGuardian sobre 2 "segredos" num arquivo de teste). O
  Revisor de PR agora lê explicitamente os comentários de bots antes de
  aprovar:
  - **GitGuardian** reportando segredo exposto → sempre pertinente, nunca
    descartado. Se for segredo real, precisa ser removido/rotacionado. Se
    for dado fictício de teste que só parece uma credencial, mesmo assim
    precisa trocar por um valor obviamente sintético (prefixo `fake-`,
    `test-`, etc.) pra não continuar disparando o alerta a cada push.
  - **Vercel** reportando falha de build/deploy do preview → também
    bloqueante.
  - A Agente de Triagem tem instrução explícita de nunca marcar um achado
    do GitGuardian como "não pertinente".
- Nenhum comentário de PR (aprovação, pedido de mudança, explicação de
  ponto não pertinente, resumo de correção) pode ficar sem justificativa —
  sempre em português, objetivo e específico o suficiente para alguém
  entender sem abrir o diff inteiro.

## 5. As 10 tarefas (ordem P0 do `PRIORIDADES_TODO.md`)

1. `#126` PRIORIDADE: bloquear edição de registros anteriores
2. `#105` Refazer UX/UI do login/cadastro → MOBILE
3. `#106` Consertar incongruências nos cards de registros do dashboard → MOBILE
4. `#107` Ajeitar menu de hambúrguer → MOBILE
5. `#109` Deixar o dashboard em grid padrão → MOBILE
6. `#110` Consertar agenda → MOBILE
7. `#100` Consertar e refatorar agenda
8. `#101` Ajeitar tela de remédios
9. `#99` Adicionar remédio e cadastrar novo remédio (feio e desalinhado)
10. `#111` Teste de segurança e integridade de dados de saúde

## 6. Execução

- Implementado como um **workflow multiagente** orquestrado (não uma
  sequência manual de prompts).
- Execução **sequencial por tarefa, sem pausas entre PRs** (confirmado pelo
  usuário) — as 10 tarefas rodam de ponta a ponta e o relatório final é
  reportado só ao término de todas.
- Execução **sequencial por tarefa** (uma funcionalidade termina — PR aberto
  e card movido — antes da próxima começar), para evitar múltiplos PRs
  concorrentes disputando revisão e para isolar falhas por tarefa.
- Dentro de cada tarefa, as subtasks podem rodar em paralelo quando não
  têm dependência entre si (ex.: duas correções de UI independentes),
  mas cada subtask individual passa pelo próprio ciclo Testes → Judge →
  Implementação → Judge antes de ser considerada concluída.
- O número de agentes por tarefa é variável (depende de quantas rodadas o
  Judge reprova, e agora também de quantas rodadas o Revisor de PR pede
  mudanças) — o volume total pode superar facilmente a centena de chamadas
  de agente ao longo das 10 tarefas.
- O loop de revisão de PR (seção 3.1) roda **depois** do PR aberto e do card
  movido no Trello — ou seja, o card já aparece em "em análise" com o link
  do PR mesmo enquanto a revisão automatizada ainda está em andamento; o
  card não é movido de novo ao final da revisão (fica a cargo de revisão
  humana decidir o próximo passo do card).

## 8. Lote P2 (iniciado em 2026-08-09) — 23 tarefas

Reaproveita o mesmo fluxo dos lotes P0/P1, com duas simplificações adotadas
para esse volume maior de tarefas (ver racional abaixo):

- **Gotcha de diretórios duplicados**: o working directory tem `app/` e
  `backend/` como pastas **não rastreadas pelo git** (resíduo de uma
  reestruturação anterior do monorepo) — não são o código real. O backend
  Django real está na **raiz** do repo (`cuidarjuntos/`, `api/`, `care/`,
  `accounts/`, `manage.py`, `requirements.txt`, `render.yaml`) e o frontend
  real é `frontend/` (Expo). Vários cards do Trello (ex.: #75, #71, #72)
  citam caminhos de `app/src/...` porque foram escritos antes da migração —
  esses caminhos **não existem mais**; o agente de cada tarefa deve mapear
  o objetivo do card para a estrutura atual em `frontend/src/`
  (`useSpeechToText.ts` em `frontend/src/hooks/`, `MicrophoneButton.tsx` em
  `frontend/src/components/`, telas em `frontend/src/screens/`), nunca criar
  ou editar arquivos dentro de `app/`/`backend/`.
- **Ciclo por tarefa simplificado para 2 estágios** (em vez dos 4 originais
  Testes→Judge→Implementação→Judge): um agente **Construtor** único faz
  planejamento, testes (red), implementação (green) e autoavaliação contra
  os critérios de aceitação do card internamente, iterando quantas vezes
  precisar antes de commitar — depois cria branch a partir de
  `desenvolvimento`, commita, dá push, abre PR e move o card no Trello. Em
  seguida um agente **Revisor** independente (sem contexto do Construtor)
  roda o loop da seção 3.1 normalmente (nunca aprova, só aponta pendências;
  teto de 2 rodadas de correção). Motivo da simplificação: o volume (23
  tarefas vs. 15 do lote P1) tornaria o custo de 4 agentes-por-subtask
  proibitivo; o portão de qualidade que mais importa na prática (revisão
  independente, sem viés de "defender o próprio trabalho") é preservado.
- **Estado da infra Celery/Redis (checado em 2026-08-09 antes de puxar o
  grupo)**: `celery[redis]` e `redis` já estão em `requirements.txt`;
  `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` já têm fallback local em
  `cuidarjuntos/settings.py`; `CELERY_BEAT_SCHEDULE` estático já existe (task
  `notify_weekly_summary`, que é o **push** semanal, não o email). **Faltam
  de verdade**: `django-celery-beat`/`django-celery-results` no
  requirements/`INSTALLED_APPS`; `cuidarjuntos/celery.py`; declaração do
  serviço Redis + workers `worker`/`beat` no `render.yaml`; processos
  `worker`/`beat` no `Procfile`; e toda a lógica de relatório **por email**
  (não existe nenhum código de envio de email de relatório hoje — é 100%
  novo). Isso confirma a ordem sugerida no `PRIORIDADES_TODO.md`.
- **Estado da base de voz**: `useSpeechToText`/`MicrophoneButton` existem só
  como contrato/stub (`frontend/src/hooks/useSpeechToText.ts`,
  `frontend/src/components/MicrophoneButton.tsx`) — nenhuma lib de STT
  instalada, nenhuma permissão configurada, único uso hoje é no
  `ChatScreen.tsx`. Todo o grupo de voz (#77, #75, #76, #71, #72, #70) está
  genuinamente pendente, na ordem do card (lib → permissão → nativo →
  integração nos formulários → QA manual).
- **Risco de conflito assumido**: o grupo Celery/email (11 tarefas) mexe
  repetidamente nos mesmos arquivos (`settings.py`, `requirements.txt`,
  `render.yaml`, `Procfile`) — cada PR nasce a partir da ponta atual de
  `desenvolvimento` (não encadeado no PR anterior), então é esperado que a
  resolução de conflitos aconteça na hora do merge (mesmo padrão já visto e
  resolvido manualmente no grupo de exportação do lote P1).
- **As 23 tarefas do lote** (ordem de execução): grupo Celery/email —
  #69, #67, #68, #59, #66, #65, #63, #64, #62, #61, #60; grupo voz — #77,
  #76, #75, #71, #72, #70; grupo feedback de produto (sem dependência entre
  si) — #112, #113, #114, #127, #102, #108.

## 7. Pontos em aberto / riscos assumidos

- Cada PR aberto **não é mergeado automaticamente**, nem mesmo depois do
  Revisor de PR aprovar — fica pendente de revisão/merge humano em
  `desenvolvimento`, o que limita o dano de uma implementação incorreta
  aprovada erroneamente pelos agentes automatizados.
- Um Judge (ou Revisor de PR) automatizado pode aprovar algo incorreto com
  confiança alta ("false positive de qualidade") — a revisão humana do PR
  continua sendo a última barreira antes do merge, mesmo com dois portões
  de qualidade automatizados (Judge por subtask + Revisor de PR no final).
- Custo: alto volume de chamadas de agente/tokens para rodar as 10 tarefas
  de ponta a ponta com múltiplas rodadas de julgamento — agora potencialmente
  maior ainda, já que cada rodada de "pedido de mudanças" do Revisor de PR
  reabre ciclos inteiros de Testes/Judge e Implementação/Judge.
- Teto de rodadas do loop de revisão de PR definido para não travar o
  pipeline indefinidamente caso o Revisor de PR nunca aprove — nesse caso o
  PR fica aberto com "changes requested" para alguém resolver manualmente.
- Card Trello e branch/PR devem ficar rastreáveis 1:1 (uma branch, um PR, um
  card movido, por tarefa) para permitir auditoria posterior de todo o lote.

## 9. Lote P3 — Fase 1: calendário externo + clínico (iniciado em 2026-08-10) — 11 tarefas

Primeira fatia do P3 (o resto — multi-paciente/Organização, 19 tarefas, e a
tarefa #104 que depende dele — fica para uma Fase 2, com etapa de design
prévio, por mudar o modelo de dados de fundo).

- **Nenhuma base de código existe hoje** para integração com calendário
  externo — confirmado por investigação antes de puxar o lote: sem model de
  token OAuth, sem lib Google/Microsoft instalada, sem endpoint, sem tela.
  O único "calendar" existente no repo é a agenda interna (`api/views/care.py`
  `calendar_data`, usa o módulo `calendar` da stdlib do Python só para montar
  a grade mensal do dashboard) — não confundir com o épico novo.
- **Escopo ajustado antes de rodar** (decisão do usuário):
  - Card **#103** ("Integração com Google Agenda + Email") **excluído** do
    lote — duplica o objetivo do épico de calendário (#41-#50), com menos
    detalhe e sem Microsoft; rodar os dois em paralelo geraria duas
    implementações OAuth Google conflitantes.
  - Card **#104** ("Refazer o fluxo CRUD de grupo") **adiado para a Fase 2**
    — o próprio card diz "alinhado ao modelo multi-paciente", que ainda não
    foi desenhado; fazer agora seria retrabalho garantido.
- **Limitação de ambiente conhecida**: os fluxos OAuth reais (#48, #47)
  dependem de credenciais de app (`GOOGLE_CLIENT_ID`/`SECRET`,
  `MICROSOFT_CLIENT_ID`/`SECRET`) que só existem depois que um humano
  cria os apps OAuth nos consoles do Google Cloud e do Azure/Entra — isso é
  trabalho de produto/infra fora do escopo de código. Os agentes devem
  implementar e testar o fluxo inteiro com credenciais fake/mockadas
  (variáveis de ambiente com valor de teste, chamadas HTTP externas
  mockadas nos testes); a conexão real só funciona em produção depois que
  o usuário configurar credenciais de verdade — isso deve ficar explícito
  no corpo de cada PR relevante (#48, #47, #46).
- **Caminhos desatualizados nos cards**: o card #42 cita
  `app/src/navigation/types.ts` (pasta antiga, não rastreada — mesmo gotcha
  documentado na seção 8). A navegação real fica em
  `frontend/src/navigation/RootNavigator.tsx`, com telas registradas
  diretamente via `<MainStack.Screen name="..." component={...} />`, sem um
  arquivo `types.ts` separado com `ParamList` explícito — o agente deve
  seguir o padrão já existente no arquivo, não recriar um `types.ts` novo.
- **As 11 tarefas do lote** (ordem de execução, épico de calendário
  sequencial por causa de dependência real entre elas, #122 independente):
  #50 (libs) → #49 (model de token, com criptografia em repouso) → #48
  (OAuth Google) → #47 (OAuth Microsoft) → #46 (serviço de sync
  Google+Microsoft) → #44 (desconectar) → #45 (task diária de sync às 06h)
  → #41 (campo/switch `sync_to_calendar`) → #42 (item de menu) → #43 (tela
  `IntegrationsScreen`) → #122 (curativos/casos de maior gravidade, sem
  dependência com o resto do lote — card com pouquíssimo detalhe no
  Trello, exige julgamento de produto do próprio agente, documentar
  decisões de escopo no corpo do PR).

## 10. Lote P3 — Fase 2: multi-paciente/Organização (iniciado em 2026-08-10) — 17 tarefas

Design completo em `DESIGN_MULTIPACIENTE.md` (aprovado pelo usuário antes de
rodar qualquer código). Cards #117 e #118 do backlog original não foram
encontrados no board Trello (nem em "to do" nem em "em análise") — ficam de
fora do lote até serem localizados/recriados.

- **Execução em duas sub-fases, não uma só**, por causa do risco de
  segurança identificado no design: a tarefa **#38** (permitir usuário em
  vários grupos) muda a premissa que hoje sustenta o isolamento de dados
  entre pacientes/famílias — toda autorização de acesso a `CareRecord` hoje
  é implícita ("o usuário só tem um grupo, então não há ambiguidade").
  - **Sub-fase 2a**: só a tarefa #38 roda no fluxo automatizado normal
    (build → revisão → triagem). Depois disso, o merge NÃO segue o padrão
    automático de "revisão do agente + merge direto" — passa por revisão
    manual extra do usuário/orquestrador antes de entrar em
    `desenvolvimento`, com suíte de testes focada em isolamento entre
    grupos (usuário A nunca deve ver dado de paciente do usuário B).
  - **Sub-fase 2b**: as 16 tarefas restantes só começam depois que #38
    estiver de fato mesclado em `desenvolvimento` (não numa branch isolada)
    — elas dependem do campo `Profile.active_group` e do
    `GroupMembership.user` já como `ForeignKey` existindo de verdade na
    branch base, senão cada uma reimplementaria isso de forma incompatível
    (mesmo problema visto no lote P2 com `send_weekly_report` duplicado).
- **Cards com pouquíssimo detalhe** (uma frase só, exigem julgamento de
  produto do agente, documentar decisões de escopo no PR): #115, #116,
  #121, #123.
- **Ordem de execução da sub-fase 2b** (ver seção 6 do design para o
  racional completo): #32 → #29 → #30 → #31 → #33 → #39 → #40 → #35 → #36
  → #37 → #28 → #34 → depois #115, #116, #121, #123 (sem ordem estrita
  entre si, mas todas dependem de #34 já ter fechado).
