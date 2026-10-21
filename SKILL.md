# SKILL: Arbitragem Flash USDT/BRL

## Parameters
- MAX_SLIPPAGE: 0.40
- EXPIRATION_SEC: 12
- MIN_SPREAD_REQ: 0.50
- ROUTE: "Binance_Spot -> Gateway_MCP -> Foxbit_OTC"

## Execution Flow
1. Fetch live quotes via MacroDataConnector.
2. Run predictive multi-agent swarm analysis.
3. Validate risk margins on Gateway Guardrail.
4. Execute atomic orders on target ledger.

---
name: macro-brazil-arbitrage
description: Consulta taxas de câmbio USD-BRL e parâmetros bancários locais para cálculo de paridade de arbitragem.
allowed-tools:
  - fetch_awesome_exchange
  - fetch_brasilapi_banks
metadata:
  author: Laus Engine
  version: 1.0.0
---
# Instruções
1. Realize o polling da cotação comercial e turismo via AwesomeAPI.
2. Avalie spread de conversão fiat considerando liquidação local via código de compensação bancária (BrasilAPI).
3. Calcule o custo de oportunidade frente ao CDI sintético.