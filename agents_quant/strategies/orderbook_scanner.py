"""
Orderbook L2 Scanner & Preditor de Slippage VWAP (Pilar 2 - Laus Quant)
Extraído cirurgicamente de notebook experimental via @graft-surgical-refactor.

Monitora o livro de ofertas L2 em tempo real e calcula o preço médio ponderado
por volume (VWAP) e o slippage projetado para absorção da ordem na fila.
"""

import json
import math
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

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        if not isinstance(symbol, str) or not symbol or symbol != symbol.strip():
            raise ValueError("symbol deve ser um par de mercado válido")
        parts = symbol.split("-")
        if (
            len(parts) != 2
            or any(not part or not part.isascii() or not part.isalnum() for part in parts)
        ):
            raise ValueError("symbol deve usar o formato BASE-QUOTE")
        return symbol.upper()

    @staticmethod
    def _parse_levels(levels: Any, side: str) -> List[List[float]]:
        if not isinstance(levels, list) or not levels:
            raise ValueError(f"Livro {side} inválido ou vazio")
        parsed = []
        for level in levels:
            if not isinstance(level, (list, tuple)) or len(level) != 2:
                raise ValueError(f"Nível do livro {side} inválido")
            try:
                price, quantity = float(level[0]), float(level[1])
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError(f"Nível do livro {side} não numérico") from exc
            if (
                not math.isfinite(price)
                or not math.isfinite(quantity)
                or price <= 0
                or quantity <= 0
            ):
                raise ValueError(f"Preço e quantidade do livro {side} devem ser positivos e finitos")
            parsed.append([price, quantity])
        return parsed

    @staticmethod
    def _validate_source_timestamp(
        value: Any,
        now: Optional[float] = None,
        max_age_seconds: float = 10.0,
    ) -> float:
        if isinstance(value, bool):
            raise ValueError("Timestamp do livro ausente ou inválido")
        try:
            timestamp = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Timestamp do livro ausente ou inválido") from exc
        if not math.isfinite(timestamp):
            raise ValueError("Timestamp do livro deve ser finito")
        if timestamp > 1e14:
            timestamp /= 1e6
        elif timestamp > 1e11:
            timestamp /= 1e3
        current_time = time.time() if now is None else now
        age_seconds = current_time - timestamp
        if age_seconds < -2.0 or age_seconds > max_age_seconds:
            raise ValueError(f"Timestamp do livro fora da janela de frescor ({age_seconds:.3f}s)")
        return timestamp

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
        symbol = cls._validate_symbol(symbol)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout deve ser positivo e finito")
        ctx = ssl.create_default_context()

        # Tentativa 1: Mercado Bitcoin (Par nativo BRL)
        try:
            url = f"https://api.mercadobitcoin.net/api/v4/{symbol}/orderbook"
            req = urllib.request.Request(url, headers=cls.HEADERS)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                source_timestamp = data.get("timestamp", data.get("time"))
                cls._validate_source_timestamp(source_timestamp)
                received_at = time.time()
                return {
                    "source": "Mercado Bitcoin (Live Book)",
                    "symbol": symbol,
                    "bids": cls._parse_levels(data.get("bids"), "bids")[:15],
                    "asks": cls._parse_levels(data.get("asks"), "asks")[:15],
                    "timestamp": int(time.time()),
                    "source_timestamp": source_timestamp,
                    "received_at": received_at,
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
                if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask <= 0:
                    raise ValueError("Cotação fallback deve ser positiva e finita")
                return {
                    "source": "AwesomeAPI (Synthetic L2 Book Fallback)",
                    "symbol": symbol,
                    "bids": [[round(bid * (1.0 - 0.0005 * i), 4), 500.0 + i * 250.0] for i in range(8)],
                    "asks": [[round(ask * (1.0 + 0.0005 * i), 4), 500.0 + i * 250.0] for i in range(8)],
                    "timestamp": int(time.time()),
                    "source_timestamp": data.get("timestamp", data.get("time")),
                    "received_at": time.time(),
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
        if (
            isinstance(target_amount_usd, bool)
            or not isinstance(target_amount_usd, (int, float))
            or not math.isfinite(target_amount_usd)
            or target_amount_usd <= 0
        ):
            raise ValueError("target_amount_usd deve ser positivo e finito")
        validated_side = cls._parse_levels(book_side, "book_side")

        preco_topo = validated_side[0][0]
        restante_usd = float(target_amount_usd)
        custo_total_brl = 0.0
        volume_total_executado = 0.0

        for preco, qty in validated_side:
            volume_nivel_usd = qty  # Para USDT, 1 token ~ 1 USD
            consumir = min(restante_usd, volume_nivel_usd)
            custo_total_brl += consumir * preco
            volume_total_executado += consumir
            restante_usd -= consumir

            if restante_usd <= 0:
                break

        if restante_usd > max(1e-9, target_amount_usd * 1e-12):
            volume_disponivel = target_amount_usd - restante_usd
            raise ValueError(
                "Liquidez insuficiente no livro: "
                f"solicitado={target_amount_usd} USD, disponível={volume_disponivel} USD"
            )
        if volume_total_executado == 0:
            raise ValueError("Livro de ofertas sem liquidez executável")

        preco_medio_vwap = custo_total_brl / volume_total_executado
        slippage_pct = abs((preco_medio_vwap - preco_topo) / preco_topo) * 100.0

        return round(preco_topo, 4), round(preco_medio_vwap, 4), round(slippage_pct, 4)


if __name__ == "__main__":
    print("Testando OrderbookScanner...")
    book = OrderbookScanner.fetch_live_orderbook("USDT-BRL")
    print(f"Fonte: {book['source']}")
    top_ask, vwap_ask, slip = OrderbookScanner.calculate_vwap_slippage(book["asks"], 300.0)
    print(f"Top Ask: R$ {top_ask:.4f} | VWAP ($300): R$ {vwap_ask:.4f} | Slippage Projetado: {slip:.4f}%")
