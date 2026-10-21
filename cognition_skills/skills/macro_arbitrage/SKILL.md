---
name: macro-fx-arbitrage
description: Executa análise de paridade entre cotações fiat locais (BRL/USD) e pares cripto estáveis (USDT/BRL).
allowed-tools:
  - fetch_usd_brl
  - validate_bank_clearing
  - evaluate_slippage
metadata:
  version: 1.0.0
  framework: agentskills
  author: Laus
---

# Procedimento Operacional Padrão

## 1. Monitoramento Macro
- Execute polling na **AwesomeAPI** para capturar o spread *bid/ask* de USD-BRL.
- Compare com o preço de USDT-BRL nas exchanges locais (ex.: Mercado Bitcoin, Binance P2P/Spot).

## 2. Validação de Risco e Custos
- Aplique custos operacionais (IOF sintético, taxa de saque fiat e gas fee).
- Se o spread líquido for superior a **0.65%**, envie sinal de arbitragem para validação do `RiskGuardrail`.
