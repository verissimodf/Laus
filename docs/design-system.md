# ⚡ Laus Design System (`DESIGN.md`)
> **Padrão:** Inspirado em `VoltAgent/awesome-design-md` (Estética: *Linear + Kraken Pro + Bloomberg Terminal + Jarvis HUD*)  
> **Alvo:** `console-ui/frontend` (Next.js 15 + Tailwind CSS + Shadcn/UI + Lucide Icons + Lightweight Charts)  
> **Instrução para Agentes (Antigravity):** Sempre leia este documento antes de criar ou modificar qualquer componente React/Next.js no diretório `console-ui/`. Nunca utilize cores genéricas fora desta paleta ou fontes proporcionais para dados numéricos.

---

## 1. Filosofia Visual e Direção de Arte

O **Laus Console** não é um site institucional; é uma **cabine de comando financeira, cognitiva e de missão crítica** operada 24/7. A interface deve transmitir precisão cirúrgica, latência zero e soberania de dados.

* **Densidade de Informação Inteligente (*High-Density Terminal*):** Priorize *grids* compactos com bordas sutis de `1px` (`#1E293B`), sem desperdício de espaço em branco excessivo, permitindo visualizar simultaneamente o estado do Orquestrador Jarvis, *Order Books*, Simulação Swarm (MiroFish) e o Livro-Razão (IN 1888).
* **Modo Escuro Absoluto (*Obsidian First*):** Projetado exclusivamente em *Dark Mode* profundo para reduzir fadiga ocular em monitoramento contínuo e destacar alertas semânticos (Lucro, Risco, *Shadow Mode* e *Kill Switch*).
* **Distinção Clara entre Simulação e Capital Real:** O usuário deve identificar em menos de 100 milissegundos se um agente está operando no **Gêmeo Digital (Paper Trading)** ou com **Custódia Real (MPC/Mainnet)** através de bordas e *badges* de estado inequívocos.

---

## 2. Paleta de Cores e Tokens Semânticos

Todos os componentes devem utilizar estritamente estas variáveis CSS / classes Tailwind:

### Superfícies e Fundos (Backgrounds)
| Token | Hex | Equivalente Tailwind | Uso Principal |
| :--- | :--- | :--- | :--- |
| `--bg-canvas` | `#06090F` | `bg-[#06090F]` | Fundo global da aplicação (Obsidian Deep) |
| `--bg-surface-1` | `#0B101B` | `bg-[#0B101B]` | Painéis principais, cards de agentes e tabelas |
| `--bg-surface-2` | `#111827` | `bg-gray-900` | Cabeçalhos de tabelas, inputs, modais e *hover* |
| `--bg-glass` | `rgba(11, 16, 27, 0.78)` | `bg-[#0B101B]/80 backdrop-blur-md` | Barra de comando Jarvis (`Cmd+K`) e *overlays* |

### Bordas e Divisores (Borders)
| Token | Hex | Uso Principal |
| :--- | :--- | :--- |
| `--border-subtle` | `#1E293B` | Divisórias de grid, bordas padrão de cards (`1px solid`) |
| `--border-focus` | `#334155` | Card selecionado ou input em foco neutro |
| `--border-jarvis` | `#00F0FF` | Destaque ativo de raciocínio/voz do Orquestrador Jarvis |

### Cores de Acento e Estados Operacionais
| Token | Hex | Significado no Ecossistema Laus |
| :--- | :--- | :--- |
| `--accent-jarvis` | `#00F0FF` | **Ciano Cognitivo:** Atividade do `core-jarvis`, voz ativa, carregamento de `SKILL.md` |
| `--accent-swarm` | `#8B5CF6` | **Violeta Neural:** Simulação multiagente `MiroFish`, memória vetorial Qdrant e GraphRAG |
| `--signal-bull` | `#10B981` | **Verde Esmeralda:** Lucro líquido (PnL > 0), compra (*Long/Bid*), spread de arbitragem positivo |
| `--signal-bear` | `#F43F5E` | **Vermelho Carmesim:** Prejuízo (PnL < 0), venda (*Short/Ask*), violação de *Guardrail* |
| `--signal-shadow` | `#F59E0B` | **Âmbar Simulação:** Modo **Gêmeo Digital / Paper Trading** (`digital-twin`) ou alerta de latência |
| `--signal-kill` | `#DC2626` | **Vermelho Crítico:** Botão de parada emergencial (**Kill Switch**) e *Circuit Breaker* aberto |

### Tipografia (Texto)
* **Texto Primário (`--text-primary`):** `#F8FAFC` (Branco gelo para títulos e valores principais)
* **Texto Secundário (`--text-secondary`):** `#94A3B8` (Cinza ardósia para rótulos, colunas e metadados)
* **Texto Mudo (`--text-muted`):** `#475569` (Hashes, timestamps antigos, IDs de transação)

---

## 3. Tipografia e Regras de Formatação Numérica

A legibilidade instantânea de cotações (`USD-BRL`), *spreads* e saldos é obrigatória:

1. **Fonte de Interface (`--font-sans`):** `Inter` ou `Geist Sans`
   * Usada em menus de navegação, descrições de *Skills*, relatórios textuais e diálogos com o Jarvis.
2. **Fonte Quantitativa e de Código (`--font-mono`):** `JetBrains Mono` ou `Geist Mono`
   * **REGRA DE OURO:** Todo número financeiro (preços, porcentagens, saldos, latência em `ms`, hashes MPC, códigos ISPB da BrasilAPI e contadores de tokens no PostHog) **DEVE** usar `font-mono` combinado com a propriedade CSS `font-variant-numeric: tabular-nums` (`tabular-nums` no Tailwind). Isso impede que a interface "trema" quando os preços atualizam via WebSocket a cada milissegundo.

### Escala Tipográfica
* **Hero KPI (Patrimônio Líquido / PnL Diário):** `text-2xl font-mono font-bold tracking-tight tabular-nums`
* **Título de Módulo/Pilar:** `text-sm font-sans font-semibold uppercase tracking-wider text-slate-400`
* **Célula de Tabela / Order Book:** `text-xs font-mono tabular-nums leading-tight`
* **Logs de Eventos / Auditoria:** `text-[11px] font-mono text-slate-400`

---

## 4. Arquitetura de Layout (App Shell)

O `console-ui` utiliza uma estrutura fixa de tela cheia (`h-screen overflow-hidden flex flex-col bg-[#06090F] text-[#F8FAFC]`):

```text
+--------------------------------------------------------------------------------------------------+
| TOPBAR (h-12): [Status Zero-Trust] [USD-BRL AwesomeAPI] [Latência] [Modo: REAL/SHADOW] [KILL SW] |
+--------+-------------------------------------------------------------------+---------------------+
|        |                                                                   |                     |
|  SIDE  |                     BENTO GRID CENTRAL                            |   PAINEL JARVIS &   |
|  RAIL  |  +-----------------------------+-------------------------------+  |   SWARM (w-80/96)   |
| (w-16  |  | Gráfico / Arbitragem Spread | Enxame MiroFish (Consenso)    |  |                     |
|  ou    |  +-----------------------------+-------------------------------+  | - Stream Cognitivo  |
|  w-56) |  | Posições Abertas (Freqtrade)| Cofre MPC & Guardrails        |  | - Voz / Waveform    |
|        |  +-----------------------------+-------------------------------+  | - Skills Ativas     |
|        |  | Livro-Razão & IN 1888       | Telemetria PostHog / Funil    |  | - Comando Rápido    |
|        |  +-----------------------------+-------------------------------+  |                     |
+--------+-------------------------------------------------------------------+---------------------+
| FOOTER TICKER (h-7): [Redis Bus: OK] [Qdrant: OK] [Freqtrade: DRY-RUN] [Último Bloco/Sync]       |
+--------------------------------------------------------------------------------------------------+
```

### Componentes Estruturais Obrigatórios:
1. **Topbar de Comando e Segurança (`h-12 border-b border-[#1E293B]`):**
   * **Ticker Macro Nacional:** Exibe permanentemente a cotação `USD/BRL` vinda da **AwesomeAPI** comparada ao `USDT/BRL` médio das corretoras e o *spread* atual em pontos-base (`bps`).
   * **Seletor de Ambiente (Pilar 7):** Chaveador visual claro entre `SHADOW MODE (Gêmeo Digital)` (borda âmbar `#F59E0B`) e `LIVE EXECUTION (MPC Ativo)` (borda esmeralda `#10B981`).
   * **Botão KILL SWITCH (Pilar 4 & 6):** Localizado no canto superior direito, sempre visível, estilizado com fundo `#DC2626/20`, borda `#DC2626` e mecanismo de proteção contra clique acidental (*Hold 1.5s to Flatten All* ou confirmação modal instantânea via atalho).

2. **Sidebar de Navegação dos 8 Pilares:**
   * Navegação rápida entre:
     1. `Visão Geral (Command Center)`
     2. `Agentes & Arbitragem (Freqtrade + Spread)`
     3. `Simulador Swarm (MiroFish Sandbox)`
     4. `Cofre MPC & Conectores MCP`
     5. `Skills & Memória (SKILL.md Editor)`
     6. `Gêmeo Digital & Stress Tests`
     7. `Ledger & Fiscal (IN 1888 / DRE)`
     8. `Infra & Telemetria (Tailscale + PostHog)`

---

## 5. Especificação de Componentes Customizados

### 5.1. Card de Consenso do Enxame (`MiroFish Swarm Widget`)
Exibe o debate em tempo real entre as personas antes da aprovação de uma operação relevante:
* Mostrar avatares minimalistas ou indicadores para cada persona (`Quant`, `Arbitrador`, `Risk Manager`, `Macro Brazil`).
* Barra de consenso horizontal dividida entre `% Aprovação (Verde)`, `% Neutro (Cinza)` e `% Veto (Vermelho)`.
* Se o `Risk Guardrail` (Pilar 3) vetar a operação, o card inteiro recebe um *badge* vermelho `VETOED BY GUARDRAIL`.

### 5.2. Visualizador e Editor de `AgentSkills` (`SKILL.md`)
* Exibe os cartões das habilidades instaladas em `cognition-skills/skills/`.
* Cada cartão mostra se a *skill* está em estado **Dormant** (apenas metadados carregados na memória para economizar tokens) ou **Active/Loaded** (corpo do `SKILL.md` injetado no contexto do agente, destacado com borda `#00F0FF`).

### 5.3. Cofre de Chaves e Assinador MPC (`Gateway Vault UI`)
* **Proibido exibir chaves em texto puro:** Chaves de API (Gemini, Corretoras) aparecem mascaradas (`••••••••••••4F9A`) com indicador de criptografia `AES-256-GCM`.
* **Fila de Assinatura MPC:** Quando uma arbitragem ou movimentação ultrapassa o limite de autonomia automática, um card pulsante aparece no topo do painel Jarvis com os detalhes exatos (Origem, Destino validado via **BrasilAPI**, Valor, Taxa Estimada, *Slippage*) e botões `[Aprovar Assinatura]` / `[Rejeitar]`.

### 5.4. Painel Contábil e IN 1888 (`Ledger & Tax Module`)
* Tabela de partidas dobradas com colunas em `font-mono`: `Timestamp`, `Conta Débito`, `Conta Crédito`, `Ativo`, `Valor Bruto`, `Fee (Gas/Exchange)`, `Valor Líquido BRL` e ` Natureza Fiscal (IN 1888)`.
* Barra de progresso mensal monitorando o volume de alienação em corretoras nacionais vs. internacionais para alertas tributários automáticos.

---

## 6. Micro-interações, Animações e Estados de Dados

* **Flash de Atualização de Preço (*Tick Flash*):** Quando um valor na tabela ou no monitor de arbitragem muda via WebSocket, o fundo da célula pisca suavemente por `300ms` em `rgba(16, 185, 129, 0.15)` (se subiu) ou `rgba(244, 63, 94, 0.15)` (se caiu), retornando ao transparente.
* **Indicador de Latência e Autocura (Pilar 6):** Um pequeno ponto luminoso (`h-2 w-2 rounded-full`) ao lado de cada corretora e container Docker:
  * `< 100ms`: Verde sólido (`#10B981`)
  * `100ms - 350ms`: Âmbar (`#F59E0B`)
  * `> 350ms ou Reconectando`: Vermelho pulsante (`#F43F5E animate-pulse`) indicando ativação iminente do *Circuit Breaker*.
* **Atalhos de Teclado (*Keyboard-First*):**
  * `Cmd/Ctrl + K`: Abre a barra de comando universal do **Jarvis**.
  * `Shift + Esc`: Abre o modal de confirmação imediata do **Kill Switch**.
  * `Alt + S`: Alterna a visualização filtrada entre contas **Shadow (Paper Trading)** e **Live**.

---

## 7. Checklist de Qualidade para o Agente Gerador de UI

Antes de concluir qualquer tarefa no diretório `console-ui/`, o agente no **Antigravity** deve validar:
1. [ ] Todos os valores monetários, taxas, *spreads* e percentuais estão usando a classe `font-mono tabular-nums`?
2. [ ] O fundo principal respeita `#06090F` e os cards usam `#0B101B` com borda `#1E293B`?
3. [ ] Existe distinção visual clara entre dados do modo **Shadow/Paper Trading** (`#F59E0B`) e **Execução Real** (`#10B981`)?
4. [ ] Os eventos críticos de clique no painel estão disparando telemetria para a instância local do **PostHog** (`posthog.capture`)?