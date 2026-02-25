# 🎨 Alinhamento de Design: Web → Mobile

## ❌ Problemas Identificados

O app mobile React Native está **muito diferente** do CuidarJuntos original em Django. Precisa ser alinhado para manter a identidade visual e UX consistentes.

---

## 🔍 Análise do Design Original (Django Web)

### Cores Primárias
- **Azul Principal:** `#2563EB` (blue-600 Tailwind) - NÃO `#3B82F6`
- **Theme Color:** `#2563eb`
- **Backgrounds:** Cinza claro `bg-gray-50`
- **Cards:** Brancos com bordas `bg-white border`

### Logo e Branding
- **Ícone:** Coração (❤️) em SVG branco
- **Container:** Quadrado azul `bg-blue-600 p-2 rounded-lg`
- **Texto:** "CuidarJuntos" em negrito
- **Tagline:** Não tem (apenas "CuidarJuntos")

### Estrutura da Navegação
- **Header:** Fixo no topo, branco com borda
- **Menu Desktop:** Links horizontais (Grupo, Remédios, Dashboard, Registros)
- **Menu Mobile:** Hambúrguer que abre menu lateral
- **SEM Bottom Tabs!** (isso é invenção do mobile)

### Dashboard
1. **Filtro de Período:**
   - Card branco com borda
   - Campos: Data Inicial, Data Final
   - Checkboxes: "Mostrar apenas exceções", "Cards: contar só realizadas"
   - Botões: "Aplicar" (azul) e "X" (vermelho para limpar)

2. **Cards de Categoria:**
   - Grid responsivo (1 col mobile, 2 md, 3 xl)
   - Cards com cores de fundo específicas por tipo
   - Bordas arredondadas `rounded-xl`
   - Mostram: Ícone emoji, número de registros, label
   - **Clicáveis para filtrar** (toggle on/off)
   - Quando selecionado: outros cards ficam com `opacity: 0.45`

3. **Lista de Registros:**
   - Cards brancos com borda esquerda colorida por tipo
   - Informações: Tipo, descrição, data/hora, cuidador, status
   - Badges coloridos para status (pendente/feito/não feito)

### Cores por Tipo de Registro
```html
MEDICATION:  bg="#EFF6FF" color="#3B82F6" (azul)
SLEEP:       bg="#F5F3FF" color="#8B5CF6" (roxo)
MEAL:        bg="#F0FDF4" color="#22C55E" (verde)
BATHROOM:    bg="#FEFCE8" color="#EAB308" (amarelo)
ACTIVITY:    bg="#FFF7ED" color="#F97316" (laranja)
VITAL:       bg="#FEF2F2" color="#EF4444" (vermelho)
PROGRESS:    bg="#EEF2FF" color="#6366F1" (indigo)
OTHER:       bg="#FDF2F8" color="#EC4899" (rosa)
```

---

## ❌ O que está ERRADO no Mobile

### 1. Navegação
- ❌ **Bottom Tabs** - NÃO existe no original
- ❌ Tabs: Dashboard, Records, Medications, Upcoming, Profile
- ✅ **Deveria ser:** Header fixo + menu hambúrguer (mobile) ou links (desktop)

### 2. Cores
- ❌ Primary color: `#3B82F6` (azul muito claro)
- ✅ **Deveria ser:** `#2563EB` (blue-600)

### 3. Logo/Branding
- ❌ Texto gigante "CuidarJuntos" com tagline inventada
- ✅ **Deveria ser:** Ícone de coração em quadrado azul + texto "CuidarJuntos"

### 4. Dashboard
- ❌ Scroll horizontal de cards de categoria
- ❌ Cards pequenos (90px width)
- ❌ Sem filtros de data
- ✅ **Deveria ser:** Grid de cards grandes e clicáveis + filtros de período

### 5. Estrutura Geral
- ❌ Telas separadas demais (RecordList, RecordCreate como telas diferentes)
- ✅ **Deveria ser:** Dashboard centralizado com tudo integrado

### 6. Tipografia
- ❌ Fontes genéricas do React Native
- ✅ **Deveria usar:** System font (já está ok, mas tamanhos diferentes)

---

## ✅ Mudanças Necessárias

### FASE 1 - Cores e Branding

**Arquivo:** `frontend/src/theme/index.ts`
```typescript
// ANTES
primary: '#3B82F6',

// DEPOIS
primary: '#2563EB',  // blue-600 exato do Tailwind
```

**Arquivo:** `frontend/src/screens/LoginScreen.tsx`
```typescript
// REMOVER a tagline inventada
// ADICIONAR logo com ícone de coração
```

### FASE 2 - Navegação

**Arquivo:** `frontend/src/navigation/RootNavigator.tsx`
```typescript
// REMOVER Bottom Tabs completamente
// CRIAR Header fixo + Stack Navigator
// Menu hambúrguer para mobile
```

**Nova estrutura:**
```
<Header>
  <Logo + CuidarJuntos>
  <MenuButton (mobile) | Links (desktop)>
</Header>

<Stack Navigator>
  - Dashboard (tela principal)
  - Criar Registro (modal ou tela)
  - Detalhes do Registro
  - Estoque de Medicamentos
  - Agenda
  - Perfil
</Stack>
```

### FASE 3 - Dashboard Redesign

**Arquivo:** `frontend/src/screens/DashboardScreen.tsx`

**Novo layout:**
1. **Filtro de Período** (card branco no topo)
   - Data Inicial / Data Final
   - Checkboxes: Exceções, Contar só realizadas
   - Botões: Aplicar (azul) / Limpar (vermelho X)

2. **Cards de Categoria** (grid responsivo)
   - Grid 1 col (mobile) → 2 cols (tablet) → 3 cols (desktop)
   - Cards grandes e clicáveis
   - Backgrounds coloridos por tipo
   - Toggle de seleção (opacity 0.45 para não selecionados)

3. **Lista de Registros** (abaixo dos cards)
   - Cards brancos com borda esquerda colorida
   - Agrupados por dia
   - Badges de status

### FASE 4 - Componentes Reutilizáveis

**Criar:**
- `Header.tsx` - Header fixo com logo e menu
- `FilterCard.tsx` - Card de filtro de período
- `CategoryGrid.tsx` - Grid de cards de categoria (clicáveis)
- `RecordList.tsx` - Lista de registros agrupados

### FASE 5 - Cards de Categoria

**Arquivo:** `frontend/src/components/CategoryCard.tsx`

```typescript
// ANTES: Card pequeno (90px) em scroll horizontal
// DEPOIS: Card grande em grid, clicável, com toggle

<TouchableOpacity
  onPress={onToggle}
  style={{
    backgroundColor: meta.bg,
    borderWidth: 2,
    borderColor: isSelected ? meta.color : 'transparent',
    opacity: hasSelection && !isSelected ? 0.45 : 1,
    // Grid responsivo (não scroll horizontal!)
  }}
>
  <Text style={{ fontSize: 32 }}>{meta.emoji}</Text>
  <Text style={{ fontSize: 24, color: meta.color }}>{count}</Text>
  <Text>{meta.label}</Text>
</TouchableOpacity>
```

---

## 📋 Checklist de Implementação

### Urgente (UX quebrada)
- [ ] Remover Bottom Tabs
- [ ] Criar Header fixo com logo de coração
- [ ] Mudar cor primária para `#2563EB`
- [ ] Redesenhar Dashboard com filtros

### Importante (Alinhamento visual)
- [ ] Grid de cards de categoria (não scroll)
- [ ] Cards clicáveis com toggle
- [ ] Filtro de período completo
- [ ] Lista de registros agrupados por dia

### Nice to have
- [ ] Menu hambúrguer animado
- [ ] Transições suaves
- [ ] Dark mode (se o web tiver)

---

## 🎯 Prioridade de Execução

1. **Cores** (5 min) - Mudar `#3B82F6` → `#2563EB` no theme
2. **Logo** (10 min) - Adicionar ícone de coração no header
3. **Navegação** (30 min) - Remover tabs, criar header fixo
4. **Dashboard** (1h) - Filtros + Grid de cards + Lista
5. **Cards Categoria** (30 min) - Tornar clicáveis com toggle

**Tempo total estimado:** ~2h15min

---

## 💡 Nota

O mobile não precisa ser **IDÊNTICO** pixel-por-pixel ao web, mas deve:
- ✅ Usar as **mesmas cores**
- ✅ Ter a **mesma estrutura de navegação** (adaptada para mobile)
- ✅ Manter a **mesma lógica de UX** (cards clicáveis, filtros, etc.)
- ✅ Usar os **mesmos ícones e emojis**

**Princípio:** Um usuário que usa o web deve reconhecer imediatamente o app mobile como sendo o mesmo sistema.
