"""
Orderbook L2 Scanner & Preditor de Slippage VWAP (Pilar 2 - Laus Quant)
Extraído cirurgicamente de notebook experimental via @graft-surgical-refactor.

Monitora o livro de ofertas L2 em tempo real e calcula o preço médio ponderado
por volume (VWAP) e o slippage projetado para absorção da ordem na fila.
"""

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class OrderbookScanner:
    """
    Scanner de profundidade L2 com cálculo determinístico de VWAP e slippage.
    Possui suporte nativo a exchanges locais (Mercado Bitcoin) e contingência AwesomeAPI.
    """

    HEADERS: Dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
        "Accept": "application/json",
    }

    @classmethod
    def fetch_live_orderbook(cls, symbol: str = "USDT-BRL", timeout: int = 4) -> Dict[str, Any]:
        """
        Coleta o livro de ofertas L2 público.
        Tenta Mercado Bitcoin (nativo BRL) e faz fallback caso haja indisponibilidade.

        Args:
            symbol: Par de negociação (ex: 'USDT-BRL' ou 'BTC-BRL').
            timeout: Tempo limite da requisição HTTP em segundos.

        Returns:
            Dict com 'source', 'bids' [[price, qty]], 'asks' [[price, qty]] e 'timestamp'.
        """
        ctx = ssl.create_default_context()

        # Tentativa 1: Mercado Bitcoin (Par nativo BRL)
        try:
            url = f"https://api.mercadobitcoin.net/api/v4/orderbook?symbol={symbol}"
            req = urllib.request.Request(url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "source": "Mercado Bitcoin (Live Book)",
                    "symbol": symbol,
                    "bids": [[float(p), float(q)] for p, q in data.get("bids", [])[:15]],
                    "asks": [[float(p), float(q)] for p, q in data.get("asks", [])[:15]],
                    "timestamp": int(time.time()),
                }
        except Exception:
            pass

        # Tentativa 2: AwesomeAPI (fallback de cotação com livro sintético escalonado)
        try:
            url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
            req = urllib.request.Request(url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))["USDBRL"]
                bid = float(data["bid"])
                ask = float(data["ask"])
                return {
                    "source": "AwesomeAPI (Synthetic L2 Book Fallback)",
                    "symbol": symbol,
                    "bids": [[round(bid * (1.0 - 0.0005 * i), 4), 500.0 + i * 250.0] for i in range(8)],
                    "asks": [[round(ask * (1.0 + 0.0005 * i), 4), 500.0 + i * 250.0] for i in range(8)],
                    "timestamp": int(time.time()),
                }
        except Exception as e:
            raise RuntimeError(f"Falha em todos os provedores de livro de ofertas: {e}")

    @classmethod
    def calculate_vwap_slippage(
        cls,
        book_side: List[List[float]],
        target_amount_usd: float,
    ) -> Tuple[float, float, float]:
        """
        Calcula o preço médio ponderado por volume (VWAP) e o slippage projetado
        ao consumir o livro até satisfazer o volume pretendido.

        Args:
            book_side: Lista de níveis de preço [[preço, quantidade], ...] ordenados.
            target_amount_usd: Volume total da ordem em USD a ser consumido.

        Returns:
            Tuple[preco_topo, preco_medio_vwap, slippage_pct]
        """
        if not book_side:
            raise ValueError("Livro de ofertas vazio. Impossível calcular VWAP.")

        preco_topo = book_side[0][0]
        restante_usd = target_amount_usd
        custo_total_brl = 0.0
        volume_total_executado = 0.0

        for preco, qty in book_side:
            volume_nivel_usd = qty  # Para USDT, 1 token ~ 1 USD
            consumir = min(restante_usd, volume_nivel_usd)
            custo_total_brl += consumir * preco
            volume_total_executado += consumir
            restante_usd -= consumir

            if restante_usd <= 0:
                break

        if volume_total_executado == 0:
            return preco_topo, preco_topo, 0.0

        preco_medio_vwap = custo_total_brl / volume_total_executado
        slippage_pct = abs((preco_medio_vwap - preco_topo) / preco_topo) * 100.0

        return round(preco_topo, 4), round(preco_medio_vwap, 4), round(slippage_pct, 4)


if __name__ == "__main__":
    print("Testando OrderbookScanner...")
    book = OrderbookScanner.fetch_live_orderbook("USDT-BRL")
    print(f"Fonte: {book['source']}")
    top_ask, vwap_ask, slip = OrderbookScanner.calculate_vwap_slippage(book["asks"], 300.0)
    print(f"Top Ask: R$ {top_ask:.4f} | VWAP ($300): R$ {vwap_ask:.4f} | Slippage Projetado: {slip:.4f}%")
