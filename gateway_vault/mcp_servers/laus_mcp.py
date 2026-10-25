"""
Laus MCP Server — Model Context Protocol Gateway (Pilar 3)
Em estrita conformidade com a skill @mcp-ccxt-builder.

Expõe ferramentas tipadas de mercado, consenso de enxame, validação no Guardrail
e liquidação contábil para agentes autônomos (Claude, Cursor, Antigravity, LLMs).
Nenhuma ordem executa diretamente em corretoras sem validação determinística prévia.
"""

import json
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Injeta caminhos de resolução de pacotes dos 8 Pilares
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

guardrail_dir = project_root / "gateway_vault" / "guardrail"
if str(guardrail_dir) not in sys.path:
    sys.path.insert(0, str(guardrail_dir))

strategies_dir = project_root / "agents_quant" / "strategies"
if str(strategies_dir) not in sys.path:
    sys.path.insert(0, str(strategies_dir))

swarm_dir = project_root / "agents_quant" / "mirofish_sim"
if str(swarm_dir) not in sys.path:
    sys.path.insert(0, str(swarm_dir))

ledger_dir = project_root / "accounting_ledger"
if str(ledger_dir) not in sys.path:
    sys.path.insert(0, str(ledger_dir))

macro_scripts_dir = project_root / "cognition_skills" / "skills" / "macro_brazil" / "scripts"
if str(macro_scripts_dir) not in sys.path:
    sys.path.insert(0, str(macro_scripts_dir))

telemetry_scripts_dir = project_root / "cognition_skills" / "skills" / "posthog_telemetry" / "scripts"
if str(telemetry_scripts_dir) not in sys.path:
    sys.path.insert(0, str(telemetry_scripts_dir))

from risk_validator import RiskGuardrail, RiskGuardrailException
from orderbook_scanner import OrderbookScanner
from swarm_engine import MiroFishSwarmSimulator
from ledger_engine import AccountingLedger
from usd_brl_monitor import fetch_brazilian_banks
from emit_posthog_event import capture_laus_event

logger = logging.getLogger("LausMCPServer")


class LausMCPServer:
    """
    Servidor MCP (Model Context Protocol) do ecossistema Laus.
    Fornece interface padronizada com ferramentas JSON-RPC para consumo de agentes autônomos.
    """

    def __init__(
        self,
        scanner: Optional[OrderbookScanner] = None,
        swarm: Optional[MiroFishSwarmSimulator] = None,
        guardrail: Optional[RiskGuardrail] = None,
        ledger: Optional[AccountingLedger] = None,
        db_path: Optional[str] = None,
    ):
        self.scanner = scanner or OrderbookScanner()
        self.swarm = swarm or MiroFishSwarmSimulator()
        self.guardrail = guardrail or RiskGuardrail()
        
        target_db = db_path or str(project_root / "accounting_ledger" / "laus_vault.db")
        self.ledger = ledger or AccountingLedger(target_db)

    @staticmethod
    def _finite_numeric_argument(value: Any, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} deve ser um número JSON finito")
        return float(value)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Retorna o esquema de ferramentas expostas pelo protocolo MCP."""
        return [
            {
                "name": "mcp_market_scan_depth",
                "description": "Lê o livro de ofertas L2 e calcula preço médio ponderado (VWAP) e slippage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Par de negociação (ex: USDT-BRL)"},
                        "volume_usd": {"type": "number", "description": "Volume pretendido em USD"}
                    },
                    "required": ["volume_usd"]
                }
            },
            {
                "name": "mcp_swarm_evaluate",
                "description": "Executa consenso simulado multiagente (MiroFish) sobre a oportunidade.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "spread_pct": {"type": "number", "description": "Spread líquido projetado em %"},
                        "slippage_pct": {"type": "number", "description": "Slippage L2 medido em %"}
                    },
                    "required": ["spread_pct", "slippage_pct"]
                }
            },
            {
                "name": "mcp_stage_order",
                "description": (
                    "Valida apenas limites por ordem (valor e slippage); não consulta "
                    "limites diários nem envia ou executa ordem."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Símbolo da moeda/par"},
                        "amount_usd": {"type": "number", "description": "Valor da ordem em USD"},
                        "estimated_slippage": {"type": "number", "description": "Slippage estimado em %"}
                    },
                    "required": ["symbol", "amount_usd", "estimated_slippage"]
                }
            },
            {
                "name": "mcp_bank_verify",
                "description": "Valida instituição bancária SPB e código ISPB via BrasilAPI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_or_ispb": {"type": "string", "description": "Código de compensação COMPE ou ISPB"}
                    },
                    "required": ["code_or_ispb"]
                }
            }
        ]

    def handle_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ponto de entrada unificado para execução de chamadas MCP (JSON-RPC).
        Garante tratamento de exceções, auditoria e telemetria.
        """
        logger.info(f"MCP Tool Invocation: {tool_name}")

        if tool_name == "mcp_market_scan_depth":
            symbol = arguments.get("symbol", "USDT-BRL")
            volume_usd = self._finite_numeric_argument(arguments["volume_usd"], "volume_usd")
            if volume_usd <= 0:
                raise ValueError("volume_usd deve ser positivo")
            book = self.scanner.fetch_live_orderbook(symbol)
            topo_bid, vwap_bid, slip_bid = self.scanner.calculate_vwap_slippage(book["bids"], volume_usd)
            topo_ask, vwap_ask, slip_ask = self.scanner.calculate_vwap_slippage(book["asks"], volume_usd)
            
            return {
                "source": book["source"],
                "symbol": symbol,
                "best_bid": topo_bid,
                "best_ask": topo_ask,
                "ask_vwap": vwap_ask,
                "ask_slippage_pct": slip_ask,
                "spread_bruto_pct": round(((topo_ask - topo_bid) / topo_bid) * 100, 3) if topo_bid > 0 else 0.0,
                "timestamp": book["timestamp"],
                "source_timestamp": book.get("source_timestamp"),
                "received_at": book.get("received_at"),
                "freshness_verified": book.get("freshness_verified", False),
            }

        elif tool_name == "mcp_swarm_evaluate":
            spread_pct = self._finite_numeric_argument(arguments["spread_pct"], "spread_pct")
            slippage_pct = self._finite_numeric_argument(arguments["slippage_pct"], "slippage_pct")
            return self.swarm.simulate_consensus(spread_pct, slippage_pct)

        elif tool_name == "mcp_stage_order":
            symbol = arguments["symbol"]
            amount_usd = arguments["amount_usd"]
            slippage = arguments["estimated_slippage"]

            try:
                self.guardrail.validate_order(symbol, amount_usd, slippage)
                return {
                    "status": "PROPOSAL_VALIDATED",
                    "symbol": symbol,
                    "amount_usd": float(amount_usd),
                    "slippage_pct": float(slippage),
                    "validation_scope": "PER_ORDER_LIMITS_ONLY",
                    "daily_paper_limits_checked": False,
                    "guardrail_authorized": True,
                    "order_submitted": False
                }
            except RiskGuardrailException as e:
                # Registra evento de veto na telemetria PostHog
                capture_laus_event(
                    event_name="laus_guardrail_blocked",
                    distinct_id="mcp_gateway",
                    properties={
                        "symbol": symbol,
                        "amount_usd": amount_usd,
                        "reason": str(e),
                        "guardrail_code": "LIMIT_EXCEEDED"
                    }
                )
                return {
                    "status": "REJECTED_BY_GUARDRAIL",
                    "reason": str(e),
                    "validation_scope": "PER_ORDER_LIMITS_ONLY",
                    "daily_paper_limits_checked": False,
                    "guardrail_authorized": False,
                    "order_submitted": False
                }

        elif tool_name == "mcp_execute_hedged_trade":
            raise RuntimeError(
                "Execução e liquidação não estão implementadas; use o modo paper."
            )

        elif tool_name == "mcp_bank_verify":
            target = str(arguments["code_or_ispb"]).strip()
            banks = fetch_brazilian_banks(limit=100)
            matched = [
                b for b in banks 
                if str(b.get("code")) == target or str(b.get("ispb")) == target
            ]
            if matched:
                return {"valid": True, "bank": matched[0]}
            return {"valid": False, "reason": f"Instituição com código/ISPB '{target}' não localizada"}

        else:
            raise ValueError(f"Ferramenta MCP desconhecida: {tool_name}")


if __name__ == "__main__":
    server = LausMCPServer()
    print("=" * 60)
    print("🔐 TESTE OPERACIONAL DO SERVIDOR MCP (GATEWAY VAULT)")
    print("=" * 60)

    # 1. Lista ferramentas
    tools = server.list_tools()
    print(f"[OK] Ferramentas MCP Registradas: {len(tools)}")
    for t in tools:
        print(f"  • {t['name']}: {t['description']}")

    # 2. Teste de Scan L2
    scan_res = server.handle_call_tool("mcp_market_scan_depth", {"volume_usd": 250.0, "symbol": "USDT-BRL"})
    print(f"\n[OK] Scan L2 Result:")
    print(f"  Fonte: {scan_res['source']} | Best Ask: R$ {scan_res['best_ask']:.4f} | VWAP: R$ {scan_res['ask_vwap']:.4f}")

    # 3. Teste de Validação Guardrail
    guard_ok = server.handle_call_tool("mcp_stage_order", {"symbol": "USDT/BRL", "amount_usd": 250.0, "estimated_slippage": 0.15})
    print(f"\n[OK] Staged Order Check: Status={guard_ok['status']} (Authorized={guard_ok['guardrail_authorized']})")

    # 4. Teste de Veto Guardrail
    guard_veto = server.handle_call_tool("mcp_stage_order", {"symbol": "USDT/BRL", "amount_usd": 850.0, "estimated_slippage": 0.15})
    print(f"[OK] Staged Veto Check: Status={guard_veto['status']} | Motivo={guard_veto.get('reason')}")
    print("=" * 60)
