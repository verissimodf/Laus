---
name: tax-ledger-in1888
description: Governança contábil por partidas dobradas, cálculo de preço médio ponderado (PMP), apuração de ganho de capital em BRL e geração de eventos da IN 1888/2019 da Receita Federal do Brasil.
triggers:
  - "in1888"
  - "tributario"
  - "fiscal"
  - "ledger"
  - "partidas-dobradas"
  - "ganho-de-capital"
  - "pmp"
allowed-tools:
  - record_journal_entry
  - compute_capital_gains
  - export_in1888_report
metadata:
  version: 1.0.0
  framework: agentskills
  pillar: "Pilar 8: Ledger Contábil & Compliance Fiscal"
---

# Tax Ledger & IN 1888 Compliance Skill

Esta habilidade operacional audita e registra todas as operações financeiras de arbitragem e negociação executadas pelos agentes, assegurando integridade contábil e conformidade com as normas tributárias brasileiras.

## 1. Livro-Razão de Partidas Dobradas
Toda movimentação financeira confirmada gera lançamentos onde débitos e créditos se equivalem:
- **Débito:** Ativo:Caixa:BRL ou Ativo:Cripto:USDT
- **Crédito:** Receita:Arbitragem ou Ativo:Banco
- **Taxas:** Despesa:Taxas:Exchange / Despesa:Taxas:Gas_Rede

## 2. Apuração Fiscal e Alertas IN 1888
1. Monitora o volume total mensal de alienações e transferências envolvendo carteiras externas e corretoras sem CNPJ brasileiro.
2. Dispara alerta no console quando o volume acumulado no mês atinge $80\%$ do limite de $\text{R\$ } 30.000,00$ da IN 1888.
3. Calcula a provisão de imposto sobre ganho de capital com base no Preço Médio Ponderado (PMP) das aquisições.

## 3. Scripts e Referências
- Motor de cálculo e relatório: `scripts/calculate_in1888_tax.py`
- Especificação tributária detalhada: `references/in1888_rules_spec.md`
