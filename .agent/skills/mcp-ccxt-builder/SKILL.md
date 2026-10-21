---
name: mcp-ccxt-builder
description: Define os padrões arquiteturais para criação e manutenção de servidores MCP (Model Context Protocol) dentro de gateway-vault/mcp_servers/, impondo validação determinística pelo risk_guardrail antes de qualquer execução em corretoras.
triggers:
  - "mcp"
  - "ccxt"
  - "gateway-vault"
  - "risk_guardrail"
  - "order"
  - "ordem"
  - "corretora"
  - "exchange"
---

# MCP CCXT & Execution Server Builder — Gateway Vault (Pilar 3)

Esta habilidade rege a construção de servidores **Model Context Protocol (MCP)** para integração com corretoras de criptoativos e finanças descentralizadas dentro do ecossistema Laus.

## 1. Princípio Fundamental de Isolamento
> **REGRA ZERO:** Nenhum agente autônomo (LLM) tem acesso direto às chaves de API das corretoras nem invoca diretamente a biblioteca CCXT sem mediação.
> Toda e qualquer intenção de negociação deve ser exposta como ferramenta MCP estritamente tipada e interceptada pelo validador determinístico `risk_guardrail`.

---

## 2. Fluxo Obrigatório de Execução de Ordens

```text
[Agente / Swarm]
       │
       ▼ (Chama MCP Tool com parâmetros JSON Schema)
[Servidor MCP (gateway-vault/mcp_servers/)]
       │
       ▼ (Submete Ordem Proposta para Validação Local)
[Risk Guardrail (gateway-vault/guardrail/risk_validator.py)]
       ├─► Reprovado: Retorna ToolError imediato ao Agente + emite laus_guardrail_blocked
       │
       ▼ Aprovado: Gera Token Assinado de Liberação
[Executor CCXT Pro / Assinador TSS MPC]
       │
       ▼ (Dispara Ordem na Corretora)
[Confirmação de Fill -> Barramento Redis -> Pilar 8 Ledger & PostHog]
```

---

## 3. Padrão de Nomenclatura das Ferramentas MCP

As ferramentas expostas pelos servidores MCP em `gateway-vault/mcp_servers/` devem seguir os prefixos canônicos:
1. `mcp_market_get_ticker(symbol: str)`: Consulta dados normalizados de livro de ofertas.
2. `mcp_market_get_depth(symbol: str, target_volume: float)`: Avalia profundidade e estima slippage.
3. `mcp_trade_propose_order(symbol: str, side: str, order_type: str, amount: float, price: float, strategy_id: str)`: Submete a proposta ao `risk_guardrail`.
4. `mcp_trade_cancel_order(symbol: str, order_id: str)`: Cancela ordens ativas.
5. `mcp_settlement_verify_bank(ispb: str)`: Validação de instituição bancária na BrasilAPI.

---

## 4. Regras Determinísticas do Risk Guardrail
Antes de qualquer envio à corretora via CCXT, o servidor MCP deve executar as seguintes travas em código puro:
- **Limite de Exposição Máxima:** $V_{\text{ordem}} \le \alpha \cdot \text{Patrimônio}$ (definido no console).
- **Limite de Drawdown 24h:** Se perdas diárias ultrapassarem o limite, novas ordens são rejeitadas.
- **Circuit Breaker de Latência:** Se o RTT da corretora for superior a 500ms, rejeitar execuções a mercado.
- **Modo Shadow vs. Live:** Se o sistema estiver em Shadow Mode (`digital-twin`), a ordem deve ser despachada para o simulador `shadow_exchange` e nunca para a API real.

---

## 5. Template Padrão de Servidor MCP em Python

Ao criar novos servidores MCP em `gateway-vault/mcp_servers/`, utilize o padrão assíncrono com validação Pydantic e captura de exceções:

```python
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from gateway_vault.guardrail.risk_validator import RiskValidator

mcp = FastMCP("laus-exchange-gateway")
validator = RiskValidator()

class OrderProposal(BaseModel):
    symbol: str = Field(description="Par de negociação, ex: USDT/BRL")
    side: str = Field(description="'buy' ou 'sell'")
    amount: float = Field(gt=0, description="Quantidade do ativo base")
    price: float = Field(gt=0, description="Preço limite da ordem")
    strategy_id: str = Field(description="Identificador da estratégia solicitante")

@mcp.tool()
async def stage_exchange_order(proposal: OrderProposal) -> dict:
    """Valida a ordem no Guardrail antes da transmissão para o CCXT."""
    validation = await validator.validate_order(proposal.model_dump())
    if not validation["allowed"]:
        return {
            "status": "rejected",
            "reason": validation["reason"],
            "guardrail_code": validation["code"]
        }
    
    # Executa via CCXT Pro se aprovado
    return {"status": "submitted", "order_id": validation["order_id"]}
```
