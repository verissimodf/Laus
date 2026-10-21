#!/usr/bin/env python3
"""
Monitor Cambial Macro Brasil (AwesomeAPI + BrasilAPI)
Pilar 5: Cognition & Skills Hub — Laus Ecosystem

Consome cotações de USD-BRL e validação de instituições bancárias,
calculando o spread cambial contra pares de stablecoin (USDT/BRL, USDC/BRL).
"""

import json
import ssl
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AWESOME_API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
BRASIL_API_BANKS_URL = "https://brasilapi.com.br/api/banks/v1"

# Custos operacionais médios padrão para arbitragem
DEFAULT_MAKER_TAKER_FEE = 0.0010  # 0.10%
DEFAULT_WITHDRAWAL_FEE_BRL = 5.00  # R$ 5,00
DEFAULT_PIX_FEE = 0.0000          # PIX PJ/PF isento ou fixo
DEFAULT_SLIPPAGE = 0.0005         # 0.05% de slippage médio


def _http_get_json(url: str, timeout: int = 10) -> Any:
    """Executa requisição HTTP GET retornando dados deserializados em JSON."""
    headers = {
        "User-Agent": "Laus-Autonomous-Quant/1.0 (Pilar-5; Cognition-Skills)"
    }
    req = urllib.request.Request(url, headers=headers)
    ctx = ssl.create_default_context()
    
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw_data = response.read().decode(charset)
        return json.loads(raw_data)


def fetch_usd_brl_quote() -> Dict[str, Any]:
    """
    Obtém a cotação oficial do dólar comercial brasileiro da AwesomeAPI.

    Returns:
        Dict contendo bid, ask, high, low, pctChange e timestamp.
    """
    data = _http_get_json(AWESOME_API_URL)
    if "USDBRL" not in data:
        raise ValueError(f"Resposta inesperada da AwesomeAPI: {data}")
    
    quote = data["USDBRL"]
    return {
        "pair": "USD-BRL",
        "bid": float(quote["bid"]),
        "ask": float(quote["ask"]),
        "high": float(quote["high"]),
        "low": float(quote["low"]),
        "pct_change": float(quote["pctChange"]),
        "timestamp": quote.get("timestamp"),
        "create_date": quote.get("create_date"),
    }


def fetch_brazilian_banks(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Obtém a lista de bancos cadastrados no Sistema Financeiro Nacional via BrasilAPI.

    Args:
        limit: Quantidade de registros amostrais para retornar.

    Returns:
        Lista com as primeiras instituições cadastradas.
    """
    banks = _http_get_json(BRASIL_API_BANKS_URL)
    if not isinstance(banks, list):
        raise ValueError(f"Resposta inesperada da BrasilAPI: {type(banks)}")
    return banks[:limit]


def calculate_net_spread(
    p_crypto: float,
    p_fiat: float,
    capital_brl: float = 10000.0,
    maker_taker_fee: float = DEFAULT_MAKER_TAKER_FEE,
    withdrawal_fee_brl: float = DEFAULT_WITHDRAWAL_FEE_BRL,
    pix_fee: float = DEFAULT_PIX_FEE,
    slippage: float = DEFAULT_SLIPPAGE,
) -> Dict[str, float]:
    """
    Calcula o spread cambial líquido segundo a equação do Pilar 2 e Pilar 5:
    Delta_net = ((P_crypto - P_fiat) / P_fiat) - (f_fee + f_withdrawal + f_pix + s_slippage)

    Args:
        p_crypto: Preço de mercado da stablecoin (USDT/BRL ou USDC/BRL).
        p_fiat: Preço ask fiduciário do USD-BRL (AwesomeAPI).
        capital_brl: Capital total alocado na operação em BRL.
        maker_taker_fee: Taxa percentual de negociação na exchange.
        withdrawal_fee_brl: Custo fixo de transferência/saque em BRL.
        pix_fee: Taxa de liquidação bancária.
        slippage: Desvio estimado de preço no order book.

    Returns:
        Dicionário com spread bruto, taxas totais e spread líquido (em bps e %).
    """
    gross_spread = (p_crypto - p_fiat) / p_fiat
    withdrawal_fee_pct = withdrawal_fee_brl / max(capital_brl, 1.0)
    total_costs = maker_taker_fee + withdrawal_fee_pct + pix_fee + slippage
    net_spread = gross_spread - total_costs
    
    return {
        "p_crypto": p_crypto,
        "p_fiat": p_fiat,
        "gross_spread_pct": gross_spread * 100.0,
        "total_costs_pct": total_costs * 100.0,
        "net_spread_pct": net_spread * 100.0,
        "net_spread_bps": net_spread * 10000.0,
        "is_profitable": net_spread > 0.0065,  # Gatilho de 65 bps
    }


def run_diagnostics() -> Dict[str, Any]:
    """Executa verificação ponta a ponta dos conectores e calcula spread simulado."""
    results = {}
    print("=" * 65)
    print("⚡ LAUS ECOSYSTEM — DIAGNÓSTICO MACRO BRASIL (PILAR 5)")
    print("=" * 65)

    # 1. Teste AwesomeAPI
    try:
        quote = fetch_usd_brl_quote()
        results["awesomeapi"] = {"status": "SUCCESS", "quote": quote}
        print(f"[OK] AwesomeAPI USD-BRL:")
        print(f"     Bid: R$ {quote['bid']:.4f} | Ask: R$ {quote['ask']:.4f} | Variação: {quote['pct_change']:+.2f}%")
        p_fiat = quote["ask"]
    except Exception as e:
        results["awesomeapi"] = {"status": "ERROR", "error": str(e)}
        print(f"[FALHA] AwesomeAPI: {e}")
        p_fiat = 5.4000  # Fallback estático de segurança

    # 2. Teste BrasilAPI
    try:
        sample_banks = fetch_brazilian_banks(limit=3)
        results["brasilapi"] = {"status": "SUCCESS", "sample_count": len(sample_banks)}
        print(f"\n[OK] BrasilAPI Bancos (Amostra de Participantes SPB):")
        for bank in sample_banks:
            code = bank.get("code") or "N/A"
            name = bank.get("name") or bank.get("fullName") or "Desconhecido"
            print(f"     ISPB: {bank.get('ispb')} | Código: {code} | Instituição: {name[:30]}")
    except Exception as e:
        results["brasilapi"] = {"status": "ERROR", "error": str(e)}
        print(f"[FALHA] BrasilAPI: {e}")

    # 3. Cálculo de Arbitragem com Paridade Simulada USDT/BRL (+0.80% de prêmio cripto)
    simulated_usdt = round(p_fiat * 1.0085, 4)
    spread_analysis = calculate_net_spread(p_crypto=simulated_usdt, p_fiat=p_fiat)
    results["arbitrage_analysis"] = spread_analysis

    print(f"\n[ANÁLISE DE ARBITRAGEM SINTÉTICA (USDT vs USD Comercial)]:")
    print(f"     Preço Fiat (Ask):        R$ {p_fiat:.4f}")
    print(f"     Preço USDT (Simulado):   R$ {simulated_usdt:.4f}")
    print(f"     Spread Bruto:            {spread_analysis['gross_spread_pct']:+.3f}%")
    print(f"     Custos Operacionais:     -{spread_analysis['total_costs_pct']:.3f}%")
    print(f"     Spread Líquido Estimado: {spread_analysis['net_spread_pct']:+.3f}% ({spread_analysis['net_spread_bps']:+.1f} bps)")
    print(f"     Gatilho Ativado (>65bps): {'SIM [DISPARAR ORDEM]' if spread_analysis['is_profitable'] else 'NÃO [SPREAD INSUFICIENTE]'}")
    print("=" * 65)

    return results


if __name__ == "__main__":
    run_diagnostics()
