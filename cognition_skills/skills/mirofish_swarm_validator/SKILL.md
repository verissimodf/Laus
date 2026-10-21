---
name: mirofish-swarm-validator
description: Orquestra simulação multiagente em sandbox (Swarm MiroFish + Gêmeo Digital) para estressar propostas de ordens contra cenários de volatilidade e slippage antes da autorização de capital real.
triggers:
  - "mirofish"
  - "swarm"
  - "consenso"
  - "stress-test"
  - "digital-twin"
  - "sandbox"
  - "simulacao"
allowed-tools:
  - run_swarm_debate
  - evaluate_paper_trade
  - stress_test_order
metadata:
  version: 1.0.0
  framework: agentskills
  pillar: "Pilar 2: Laus Quant & Swarm + Pilar 7: Gêmeo Digital"
---

# MiroFish Swarm & Digital Twin Validator Skill

Esta habilidade operacional submete intenções de negociação geradas por robôs quantitativos a um debate entre personas analíticas heterogêneas no ambiente de simulação em enxame (*Swarm Sandbox*).

## 1. Personas do Enxame
1. **LiquidityProvider_Bot:** Avalia a profundidade do livro L2 e se a ordem causará esgotamento da fila.
2. **WhaleMomentum_Bot:** Verifica se o spread bruto absorve a volatilidade realizada recente.
3. **SpreadArbitrageur_Bot:** Mede o tempo de resposta e viabilidade da janela de latência.
4. **TailRisk_Auditor:** Simula cenários de estresse histórico (Flash Crashes, desancoragem cambial).

## 2. Critérios de Aprovação
- **Score Mínimo de Consenso:** $\ge 0.70$ (70% de aprovação ponderada por confiança).
- **Validação de Slippage Sintético:** A ordem é replicada no Gêmeo Digital (`digital-twin`). Se o spread efetivo resultante descontando ruído estocástico for $\le 0$, a ordem é abortada com status `SLIPPAGE_KILL`.
- **Exposição Máxima:** Operações acima de US$ 280,00 requerem consenso estrito $\ge 0.85$.

## 3. Scripts e Referências
- Script de teste e validação: `scripts/simulate_consensus.py`
- Cenários de estresse: `references/stress_scenarios.json`
