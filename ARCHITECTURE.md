# 🏗️ Especificação de Arquitetura Técnica — Plataforma Laus (8 Pilares)

Este documento descreve a arquitetura de engenharia, o fluxo de dados, os modelos matemáticos de risco e contabilidade, e os protocolos de comunicação entre os **8 Pilares** do ecossistema **Laus**.

---

## 1. Visão Macro e Topologia do Sistema

O **Laus** adota uma arquitetura de microsserviços modular e orientada a eventos (*Event-Driven Architecture*), onde nenhuma decisão gerada por modelos de linguagem (LLMs) tem acesso direto à rede das corretoras ou chaves privadas sem atravessar três camadas determinísticas de validação: **Gêmeo Digital (Pilar 7)**, **Risk Guardrail (Pilar 3)** e **Circuit Breaker de Infraestrutura (Pilar 6)**.

```text
+===================================================================================================+
|                  PILAR 6: INFRAESTRUTURA RESILIENTE & REDE ZERO-TRUST (Tailscale)                 |
|       [Watchdogs / Docker Self-Healing]  |  [Latency Circuit Breakers]  |  [Fail-Safe Daemon]     |
+===================================================================================================+
                                                  |
+-------------------------------------------------v-------------------------------------------------+
|               PILAR 4: CONSOLE DE GERENCIAMENTO & OBSERVABILIDADE (console_ui)                    |
|  Next.js UI (awesome-design-md)  |  API Key Vault (AES-GCM)  |  PostHog Telemetry  |  Kill Switch |
+-------------------------------------------------+-------------------------------------------------+
                                                  | WebSockets / REST / Feature Flags
+-------------------------------------------------v-------------------------------------------------+
|                         PILAR 1: LAUS CORE — JARVIS ORCHESTRATOR (core_jarvis)                    |
|              Voice/Text Gateway  |  Intent Router  |  Event Bus (Redis Streams / NATS)            |
+------------+------------------------------------+------------------------------------+------------+
             |                                    |                                    |
+------------v-------------+        +-------------v--------------+       +-------------v------------+
| PILAR 5: COGNITION &     |        | PILAR 2: LAUS QUANT &      |       | PILAR 7: GÊMEO DIGITAL   |
| SKILLS HUB               |        | SWARM SIMULATOR            |       | & SANDBOXING             |
| (cognition_skills)       |        | (agents_quant)             |       | (digital_twin)           |
|                          |        |                            |       |                          |
| - AgentSkills (SKILL.md) |<------>| - Freqtrade + FreqAI       |<----->| - Shadow Exchange Engine |
| - AwesomeAPI (USD-BRL)   |        | - MiroFish Swarm Sandbox   |       | - Walk-Forward Validator |
| - BrasilAPI (Banks v1)   |        | - CeFi/DeFi Arbitrators    |       | - Flash Crash Replayer   |
| - Qdrant + GraphRAG      |        |                            |       |                          |
+------------+-------------+        +-------------+--------------+       +-------------+------------+
             |                                    |                                    |
             +------------------------------------+------------------------------------+
                                                  | Proposta de Ordem Estruturada (JSON/Pydantic)
+-------------------------------------------------v-------------------------------------------------+
|                PILAR 3: GATEWAY DE EXECUÇÃO MCP & CUSTÓDIA SEGURA (gateway_vault)                 |
|   [Risk Guardrail Determinístico]  -->  [Servidores MCP (CCXT/Web3)]  -->  [Assinador TSS / MPC]  |
+-------------------------------------------------+-------------------------------------------------+
                                                  | Eventos de Execução & Fills Confirmados
+-------------------------------------------------v-------------------------------------------------+
|                PILAR 8: LEDGER CONTÁBIL & COMPLIANCE FISCAL (ledger-compliance)                   |
|   [Double-Entry Bookkeeping]  |  [Reconciliador On-Chain/CeFi]  |  [Motor Fiscal Brasil IN 1888]  |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. Especificação Técnica dos 8 Pilares

### Pilar 1: Laus Core (`core_jarvis`)
* **Barramento de Eventos (`bus.py`):** Implementado sobre **Redis Streams** (ou NATS JetStream) garantindo entrega *at-least-once* e persistência de mensagens entre containers.
* **Tópicos Principais do Barramento:**
  * `market.ticks.*`: Feeds normalizados de preços, *order books* e câmbio (`USD-BRL`).
  * `agent.proposals`: Intenções de operação geradas pelo enxame ou motores de arbitragem.
  * `risk.validated`: Ordens aprovadas pelo Guardrail prontas para assinatura MCP/MPC.
  * `execution.fills`: Confirmações de ordens executadas enviadas diretamente para o **Pilar 8 (Ledger)** e **Pilar 4 (PostHog)**.
  * `system.emergency`: Canal prioritário de latência zero para acionamento do *Kill Switch*.

---

### Pilar 2: Laus Quant & Swarm Simulator (`agents_quant`)
Divide o processamento de mercado em dois ciclos complementares (Rápido e Reflexivo):
1. **Ciclo Rápido Determinístico (`freqtrade_engine` & `arbitrators`):**
   * Calcula indicadores técnicos, *order flow imbalance* e *spreads* de arbitragem em milissegundos.
   * **Equação de Gatilho de Arbitragem Cambial/Cripto:**
     Seja $P_{\text{fiat}}$ a cotação `ask` do dólar comercial na **AwesomeAPI** (`USD-BRL`) e $P_{\text{crypto}}$ o preço efetivo de venda de `USDT/BRL` na corretora local considerando a profundidade do livro de ofertas (*VWAP*). O *spread* líquido $\Delta_{\text{net}}$ é dado por:
     $$\Delta_{\text{net}} = \frac{P_{\text{crypto}} - P_{\text{fiat}}}{P_{\text{fiat}}} - \left( f_{\text{maker/taker}} + f_{\text{withdrawal}} + f_{\text{iof/pix}} + s_{\text{slippage}} \right)$$
     A proposta de arbitragem só é emitida para o barramento se $\Delta_{\text{net}} > \theta_{\text{min}}$ (onde $\theta_{\text{min}}$ é o limite mínimo de lucro líquido parametrizado no console).
2. **Ciclo Reflexivo em Enxame (`mirofish_simulator`):**
   * Inspirado na arquitetura do **MiroFish**, instancia agentes especializados (Analista Macro Brasil, Caçador de Liquidez, Auditor de Risco Tail-Event) que avaliam mudanças de regime de mercado e calibram os hiperparâmetros das estratégias quantitativas.

---

### Pilar 3: Gateway de Execução MCP & Custódia Segura (`gateway_vault`)
* **Padronização via MCP (`mcp_servers/`):**
  Os agentes não invocam APIs REST arbitrárias. Toda interação com corretoras passa por servidores **Model Context Protocol (MCP)** locais que expõem ferramentas estritamente tipadas:
  * `mcp_exchange_get_liquidity_depth(symbol, volume_target)`
  * `mcp_exchange_stage_order(symbol, side, order_type, amount, price, strategy_id)`
  * `mcp_settlement_verify_bank(ispb_or_code)` (integrado à **BrasilAPI**)
* **Validador Determinístico (`risk_guardrail/`):**
  Escrito em código puro (sem LLM no loop), aplica travas matemáticas rígidas antes de qualquer chamada externa:
  * **Limite de Exposição por Operação:** Valor máximo de capital alocado por ordem ($V_{\text{order}} \le \alpha \cdot \text{Patrimônio Líquido}$).
  * **Trava de Drawdown Diário:** Se o prejuízo acumulado em 24h atingir o limite máximo ($DD_{24h} \ge DD_{\max}$), o Guardrail rejeita novas aberturas de posição e aciona o modo de proteção.
* **Assinatura TSS/MPC (`tss_mpc/`):**
  Para carteiras Web3/DeFi e movimentações entre corretoras, utiliza computação multipartidária (*Threshold Signature Scheme* $t$-de-$n$). O Agente possui apenas 1 fragmento da chave; o Cofre Local (`risk_guardrail`) assina com o 2º fragmento apenas se todas as regras determinísticas forem cumpridas.

---

### Pilar 4: Console de Gerenciamento & Observabilidade (`console_ui`)
* **Design System (`docs/design-system.md`):** Baseado nos padrões do repositório `VoltAgent/awesome-design-md`, utilizando estética *Dark-First* de alta precisão, fontes monoespaçadas (`JetBrains Mono`) com `font-variant-numeric: tabular-nums` para alinhamento perfeito de livros de ofertas e PnL.
* **Telemetria Analítica com PostHog (`telemetry/`):**
  Cada ação relevante dispara eventos estruturados para a instância auto-hospedada do **PostHog**:
  * `laus_skill_invoked`: Mede quais `SKILL.md` geram maior retorno financeiro.
  * `laus_guardrail_blocked`: Registra tentativas de ordens barradas pelo filtro de risco (útil para detectar alucinações ou agressividade excessiva de agentes).
  * **Feature Flags Operacionais:** Permite desligar instantaneamente o módulo de arbitragem DeFi ou trocar o modelo de LLM de um agente diretamente pela interface do PostHog sem reiniciar containers.

---

### Pilar 5: Cognition & Skills Hub (`cognition_skills`)
* **Especificação `AgentSkills` (`skills/*/SKILL.md`):**
  Cada habilidade segue o padrão `agentskills`, contendo cabeçalho YAML (`name`, `description`, `triggers`, `required_connectors`) e corpo em Markdown com instruções passo a passo e scripts auxiliares.
* **Conectores Nacionais e Públicos (`connectors/`):**
  * **Conector AwesomeAPI:** Consulta `https://economia.awesomeapi.com.br/json/last/USD-BRL` com cache inteligente em Redis e *fallback* para cálculo de paridade cambial.
  * **Conector BrasilAPI:** Consulta `https://brasilapi.com.br/api/banks/v1` para mapear códigos COMPE/ISPB, garantindo que transferências fiduciárias e registros bancários de arbitragem OTC estejam vinculados a instituições válidas.
* **Memória Episódica & GraphRAG (`memory/`):**
  Armazena vetores no **Qdrant** combinados a relações causais. Ao final de cada ciclo operacional, o agente grava uma tupla `(Contexto_Macro, Skill_Usada, Decisão, Resultado_Líquido, Lição_Aprendida)`, permitindo ajuste dinâmico de pesos via *Reinforcement Learning from Market Feedback*.

---

### Pilar 6: Infraestrutura Resiliente & Rede Zero-Trust (`resilience_edge`)
* **Malha Zero-Trust (`tailscale/`):** Todos os containers administrativos (Console UI, PostHog, Qdrant, FreqUI) escutam exclusivamente na interface privada `tailscale0` ou `127.0.0.1`. Nenhuma porta de gerência fica exposta na WAN pública.
* **Circuit Breakers de Conectividade (`circuit_breakers/`):**
  Monitora continuamente o *Round-Trip Time* ($RTT$) dos WebSockets das corretoras e o *drift* de relógio NTP ($\Delta t$).
  * Se $RTT > 500\text{ ms}$ ou $\Delta t > 100\text{ ms}$, o estado muda para `HALF-OPEN` (bloqueia novas entradas de arbitragem).
  * Se a desconexão persistir por mais de $N$ segundos com ordens limitadas abertas no livro, um comando de *Cancel-All-Open-Orders* é disparado via rota secundária de contingência.

---

### Pilar 7: Gêmeo Digital & Sandboxing (`digital_twin`)
* **Pipeline de Promoção de Agentes (Estágios Obrigatórios):**
  1. **Estágio 1 — Crash Replay (`crash_scenarios/`):** O agente é submetido a *datasets* históricos de alta volatilidade (ex.: colapsos rápidos de liquidez e picos de dólar).
  2. **Estágio 2 — Walk-Forward Validation (`walk_forward/`):** Otimização em janela móvel para verificar se a estratégia sofre de *overfitting*.
  3. **Estágio 3 — Shadow Mode (`shadow_exchange/`):** O agente opera por um período probatório em *Paper Trading* recebendo o livro de ofertas real ao vivo e simulando *slippage* realístico e fila de execução. Somente estratégias com *Sharpe Ratio* $> 1.5$ e *Max Drawdown* dentro do limite no Shadow Mode podem ser promovidas para produção no Console UI.

---

### Pilar 8: Ledger Contábil & Compliance Fiscal (`accounting_ledger`)
* **Motor de Partidas Dobradas (`double_entry/`):**
  Toda movimentação gera lançamentos contábeis atômicos no PostgreSQL onde a soma dos débitos e créditos é estritamente zero:
  $$\sum_{i} \text{Débitos}_i - \sum_{j} \text{Créditos}_j = 0$$
  Contas rastreadas: `Ativo:Caixa:BRL`, `Ativo:Cripto:USDT`, `Despesa:Taxas:Exchange`, `Despesa:Taxas:Gas_Rede`, `Receita:Arbitragem:Realizada`.
* **Motor Fiscal Brasileiro — IN 1888 e Ganho de Capital (`tax_brazil_in1888/`):**
  * Monitora o volume total mensal de operações (compras, vendas, permutas entre criptoativos e transferências para/de corretoras sem domicílio fiscal no Brasil).
  * Aplica alerta automático e geração de arquivo de exportação no leiaute da **Instrução Normativa RFB nº 1.888/2019** sempre que o volume mensal de operações em exchanges estrangeiras ou carteiras auto-custodiadas ultrapassar $\text{R\$ } 30.000,00$ (ou o limite vigente parametrizado).
  * Calcula o **Preço Médio Ponderado (PMP)** em `BRL` de cada ativo a cada aquisição, utilizando a cotação PTAX/AwesomeAPI do instante da transação e cruzando os dados bancários de origem/destino via **BrasilAPI**.

---

## 3. Fluxo de Vida de uma Decisão Autônoma (End-to-End)

1. **Percepção:** O conector `cognition_skills` detecta uma distorção entre o dólar comercial na **AwesomeAPI** e o par `USDT/BRL` via WebSocket, publicando o evento no `core_jarvis` (`bus.py`).
2. **Ativação de Habilidade:** O orquestrador aciona a skill `skills/macro_brazil/SKILL.md` e consulta a memória episódica no Qdrant para verificar o histórico de acerto sob condições similares de volatilidade.
3. **Simulação Rápida:** Se o volume da operação for expressivo, o módulo `agents_quant/mirofish_simulator` executa um consenso rápido com o `digital_twin` para estimar o *slippage* real no livro de ofertas.
4. **Validação e Execução:** A ordem estruturada é enviada ao `gateway_vault`. O `risk_guardrail` valida a exposição e a saúde da rede (`resilience_edge`). Sendo aprovada, o servidor **MCP** envia a ordem assinada via **TSS/MPC**.
5. **Auditoria e Contabilização:** Assim que a corretora confirma a execução (*fill*), o **PostHog** (`console_ui`) registra as métricas de performance do agente e o `accounting_ledger` grava os lançamentos de partidas dobradas, atualizando o DRE em tempo real e o relatório mensal da **IN 1888**.