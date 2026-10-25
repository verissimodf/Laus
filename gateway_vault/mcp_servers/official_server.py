"""
Official MCP stdio entry point for safe, non-executing Laus tools.

Run from the repository root with:
    python -m gateway_vault.mcp_servers.official_server

Trade submission and settlement are intentionally not exposed. The current
ledger operation is a paper estimate and is not an exchange execution.
"""
from typing import Any

from mcp.server import MCPServer

from gateway_vault.mcp_servers.laus_mcp import LausMCPServer

# In-memory ledger avoids creating a persistent accounting database for a server
# that exposes only market reads, swarm simulation, and proposal validation.
backend = LausMCPServer(db_path=":memory:")
mcp = MCPServer(
    "Laus Safe Gateway",
    instructions=(
        "Read-only market and bank lookup, simulation, and risk validation only. "
        "No exchange order submission or financial settlement is available."
    ),
)


@mcp.tool(name="laus_market_scan_depth")
def market_scan_depth(symbol: str = "USDT-BRL", volume_usd: float = 250.0) -> dict[str, Any]:
    """Read market depth and return prices, source provenance, and estimated slippage."""
    return backend.handle_call_tool(
        "mcp_market_scan_depth",
        {"symbol": symbol, "volume_usd": volume_usd},
    )


@mcp.tool(name="laus_simulate_swarm")
def simulate_swarm(spread_pct: float, slippage_pct: float) -> dict[str, Any]:
    """Run the local simulated agent consensus for a hypothetical opportunity."""
    return backend.handle_call_tool(
        "mcp_swarm_evaluate",
        {"spread_pct": spread_pct, "slippage_pct": slippage_pct},
    )


@mcp.tool(name="laus_validate_order_proposal")
def validate_order_proposal(
    symbol: str,
    amount_usd: float,
    estimated_slippage: float,
) -> dict[str, Any]:
    """Validate proposal limits; this does not stage or submit an exchange order."""
    return backend.handle_call_tool(
        "mcp_stage_order",
        {
            "symbol": symbol,
            "amount_usd": amount_usd,
            "estimated_slippage": estimated_slippage,
        },
    )


@mcp.tool(name="laus_verify_bank")
def verify_bank(code_or_ispb: str) -> dict[str, Any]:
    """Look up a Brazilian bank by COMPE code or ISPB."""
    return backend.handle_call_tool(
        "mcp_bank_verify",
        {"code_or_ispb": code_or_ispb},
    )


if __name__ == "__main__":
    # Local MCP clients use stdio; SDK defaults to stdio and keeps stdout on-wire.
    mcp.run()
