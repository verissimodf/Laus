---
name: posthog-telemetry
description: Esquema de rastreamento de eventos analíticos, auditoria de decisões de agentes autônomos e monitoramento de funis operacionais no PostHog self-hosted.
triggers:
  - "telemetria"
  - "posthog"
  - "observabilidade"
  - "eventos"
  - "auditoria"
  - "metricas"
allowed-tools:
  - capture_telemetry_event
  - evaluate_feature_flag
  - query_agent_insights
metadata:
  version: 1.0.0
  framework: agentskills
  pillar: "Pilar 4: Console UI & Observabilidade"
---

# PostHog Telemetry & Agent Decision Audit Skill

Esta habilidade padroniza a emissão de métricas e telemetria comportamental de todos os agentes para a instância auto-hospedada do **PostHog** (rodando via `docker-compose.yml` na porta `8000`).

## 1. Eventos Críticos Padronizados
1. `laus_skill_invoked`: Registra qual habilidade do catálogo gerou a decisão e o tempo de processamento.
2. `laus_guardrail_blocked`: Registra violações de segurança para identificar agentes agressivos ou alucinações.
3. `laus_order_filled`: Rastreia o PnL líquido, slippage realizado e taxa de corretora por operação.
4. `laus_kill_switch_triggered`: Registra acionamentos de parada emergencial e motivo.

## 2. Feature Flags Operacionais
Permite ligar/desligar comportamentos dinâmicos sem alterar código ou reiniciar containers:
- `flag_enable_defi_arbitrage`: Ativa ou desativa rotas de arbitragem em pools descentralizados.
- `flag_force_shadow_mode`: Força todos os agentes a operarem no Gêmeo Digital (Paper Trading).
- `flag_llm_model_tier`: Altera o modelo de raciocínio de um agente (`gemini-2.5-flash` vs. `gemini-2.5-pro` vs. `gemini-3.8-flash`).

## 3. Scripts e Referências
- Emissor e mock de telemetria: `scripts/emit_posthog_event.py`
- Esquema de eventos JSON: `references/telemetry_events_schema.json`
