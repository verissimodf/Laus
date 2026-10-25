# Laus — Plataforma Autônoma de Agentes e Arbitragem (8 Pilares)

# ⚡ Laus — Autonomous Quant, Swarm & Jarvis Ecosystem

[![Self-Hosted](https://img.shields.io/badge/Architecture-Self--Hosted-0A0E17?style=for-the-badge&logo=docker&logoColor=00F0FF)](#)
[![Zero-Trust](https://img.shields.io/badge/Security-Zero--Trust_%2F_MPC-0A0E17?style=for-the-badge&logo=tailscale&logoColor=10B981)](#)
[![AgentSkills](https://img.shields.io/badge/Standard-AgentSkills_(SKILL.md)-0A0E17?style=for-the-badge&logo=markdown&logoColor=F59E0B)](#)
[![Mode](https://img.shields.io/badge/Mode-Paper_Only-0A0E17?style=for-the-badge&logo=python&logoColor=3B82F6)](#)

> **Estado atual do código:** Laus é experimental e opera somente em modo paper. O pipeline registra estimativas e não envia ordens a corretoras ([pipeline](core_jarvis/pipeline_e2e.py)); o gateway MCP oferece leitura, simulação e validação de propostas, sem liquidação ([servidor MCP](gateway_vault/mcp_servers/official_server.py)). O guardrail lê limites de ordem e slippage do ambiente, interrompe o registro paper quando o PnL realizado diário atinge o limite e restringe o notional paper acumulado por dia UTC; esse volume simulado não mede exposição nem risco projetado de uma conta real. O ledger SQLite é uma estimativa simplificada; o pipeline rejeita a regravação paper da mesma proposta pelo ID. O ledger não implementa partidas dobradas nem conformidade fiscal ([ledger](accounting_ledger/ledger_engine.py)). A telemetria PostHog exige ativação explícita e token de projeto ([emissor](cognition_skills/skills/posthog_telemetry/scripts/emit_posthog_event.py)). As seções abaixo descrevem a arquitetura-alvo e itens em evolução, não capacidades já disponíveis em produção.


**Laus** é uma plataforma pessoal, auto-hospedada (*self-hosted*) e orientada a eventos que unifica **orquestração cognitiva estilo Jarvis**, **motores quantitativos de alta frequência e arbitragem**, **simulação multiagente em enxame (Swarm)** e **governança financeira/fiscal rigorosa**.

Projetado para operar 24/7 com soberania total de dados e chaves, o Laus combina a precisão determinística de algoritmos quantitativos (como **Freqtrade**) com a capacidade adaptativa de agentes autônomos dotados de memória episódica, operando sob guardrails criptográficos (**MPC/TSS**) e conectividade padronizada (**MCP**).

---

## 🏛️ Arquitetura-alvo: 8 pilares em evolução

A arquitetura do **Laus** é sustentada por 8 dimensões interdependentes que garantem autonomia decisória, resiliência operacional e conformidade contábil:

### 1. 🧠 Laus Core (`core_jarvis` — Jarvis Orchestrator)
O plano de controle cognitivo central. Opera como um assistente executivo multimodal (voz/texto) e roteador de intenções em tempo real sobre um barramento de eventos (Redis/NATS). Traduz comandos estratégicos de alto nível em parâmetros quantitativos e coordena o ciclo de vida de todos os agentes.

### 2. 📈 Laus Quant & Swarm Simulator (`agents_quant` — Freqtrade + MiroFish)
União da execução matemática com inteligência coletiva:
* **Freqtrade Engine & Arbitrators:** Estratégias algorítmicas, *FreqAI* e robôs de arbitragem espacial, triangular e cambial (`USD-BRL` fiduciário vs. pares cripto CeFi/DeFi).
* **MiroFish Swarm Simulator:** Ambiente de simulação multiagente onde diferentes personas analíticas (Conservador, Arbitrador, *Market Maker*, Macro) debatem e testam cenários antes da alocação de capital expressivo.

### 3. 🔐 Gateway de Execução MCP & Custódia Segura (`gateway_vault` — MCP + MPC/KMS)
Isolamento total entre o raciocínio do agente e a assinatura de transações:
* **Servidores MCP (Model Context Protocol):** Interfaces padronizadas para que os agentes operem corretoras (via CCXT Pro/Freqtrade) e redes Web3 com ferramentas fortemente tipadas.
* **Assinatura TSS/MPC & Risk Guardrails:** Chaves fragmentadas e validadores determinísticos que bloqueiam ordens fora dos limites de *drawdown*, *slippage* ou exposição máxima.

### 4. 🖥️ Console de Gerenciamento & Observabilidade (`console_ui` — PostHog + awesome-design-md)
Centro de comando web construído em Next.js/React seguindo rigorosamente as diretrizes estéticas de alta densidade financeira inspiradas no **`VoltAgent/awesome-design-md`**:
* **API Key Vault:** Cofre criptografado para chaves de provedores de LLM e corretoras.
* **Telemetria PostHog Self-Hosted:** Rastreamento de cada decisão de agente, funis de conversão de arbitragem, custo de tokens e *Feature Flags* para ativação instantânea de estratégias.
* **Kill Switch:** Protocolo de parada de emergência de 1 clique (*Panic Button* / *Flatten All*).

### 5. 🧩 Cognition & Skills Hub (`cognition_skills` — AgentSkills + APIs Públicas)
Biblioteca modular de conhecimento e evolução contínua:
* **Padrão `AgentSkills` (`SKILL.md`):** Habilidades modulares com descoberta progressiva (*Progressive Disclosure*) para manter o contexto dos agentes enxuto e preciso.
* **Conectores Macro & Nacionais:** Integração nativa com **AwesomeAPI** (cotações `USD-BRL` em tempo real), **BrasilAPI** (validação de bancos, ISPB/COMPE para rampas fiat/OTC) e catálogos do **Public APIs**.
* **Memória Episódica & GraphRAG:** Banco vetorial (Qdrant) e grafos de conhecimento para auditoria *post-mortem* de operações e autoaprendizado adaptativo.

### 6. 🛡️ Infraestrutura Resiliente & Rede Zero-Trust (`resilience_edge` — Tailscale + Autocura)
Garantia de continuidade operacional durante picos de volatilidade:
* **Watchdogs & Self-Healing:** Monitoramento ativo de containers com políticas de autocura e *graceful shutdown* para nunca deixar ordens abertas desprotegidas.
* **Rede Zero-Trust:** Acesso remoto seguro via **Tailscale** / **Cloudflare Tunnels**, sem exposição de portas públicas no host local.
* **Circuit Breakers de Latência:** Entrada automática em modo *Fail-Safe* caso a latência com as corretoras ultrapasse limites seguros ou ocorra degradação de link.

### 7. 🧪 Gêmeo Digital & Sandboxing (`digital_twin` — Paper Trading Contínuo)
Nenhum agente ou estratégia opera capital real sem comprovação estatística prévia:
* **Modo Shadow / Paper Trading:** Agentes recém-criados operam em paralelo consumindo *order books* reais em tempo real, mas executando em livro de simulação.
* **Motor Walk-Forward & Stress Testing:** Reprodução automatizada de eventos extremos históricos (*flash crashes*, desancoragem de *stablecoins*, choques cambiais) para validar a sobrevivência conjunta das regras do Freqtrade e do enxame MiroFish.

### 8. ⚖️ Ledger Contábil & Compliance Fiscal (`accounting_ledger` — IN 1888 + DRE Automático)
Governança patrimonial e automação tributária em tempo real:
* **Livro-Razão de Partidas Dobradas (*Double-Entry Bookkeeping*):** Registro imutável de cada centavo movimentado, discriminando principal, taxas de gás/rede, comissões *maker/taker* e *spread* cambial.
* **Compliance Fiscal Brasil (IN 1888 & Ganho de Capital):** Motor de regras fiscais brasileiras com cálculo automático de preço médio ponderado, controle de limite de isenção, apuração de permutas entre criptoativos e exportação de relatórios compatíveis com a Receita Federal (integrado aos códigos bancários da **BrasilAPI**).

---

## 📂 Estrutura do Repositório

```text
Laus/
├── README.md                       # Apresentação e guia rápido da plataforma
├── ARCHITECTURE.md                 # Especificação técnica profunda dos 8 Pilares
├── AGENTS.md                       # Diretrizes de desenvolvimento para o Google Antigravity
├── docker-compose.yml              # Orquestração completa dos serviços self-hosted
├── .env.example                    # Template de variáveis de ambiente e segredos
├── docs/                           # Documentação complementar e diagramas
│   └── design-system.md            # Tokens visuais e UI inspirados no awesome-design-md
│
├── core_jarvis/                    # PILAR 1: Orquestrador Central
│   ├── app/
│   │   ├── orchestrator.py         # Coordenação de agentes, intenções e rotinas
│   │   ├── bus.py                  # Barramento de eventos assíncrono (Redis/NATS)
│   │   └── voice_gateway.py        # Interface multimodal de voz/texto (STT/TTS)
│   └── Dockerfile
│
├── agents_quant/                   # PILAR 2: Agentes de Mercado & Arbitragem
│   ├── freqtrade_engine/           # Estratégias quantitativas e modelos FreqAI
│   ├── mirofish_simulator/         # Simulação multiagente em enxame (Swarm)
│   └── arbitrators/                # Motores de spread CeFi/DeFi e câmbio USD-BRL
│
├── gateway_vault/                  # PILAR 3: Segurança, MCP e Execução
│   ├── mcp_servers/                # Servidores MCP (Freqtrade, CCXT Pro, Web3)
│   ├── tss_mpc/                    # Assinatura distribuída e cofre de chaves (KMS)
│   └── risk_guardrail/             # Validador determinístico de limites operacionais
│
├── console_ui/                     # PILAR 4: Painel de Gerenciamento & Observabilidade
│   ├── frontend/                   # Dashboard Next.js / React (Trading, Vault & Config)
│   ├── telemetry/                  # Integração e eventos do PostHog self-hosted
│   └── killswitch/                 # Protocolos de parada emergencial e liquidação
│
├── cognition_skills/               # PILAR 5: Memória, Aprendizado e Habilidades
│   ├── skills/                     # Biblioteca padrão AgentSkills (SKILL.md)
│   │   ├── macro_brazil/
│   │   │   └── SKILL.md            # Arbitragem e análise cambial (AwesomeAPI/BrasilAPI)
│   │   └── sentiment_analyzer/
│   │       └── SKILL.md            # Leitura de sentimento e eventos extremos
│   ├── connectors/                 # Clientes HTTP/WS (AwesomeAPI, BrasilAPI, Public APIs)
│   └── memory/                     # Vector Store (Qdrant) e GraphRAG episódico
│
├── resilience_edge/                # PILAR 6: Autocura, Watchdogs e Rede Zero-Trust
│   ├── tailscale/                  # Configuração de malha privada Zero-Trust
│   ├── watchdogs/                  # Monitoramento de saúde de containers e processos
│   └── circuit_breakers/           # Proteção contra alta latência e queda de link
│
├── digital_twin/                   # PILAR 7: Gêmeo Digital, Shadow Mode e Backtesting
│   ├── shadow_exchange/            # Simulador de execução Paper Trading em tempo real
│   ├── walk_forward/               # Validação contínua de estratégias e decaimento (Alpha Decay)
│   └── crash_scenarios/            # Datasets e replay de Flash Crashes históricos
│
└── accounting_ledger/              # PILAR 8: Contabilidade e Compliance Fiscal
    ├── double_entry/               # Motor contábil de partidas dobradas (PostgreSQL)
    ├── reconciler/                 # Conciliação automática de saldos on-chain e corretoras
    └── tax_brazil_in1888/          # Apuração mensal IN 1888, DRE e Ganho de Capital
```

---

## 🗺️ Roteiro Prático de Implementação (Roadmap)

### Fase 1: Fundação de Segurança, Rede e Infraestrutura (Pilares 1, 3 e 6)
- [ ] Configuração do `docker-compose.yml` base contendo Redis/NATS, PostgreSQL, Qdrant (Vector DB), PostHog e o esqueleto do `core_jarvis`.
- [ ] Configuração da malha Zero-Trust (`resilience_edge`) com Tailscale e *healthchecks* de autocura.
- [ ] Implementação do `gateway_vault` com cofre seguro de credenciais e o validador determinístico de limites de perda (*Risk Guardrail*).

### Fase 2: Motor Quantitativo, Conectores Nacionais & Gêmeo Digital (Pilares 2, 5 e 7)
- [ ] Subida da instância controlada do **Freqtrade** integrada ao módulo `digital_twin` em modo *Shadow / Dry-Run*.
- [ ] Implementação dos conectores de mercado no `cognition_skills` consumindo **AwesomeAPI** (`USD-BRL`) e **BrasilAPI** (`banks/v1`).
- [ ] Criação do primeiro servidor **MCP** em `gateway_vault/mcp_servers/` para interligar o `core_jarvis` ao motor do Freqtrade e CCXT.

### Fase 3: Console Administrativo, Telemetria & Ledger Contábil (Pilares 4 e 8)
- [ ] Criação do painel `console_ui/frontend` baseado no sistema de design `docs/design-system.md` (inspirado no `VoltAgent/awesome-design-md`).
- [ ] Integração dos dashboards de telemetria, auditoria de agentes e PnL com captura de eventos via **PostHog**.
- [ ] Implementação do livro-razão `accounting_ledger` (partidas dobradas e regras da IN 1888) + teste operacional do **Kill Switch**.

### Fase 4: Cognição Avançada, AgentSkills e Simulação Swarm (Pilares 2, 5 e 7)
- [ ] Implementação completa do formato padrão de habilidades (`SKILL.md`) seguindo a especificação `agentskills`.
- [ ] Adaptação do motor de sandbox **MiroFish** (`mirofish_simulator`) para rodar debates multiagente e testes de estresse antes de ordens de volume expressivo.
- [ ] Ativação da memória episódica contínua (`memory/`) para reflexão *post-mortem* e ajuste adaptativo de carteiras.

---

## 🚀 Como Iniciar o Desenvolvimento Híbrido (Antigravity + Colab + AI Studio)

1. **Clone o repositório** na sua pasta sincronizada ou servidor local e marque-a como **Disponível Offline**.
2. Copie o arquivo de variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```
3. Abra a pasta raiz no **Google Antigravity Desktop** — o agente lerá automaticamente o arquivo `AGENTS.md` e `ARCHITECTURE.md` para manter a padronização dos 8 pilares.
4. Suba a infraestrutura base em modo de simulação (*Shadow Mode*):
   ```bash
   docker compose up -d
   ```

### Reset local do Kill Switch

Após investigar e corrigir a causa da parada, execute `python -m core_jarvis.reset_kill_switch` na raiz do repositório. O comando mostra o motivo ativo, solicita o motivo da revisão e só libera o despacho após a confirmação literal `RESET KILL SWITCH`. O reset grava data UTC e justificativa no estado local. O recurso é local e não cria endpoint de reset no servidor MCP.

---

## 🔗 Referências e Inspirações Tecnológicas

* **Design System & UI:** [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md)
* **Observabilidade & Feature Flags:** [PostHog/posthog](https://github.com/PostHog/posthog)
* **Simulação Multiagente & Enxame:** [666ghj/MiroFish](https://github.com/666ghj/MiroFish)
* **Padrão Modular de Habilidades:** [agentskills/agentskills](https://github.com/agentskills/agentskills)
* **Catálogo de Dados Abertos:** [public-apis/public-apis](https://github.com/public-apis/public-apis)
* **APIs Econômicas e Bancárias Nacionais:** [AwesomeAPI Moedas](https://economia.awesomeapi.com.br/json/last/USD-BRL) & [BrasilAPI Bancos](https://brasilapi.com.br/api/banks/v1)

🗺️ Roteiro Prático de Implementação (Roadmap)

Fase 1: Fundação de Segurança, Rede e Infraestrutura (Pilares 1, 3 e 6)

[ ] Configuração do docker-compose.yml base contendo Redis/NATS, PostgreSQL, Qdrant (Vector DB), PostHog e o esqueleto do core-jarvis.

[ ] Configuração da malha Zero-Trust (infra-resilience) com Tailscale e healthchecks de autocura.

[ ] Implementação do gateway-vault com cofre seguro de credenciais e o validador determinístico de limites de perda (Risk Guardrail).

Fase 2: Motor Quantitativo, Conectores Nacionais & Gêmeo Digital (Pilares 2, 5 e 7)

[ ] Subida da instância controlada do Freqtrade integrada ao módulo digital-twin em modo Shadow / Dry-Run.

[ ] Implementação dos conectores de mercado no cognition-skills consumindo AwesomeAPI (USD-BRL) e BrasilAPI (banks/v1).

[ ] Criação do primeiro servidor MCP em gateway-vault/mcp_servers/ para interligar o core-jarvis ao motor do Freqtrade e CCXT.

Fase 3: Console Administrativo, Telemetria & Ledger Contábil (Pilares 4 e 8)

[ ] Criação do painel console-ui/frontend baseado no sistema de design docs/design-system.md (inspirado no VoltAgent/awesome-design-md).

[ ] Integração dos dashboards de telemetria, auditoria de agentes e PnL com captura de eventos via PostHog.

[ ] Implementação do livro-razão ledger-compliance (partidas dobradas e regras da IN 1888) + teste operacional do Kill Switch.

Fase 4: Cognição Avançada, AgentSkills e Simulação Swarm (Pilares 2, 5 e 7)

[ ] Implementação completa do formato padrão de habilidades (SKILL.md) seguindo a especificação agentskills.

[ ] Adaptação do motor de sandbox MiroFish (mirofish_simulator) para rodar debates multiagente e testes de estresse antes de ordens de volume expressivo.

[ ] Ativação da memória episódica contínua (memory/) para reflexão post-mortem e ajuste adaptativo de carteiras.

🚀 Como Iniciar o Desenvolvimento Híbrido (Antigravity + Colab + AI Studio)

Clone o repositório na sua pasta sincronizada ou servidor local e marque-a como Disponível Offline.

Copie o arquivo de variáveis de ambiente:

cp .env.example .env


Abra a pasta raiz no Google Antigravity Desktop — o agente lerá automaticamente o arquivo AGENTS.md e ARCHITECTURE.md para manter a padronização dos 8 pilares.

Suba a infraestrutura base em modo de simulação (Shadow Mode):

docker compose up -d


🔗 Referências e Inspirações Tecnológicas

Design System & UI: VoltAgent/awesome-design-md

Observabilidade & Feature Flags: PostHog/posthog

Simulação Multiagente & Enxame: 666ghj/MiroFish

Padrão Modular de Habilidades: agentskills/agentskills

Catálogo de Dados Abertos: public-apis/public-apis

APIs Econômicas e Bancárias Nacionais: AwesomeAPI Moedas & BrasilAPI Bancos