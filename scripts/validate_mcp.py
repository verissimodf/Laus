"""Validate the deployed container through the real MCP stdio protocol."""
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main():
    root = Path(__file__).resolve().parents[1]
    server = StdioServerParameters(command="docker", args=["compose", "-f", str(root / "docker-compose.paper.yml"),
                                  "--profile", "tools", "run", "--rm", "-T", "mcp"])
    async with Client(server) as client:
        listing = await client.list_tools()
        names = sorted(tool.name for tool in listing.tools)
        assert names == ["laus_market_scan_depth", "laus_simulate_swarm", "laus_validate_order_proposal", "laus_verify_bank"]
        result = await client.call_tool("laus_validate_order_proposal", {"symbol": "USDT-BRL", "amount_usd": 100,
                                                                        "estimated_slippage": 0.1})
        encoded = result.model_dump(mode="json")
        assert "PROPOSAL_VALIDATED" in json.dumps(encoded)
        evidence = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "transport": "stdio",
                    "containerized": True, "tools": names, "validation_result": encoded,
                    "live_execution_enabled": False}
    (root / "docs" / "validation-mcp.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"transport": "stdio", "tools": names, "validation_passed": True}, indent=2))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=90))
