---
name: macro-brazil
description: Monitora cotações oficiais do par USD-BRL e validação bancária via AwesomeAPI e BrasilAPI, calculando spreads de arbitragem cambial contra stablecoins (USDT/USDC).
triggers:
  - "cambio"
  - "usd-brl"
  - "awesomeapi"
  - "brasilapi"
  - "spread"
  - "arbitragem"
  - "stablecoin"
allowed-tools:
  - fetch_usd_brl
  - validate_bank
  - compute_net_spread
metadata:
  version: 1.1.0
  framework: agentskills
  pillar: "Pilar 5: Cognition & Skills Hub"
---

# Macro Brazil & FX Arbitrage Skill

Esta habilidade operacional é responsável pelo monitoramento contínuo das taxas cambiais do dólar comercial brasileiro e cálculo de oportunidades de arbitragem espacial/cambial contra stablecoins lastreadas em dólar (`USDT/BRL`, `USDC/BRL`).

## 1. Conectores e Endpoints
- **AwesomeAPI Moedas:** `https://economia.awesomeapi.com.br/json/last/USD-BRL`
- **BrasilAPI Bancos:** `https://brasilapi.com.br/api/banks/v1`

## 2. Fluxo de Execução
1. Consulta a cotação `ask` do dólar comercial fiduciário ($P_{\text{fiat}}$).
2. Consulta o preço médio ponderado no livro de ofertas (*VWAP*) do par de stablecoin na corretora ($P_{\text{crypto}}$).
3. Desconta os custos operacionais agregados:
   - Taxa de negociação na corretora ($f_{\text{maker/taker}}$): ex. $0.10\%$
   - Taxa de rede / saque cripto ($f_{\text{withdrawal}}$): convertida em BRL
   - Custo de liquidação fiduciária PIX/TED ($f_{\text{pix}}$)
   - Estimativa de slippage na execução ($s_{\text{slippage}}$)
4. Avalia a condição de ativação: se $\Delta_{\text{net}} > 0.65\%$, emite proposta de arbitragem para o `core-jarvis`.

## 3. Scripts Operacionais
- Monitor e verificador: `scripts/usd_brl_monitor.py`
