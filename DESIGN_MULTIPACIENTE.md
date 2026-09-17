# Design — Multi-paciente / Organização (P3, Fase 2)

> Proposta de arquitetura para o épico de multi-paciente do `PRIORIDADES_TODO.md`
> (13 tarefas centrais #28-#40 + 6 relacionadas #115-#123). Escrito antes de
> qualquer código, para aprovação — este documento é a base que o fluxo de
> desenvolvimento automatizado vai seguir depois de aprovado.

## 1. Por que isso é um épico de verdade (não só "mais uma feature")

O modelo de dados atual assume, em três lugares estruturais diferentes, que
**um usuário só cuida de um paciente**:

- `GroupMembership.user` é `OneToOneField` + `unique_together(user)` — um
  usuário só pode estar em **um** grupo, nunca mais (`care/models.py:90-92,104-106`).
- `CareGroup.patient` é `OneToOneField` — um grupo tem **exatamente um**
  paciente, nunca mais (`care/models.py:58-60`).
- Toda a autorização de acesso a dados (`_get_patient(user)` em
  `api/views/care.py:30-34`, usado por praticamente todo endpoint de
  `CareRecord`) resolve o paciente do usuário **implicitamente**, via esse
  único grupo — não existe hoje nenhuma checagem explícita "este registro
  pertence a um grupo do qual o usuário é membro". A unicidade do grupo *é*
  o mecanismo de isolamento.

Isso significa que remover a restrição de "1 grupo por usuário" não é uma
mudança de schema isolada — quebra a suposição que sustenta o isolamento de
dados de saúde entre famílias/pacientes diferentes hoje. É o ponto de maior
risco de todo o épico e por isso está no centro deste design.

## 2. O que o backlog do Trello realmente pede

Lendo as 13 tarefas centrais (#28-#34, #35-#40) e as 6 relacionadas
(#115-#123) juntas, dá pra separar em três mudanças independentes:

1. **Um usuário pode pertencer a vários `CareGroup`** (ex.: cuida da própria
   mãe num grupo familiar e trabalha como cuidador profissional em outro
   grupo, de outro paciente) — tarefas #38, #29-#33.
2. **O mesmo paciente pode ter mais de um `CareGroup`** (ex.: um grupo
   familiar e um grupo de uma clínica gerenciando o mesmo paciente,
   separadamente) — tarefa #39.
3. **Organizações** (ex.: uma clínica) podem agrupar vários `CareGroup` sob
   um guarda-chuva administrativo, com papéis próprios — tarefas #40, #35,
   #36, #37, e as relacionadas de acesso por função (#115, #116, #123).

As três são conceitualmente independentes, mas #2 e #3 dependem de #1 estar
pronto e testado primeiro (não dá pra ter organizações multi-grupo sem
primeiro suportar usuário-em-vários-grupos).

## 3. Modelo de dados proposto

```
Organization (novo)
  id, name, created_by, created_at

OrganizationMembership (novo)
  organization FK, user FK, role (ADMIN | STAFF)
  unique_together(organization, user)

CareGroup (alterado)
  patient: OneToOneField → ForeignKey(Patient, related_name="care_groups")
  organization: FK(Organization, null=True, blank=True)  [novo — grupo "solto" se null]
  (resto sem mudança)

GroupMembership (alterado)
  user: OneToOneField → ForeignKey(User, related_name="group_memberships")
  role: novo CharField (ADMIN | MEMBER), default MEMBER
  unique_together: troca de unique(user) para unique(user, group)

Profile (accounts/models.py, alterado)
  active_group: novo FK(CareGroup, null=True, blank=True, related_name="+")
```

**Por que `active_group` no `Profile` e não numa tabela separada de sessão:**
mais simples, sobrevive a troca de dispositivo (o usuário troca de paciente
ativo no celular e vê o mesmo ao abrir no navegador), e já existe um padrão
equivalente (`Profile.full_name`, `Profile.role`) sendo lido em request por
request sem custo perceptível.

**Papel dentro do grupo (`GroupMembership.role`) é novo** — hoje não existe
nenhuma distinção admin/membro dentro de um `GroupMembership`
(`relation_to_patient` é só rótulo clínico, não controla permissão). Preciso
disso para #36 (papéis) e para decidir quem pode remover outros membros do
grupo, sem reaproveitar `accounts.Profile.role` (que é global do usuário,
não por grupo — a mesma pessoa pode ser "membro comum" num grupo e "admin"
em outro).

## 4. O ponto crítico: autorização deixa de ser implícita

Hoje: `_get_patient(user)` = "o paciente do único grupo do usuário", usado
para filtrar `CareRecord.objects.filter(patient=patient)` em praticamente
todo endpoint.

Depois: um usuário tem N grupos. Toda request precisa saber **qual** grupo
está em uso. Proposta:

- Todo endpoint que hoje resolve o paciente implicitamente passa a resolver
  via `request.user.profile.active_group` — mas **sempre revalidando** que
  o usuário ainda é membro daquele grupo (`GroupMembership.objects.filter(
  user=request.user, group=active_group).exists()`) antes de qualquer
  leitura/escrita. Nunca confiar cegamente no valor salvo.
- Se `active_group` for `None` ou o usuário não for mais membro dele
  (removido do grupo, por exemplo), a API retorna 409/400 pedindo para
  selecionar um grupo ativo — nunca cai silenciosamente para "primeiro
  grupo encontrado" (isso seria escolher o paciente errado por trás das
  costas do usuário, no pior cenário possível dado que é dado de saúde).
- Nova permission class `IsMemberOfActiveGroup` (substitui/complementa
  `HasGroupMembership`, que hoje só checa "tem algum grupo", não "é membro
  *deste* grupo").
- **Cada endpoint que usa `_get_patient` hoje precisa ser tocado** — não dá
  pra fazer uma mudança central e pronto. Listei os principais candidatos na
  seção 6.

## 5. Migração de dados

Boa notícia: como hoje `unique(user)` garante no máximo 1 membership por
usuário, **não há conflito de dados para resolver** — a migração é
estritamente aditiva:

1. `GroupMembership.user`: `OneToOneField` → `ForeignKey` (Django faz isso
   como uma migration simples, sem perda de dados; o índice único antigo
   vira único composto `(user, group)`, que a linha existente já satisfaz).
2. `CareGroup.patient`: `OneToOneField` → `ForeignKey` (idem — nenhuma linha
   viola a unicidade nova porque hoje só existe uma por paciente).
3. `Profile.active_group`: novo campo nullable. Uma migration de dados
   (`RunPython`) popula `active_group` de cada usuário com o grupo do
   `GroupMembership` que ele já tinha antes da migração — **todo usuário
   existente continua vendo exatamente o mesmo paciente que via antes**,
   sem precisar escolher nada na primeira vez que abrir o app depois do
   deploy.
4. `Organization`/`OrganizationMembership`: tabelas novas, sem dados
   herdados — todo `CareGroup` existente fica com `organization=None`
   ("grupo solto", fora de qualquer organização), que é o estado válido e
   esperado até alguém criar uma organização de verdade.

Nenhum downtime ou script de reconciliação manual necessário — é o tipo de
migração mais seguro que existe (relaxar uma constraint, não apertar).

## 6. Ordem de execução sugerida (mapeando para as tarefas do Trello)

Fiel à ordem que já está no `PRIORIDADES_TODO.md`, com uma correção: mover
#39 (patient multi-grupo) para depois de #38 (user multi-grupo) já que #38 é
o que efetivamente testa a mudança de autorização pela primeira vez — mais
arriscado, deve vir sozinho e bem testado antes de empilhar mais uma
mudança de cardinalidade em cima.

1. **#38** — `GroupMembership.user` OneToOne → FK, `Profile.active_group`,
   revisão de TODO endpoint que usa `_get_patient`/`HasGroupMembership`
   para checar o grupo ativo explicitamente. **Este é o PR que carrega o
   risco de segurança do épico inteiro — merece revisão humana extra, não
   só o Revisor de PR automatizado.**
2. **#32** — API trocar de paciente ativo (`PATCH /api/v1/profile/active-group/`
   ou similar, valida membership antes de trocar).
3. **#29** — app lembra o paciente ativo (frontend: `AuthContext` passa a
   guardar `activeGroup` vindo do backend, não mais assumido único).
4. **#30** — mostrar paciente ativo no topo da tela (Header).
5. **#31** — tela pra trocar entre pacientes (lista os grupos do usuário).
6. **#33** — auditoria: todo hook/query do frontend que assume "o grupo" já
   respeita o grupo ativo escolhido (não é uma tarefa de código isolada, é
   uma varredura — pode virar checklist dentro do PR de #34).
7. **#39** — `CareGroup.patient` OneToOne → FK (paciente em vários grupos).
8. **#40** — model `Organization` + `OrganizationMembership`.
9. **#35** — API de gestão de organizações (CRUD).
10. **#36** — papéis dentro da organização (ADMIN/STAFF já no model de #40;
    aqui é a lógica de permissão em cima disso).
11. **#37** — vincular `CareGroup` a uma `Organization`.
12. **#28** — tela de gestão da organização (frontend).
13. **#34** — adaptar todas as áreas restantes (último, depende de tudo).

Relacionadas (#115-#123), encaixam depois de #34 porque dependem de papéis
de organização (#36) ou de multi-grupo (#38) já estarem prontos:
#115 (acesso por função) → depende de #36; #116/#117/#118 → dependem de #34
(relatórios já precisam saber lidar com múltiplos grupos); #121/#123 →
dependem de #37/#40.

## 7. Riscos assumidos e o que fica de fora deste design

- **Não cobre** o desenho visual das telas novas (#28, #31) — fica a
  critério do agente de implementação seguir o design system já existente
  no app, sem mockup prévio.
- **Não cobre** regras de billing/cobrança para organizações tipo clínica
  (#123 menciona "modelo B2B" — se isso implicar em cobrança, é uma decisão
  de negócio fora do escopo técnico deste documento).
- **Risco aceito**: o PR de #38 vai ser grande (toca praticamente todo
  endpoint de `api/views/care.py`) — não dá para quebrar em PRs menores sem
  deixar o sistema num estado inconsistente pelo meio do caminho (endpoints
  migrados convivendo com endpoints ainda assumindo grupo único). Proponho
  aceitar um PR grande, mas com suíte de testes extensiva focada em
  isolamento entre grupos (usuário A não pode nunca ver dado de paciente do
  usuário B mesmo trocando `active_group` manualmente na request).
