---
name: risk-mpc-guardrail
description: Regras determinísticas de proteção patrimonial, limites de alocação por operação, Circuit Breaker de latência e protocolo de assinatura multipartidária (MPC/TSS).
triggers:
  - "guardrail"
  - "mpc"
  - "tss"
  - "risco"
  - "drawdown"
  - "circuit-breaker"
  - "slippage"
allowed-tools:
  - validate_order_risk
  - check_latency_breaker
  - request_mpc_signature
metadata:
  version: 1.0.0
  framework: agentskills
  pillar: "Pilar 3: Gateway Vault + Pilar 6: Infra Resilience"
---

# Risk Guardrail & MPC Custody Skill

Esta habilidade rege as validações de integridade financeira antes que qualquer proposta seja enviada para os nós de assinatura das redes blockchain ou APIs privadas das corretoras.

## 1. Princípios de Proteção de Capital
1. **Validação Determinística em Código Puro:** Nenhuma LLM pode revogar ou suavizar as regras do `RiskGuardrail`. Se uma regra for violada, o processo levanta `RiskGuardrailException` e a operação é terminada.
2. **Limites Operacionais Estritos:**
   - Valor máximo por ordem ($V_{\text{order}} \le \text{US\$ } 500,00$).
   - Tolerância máxima de slippage no livro ($\le 0.50\%$).
   - Trava de Drawdown acumulado diário ($DD_{\text{max}} \le \text{US\$ } 250,00$).

## 2. Circuit Breaker de Infraestrutura e Latência (Pilar 6)
- Se a latência RTT com a corretora ultrapassar $500\text{ ms}$, o estado do sistema transiciona para `HALF-OPEN`.
- Nenhuma nova ordem a mercado (*Taker*) é permitida enquanto o circuito estiver aberto.

## 3. Protocolo de Assinatura MPC/TSS (2-de-3)
- O Agente possui apenas o fragmento 1 da chave.
- O cofre local (`gateway-vault`) retém o fragmento 2 e só gera a assinatura criptográfica se o `RiskGuardrail` retornar aprovação explícita.
- O fragmento 3 permanece frio para recuperação de contingência.

## 4. Scripts e Referências
- Verificador de risco e assinatura: `scripts/verify_risk_and_mpc.py`
- Tabela de limites de segurança: `references/guardrail_rules.json`
