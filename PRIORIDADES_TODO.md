# Priorização das tarefas do Trello — coluna "to do"

> Board: [CUIDARJUNTOS DEV](https://trello.com/b/AwQ57bjv/cuidarjuntos-dev)
> Gerado em: 2026-08-05 — atualizado em 2026-08-09 (10 itens de P0 concluídos e removidos; 15 itens de P1 concluídos e mesclados em `desenvolvimento`)
>
> Critério: impacto em produção (bug em feature já lançada > feature nova), sinalização explícita da equipe (`urgent`, "PRIORIDADE"), sensibilidade de dados de saúde/segurança, e esforço restante (o que já tem base pronta no código vs. épico do zero). Agrupado por contexto de desenvolvimento porque tarefas do mesmo grupo compartilham arquivos/branch e fazem sentido serem puxadas em sequência.

---

## 🔴 P0 — Crítico (produção quebrada, segurança, ou marcado como prioridade)

### ✅ Concluído (verificado em produção em 2026-08-09)

Os 10 itens que abriam esta seção já foram desenvolvidos, mesclados em `desenvolvimento`/`main` e verificados no ar — removidos da lista ativa:

- #126 Bloquear edição de registros anteriores
- #105 Refazer UX/UI do login/cadastro → MOBILE
- #106 Consertar incongruências nos cards de registros do dashboard → MOBILE
- #107 Ajeitar menu de hambúrguer → MOBILE
- #109 Deixar o dashboard em grid padrão → MOBILE
- #110 Consertar agenda → MOBILE
- #100 Consertar e refatorar agenda (não-mobile, mesma área)
- #101 Ajeitar tela de remédios
- #99 Adicionar remédio e cadastrar novo remédio (feio e desalinhado)
- #111 Teste de segurança e integridade de dados de saúde

### Segurança / dados de saúde
(LGPD-sensível — cruza com o card já estudado "conformidade LGPD")

- #119 Reconhecimento fácil para segurança dos dados
- #120 Filtrar acesso com senha + atividade nova propaga para todos

**Ordem sugerida dentro do P0 restante:** o bloco de segurança que sobrou (#119, #120) é mais amplo e precisa de design antes de codar.

---

## 🟠 P1 — Alto impacto, esforço menor (constrói em cima do que já existe)

### ✅ Concluído (mesclado em `desenvolvimento` em 2026-08-09/10 — ver [GUIA_DE_TESTES.md](GUIA_DE_TESTES.md) para como validar cada item)

**Exclusão de registros / auditoria admin:**

- #88 Integrar exclusão de registros no app — PR #44
- #89 Modal de confirmação para ações destrutivas — PR #45
- #92 Excluir registro mantendo histórico para auditoria — PR #46
- #93 API: superuser pode excluir qualquer registro — PR #47
- #90 Aba Registros na tela do admin — PR #48
- #91 Testes da exclusão de registros pelo admin — PR #49

**Exportação — filtros:**

- #82 API: filtrar exportação por cuidador — PR #50
- #83 API: filtrar exportação por status — PR #51
- #79 Filtrar exportação por categoria de cuidado — PR #52
- #80 Filtrar exportação por status — PR #53
- #78 Corrigir filtro de datas no Exportar — PR #54
- #81 Testes dos novos filtros de exportação — PR #55
- #84 Rodapé com metadados no DOCX exportado — PR #56
- #86 Resumo estatístico no início dos exports — PR #57
- #87 Capa com paciente e período nos exports — PR #58 (unificado com #86 no mesmo formato de resumo, sem aba "Capa" separada)

---

## 🟡 P2 — Funcionalidade nova de médio porte, dependências internas claras

### Relatório semanal por email + infra Celery/Redis
Distinto do push semanal que já foi mergeado — aqui é o e-mail. Ordem: infra primeiro, senão nada do resto roda.

1. #67 Configurar variáveis de ambiente do Celery
2. #69 Instalar bibliotecas de tarefas agendadas
3. #59 Configurar Redis em produção
4. #68 Configurar agendador de tarefas
5. #66 Subir worker e scheduler em produção
6. #64 Conteúdo do relatório semanal
7. #63 Layout do email de relatório semanal
8. #65 Task de envio de relatório semanal
9. #62 Agendar envio do relatório toda segunda às 08h
10. #61 Membro pode optar por receber ou não o relatório
11. #60 Testes do envio do relatório semanal

⚠️ Como o **push semanal** (`celery-weekly-summary`) já está em produção, é bem provável que a infra Celery/Redis básica **já exista** — vale confirmar antes de fazer #59/#66-69 do zero, senão é retrabalho.

### Voz — extensão do uso
A base já foi mergeada: `useSpeechToText`, `MicrophoneButton`.

- #77 Adicionar biblioteca de reconhecimento de voz *(pode já estar feita — checar antes)*
- #75 Reconhecimento de voz nativo no iOS e Android
- #76 Pedir permissão de microfone ao usuário
- #71 Permitir falar em campos de texto livre
- #72 Permitir falar no campo Observações
- #70 Testar gravação de voz em iOS, Android e Web *(QA, por último)*

### Feedback de produto — melhorias pontuais
Baixo acoplamento entre si, podem ser feitas avulsas.

- #112 Anexar foto
- #113 Mudar atividades em blocos (manhã/tarde/noite)
- #114 Deixar mais claro estoque disponível e alerta de compra
- #127 Timing do registro ("colocado há X horas")
- #102 Adicionar filtros no histórico de registros
- #108 Adicionar carregamento no processamento de registro → MOBILE

---

## 🔵 P3 — Épicos grandes (arquitetura nova, alto esforço, menor urgência)

### Multi-paciente / Organização
Muda o modelo de dados de fundo (hoje é 1 paciente por grupo). Precisa de design antes de codar.

1. #40 Conceito de Organização (ex: clínica) *(fundação do épico)*
2. #35 API de gestão de organizações
3. #36 Definir papéis dentro de uma organização
4. #37 Vincular grupos de cuidado a uma organização
5. #38 Permitir que um usuário esteja em vários grupos
6. #39 Permitir múltiplos grupos para o mesmo paciente
7. #28 Tela de gestão da organização
8. #32 API: trocar de paciente ativo
9. #29 App lembra qual paciente o usuário está cuidando
10. #30 Mostrar o paciente ativo no topo da tela
11. #31 Tela para trocar entre pacientes
12. #33 Consultas respeitam o paciente ativo
13. #34 Adaptar todas as áreas para multi-paciente *(último — depende de tudo acima)*

Relacionados a papéis/organização, encaixam neste épico:

- #115 Acessos diferentes por função (ex.: área financeira)
- #116 Prestador com acesso ao dia anterior (filtrado)
- #117 Relatório diário por cuidador (evitar conflito)
- #118 Personalizar destinatários do relatório
- #121 Identificar cuidadores por códigos/números
- #123 Cadastrar um cliente pela empresa *(soa a modelo B2B — validar com negócio antes)*

### Integração com calendário externo
Épico isolado, nenhuma outra área depende dele.

1. #49 Guardar credenciais de calendários conectados *(fundação)*
2. #50 Adicionar bibliotecas para integração de calendários
3. #48 Conectar conta Google
4. #47 Conectar conta Microsoft Outlook
5. #46 Lógica de criação de eventos no Google e Outlook
6. #44 API: desconectar calendário externo
7. #45 Enviar cuidados do dia seguinte para o calendário
8. #41 Opção de sincronizar cuidado com calendário externo
9. #42 Adicionar Integrações ao menu
10. #43 Tela para conectar Google Calendar e Outlook

### Clínico / avançado

- #122 Inserção de curativos e casos de maior gravidade
- #103 Integração com Google Agenda + Email
- #104 Refazer o fluxo CRUD de grupo

---

## ⚪ P4 — Exploratório / não-dev (pesquisa, validação, processo)

- #95 Estudar bancos de dados relacionais, NoSQL e vetoriais
- #96 Estudar Machine Learning
- #97 Estudar métodos estatísticos e quantitativos
- #124 Prática interna dos cuidadores + teste da doutora *(validação/UX research, não é código)*
- #125 Fazer em conjunto com cuidadores (viver a experiência) *(idem)*
- #98 TESTAR SITE E APP *(QA manual geral — bom para rodar depois de fechar o P0/P1)*

---

## Resumo executivo

Os bugs mobile (**P0**, exceto o bloco de segurança #119/#120) e os dois grupos que tinham base de código pronta — exclusão/auditoria e exportação (**P1**) — já foram fechados e mesclados em `desenvolvimento`. O próximo alvo natural é o **P2** (relatório semanal por email + infra Celery/Redis, e a extensão de voz), antes de abrir os épicos grandes de multi-paciente e calendário (**P3**), que exigem design prévio.

Próximo passo sugerido: confirmar se a infra Celery/Redis do push semanal já cobre parte do P2 (ver aviso na seção), e depois verificar no código quais grupos de P2 já têm mais coisa pronta do que o Trello sugere (mesmo padrão usado para mapear a coluna "em análise").
