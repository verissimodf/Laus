"""
Laus Swarm LLM Engine — Pilares 2 e 5 (MiroFish Multi-Agent Reasoning)
Extraído cirurgicamente de notebook experimental via @graft-surgical-refactor.

Submete métricas L2 e macro a personas especializadas via LLM ou motor
heurístico determinístico com quórum qualificado e score de consenso ponderado.
"""

import json
import logging
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("LausCognitiveSwarm")

# Adiciona diretório raiz para integração com src/
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))


class LLMProvider:
    """Provedor agnóstico de chamadas HTTP para APIs de LLM."""

    @staticmethod
    def query_gemini(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """Consulta o Google Gemini via src.ai_studio_client se a credencial estiver configurada."""
        try:
            from src.ai_studio_client import generate_structured
            from pydantic import BaseModel, Field

            class SwarmVoteSchema(BaseModel):
                approves: bool = Field(description="Voto de aprovação da persona")
                confidence: float = Field(ge=0.0, le=1.0, description="Nível de confiança entre 0.0 e 1.0")
                reasoning: str = Field(description="Justificativa técnica sintética da decisão")

            res_text = generate_structured(
                prompt=user_prompt,
                response_schema=SwarmVoteSchema,
                system_instruction=system_prompt,
            )
            return json.loads(res_text)
        except Exception as e:
            logger.debug(f"Gemini indisponível ou não configurado para o Swarm: {e}")
            return None

    @staticmethod
    def query_groq(
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        model: str = "llama-3.3-70b-versatile",
        timeout: int = 8,
    ) -> Optional[Dict[str, Any]]:
        """Consulta a API da Groq."""
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LausSwarm/1.0",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return json.loads(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug(f"Groq API call error: {e}")
            return None

    @staticmethod
    def query_openai(
        api_key: str,
        system_prompt: str,
        user_prompt: str,
        model: str = "gpt-4o-mini",
        timeout: int = 8,
    ) -> Optional[Dict[str, Any]]:
        """Consulta a API da OpenAI."""
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            ctx = ssl.create_default_context()
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return json.loads(data["choices"][0]["message"]["content"])
        except Exception as e:
            logger.debug(f"OpenAI API call error: {e}")
            return None


class MiroFishCognitiveSwarm:
    """
    Comitê Cognitivo MiroFish com deliberação por agentes especialistas.
    Suporta Gemini, Groq, OpenAI e fallback heurístico determinístico.
    """

    def __init__(
        self,
        groq_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
        enable_gemini: bool = True,
    ):
        self.groq_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.enable_gemini = enable_gemini

        # Definição das Personas do Comitê e seus pesos
        self.personas: List[Dict[str, Any]] = [
            {
                "id": "Conservative_Risk_Officer",
                "role": "Diretor de Risco Conservador",
                "focus": "Preservação estrita de capital, teto de slippage (< 0.20%) e aversão a volatilidade.",
                "weight": 0.40,
            },
            {
                "id": "Macro_Trend_Follower",
                "role": "Analista Macroeconômico",
                "focus": "Spread de paridade cambial USD-BRL, viabilidade da janela e custo de oportunidade.",
                "weight": 0.30,
            },
            {
                "id": "HFT_Liquidity_Hunter",
                "role": "Caçador de Liquidez de Alta Frequência",
                "focus": "Profundidade de livro L2, latência de execução e spread líquido após taxas.",
                "weight": 0.30,
            },
        ]

    def _build_prompt(self, persona: Dict[str, Any], market_context: Dict[str, Any]) -> str:
        return f"""Você é {persona['role']} ({persona['id']}).
Seu foco estrito de decisão é: {persona['focus']}

DADOS DE MERCADO EM TEMPO REAL:
- Par: {market_context.get('symbol', 'USDT-BRL')}
- Volume pretendido: ${market_context.get('volume_usd', 0.0):.2f} USD
- Melhor Oferta Compra (Bid): R$ {market_context.get('best_bid', 0.0):.4f}
- Melhor Oferta Venda (Ask): R$ {market_context.get('best_ask', 0.0):.4f}
- Preço VWAP Médio: R$ {market_context.get('ask_vwap', 0.0):.4f}
- Slippage L2 Estimado: {market_context.get('slippage_pct', 0.0):.4f}%
- Spread Bruto da Janela: {market_context.get('spread_pct', 0.0):.4f}%
- Provedor do Livro: {market_context.get('source', 'Unknown')}

RESPONDA OBRIGATORIAMENTE EM JSON NO FORMATO:
{{
  "approves": true ou false,
  "confidence": número float entre 0.0 e 1.0,
  "reasoning": "Sua justificativa técnica sintética (máximo 2 frases)"
}}
"""

    def evaluate_opportunity(self, market_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submete o contexto aos agentes especialistas e calcula o quórum de aprovação.

        Args:
            market_context: Dicionário contendo dados de livro L2 e spread.

        Returns:
            Dict com 'authorized', 'consensus_score' e lista detalhada de 'votes'.
        """
        votes: List[Dict[str, Any]] = []

        for p in self.personas:
            vote_data: Optional[Dict[str, Any]] = None
            prompt = self._build_prompt(p, market_context)

            # 1. Tenta Gemini (SDK oficial do projeto)
            if self.enable_gemini and not vote_data:
                try:
                    vote_data = LLMProvider.query_gemini(
                        "Você é um agente quantitativo institucional focado em trading algorítmico e arbitragem.",
                        prompt,
                    )
                    if vote_data:
                        vote_data["engine"] = "Google Gemini (Official SDK)"
                except Exception:
                    pass

            # 2. Tenta Groq (Llama-3)
            if self.groq_key and not vote_data:
                vote_data = LLMProvider.query_groq(
                    self.groq_key,
                    "Você é um agente quantitativo institucional focado em trading algorítmico e arbitragem.",
                    prompt,
                )
                if vote_data:
                    vote_data["engine"] = "Groq Llama-3"

            # 3. Tenta OpenAI
            if self.openai_key and not vote_data:
                vote_data = LLMProvider.query_openai(
                    self.openai_key,
                    "Você é um agente quantitativo institucional focado em trading algorítmico e arbitragem.",
                    prompt,
                )
                if vote_data:
                    vote_data["engine"] = "OpenAI GPT-4o-mini"

            # 4. Fallback Heurístico Determinístico (resiliente, offline)
            if not vote_data:
                slip = float(market_context.get("slippage_pct", 0.0))
                spr = float(market_context.get("spread_pct", 0.0))
                approves = slip < 0.35 and spr >= 0.40
                conf = 0.88 if approves else 0.50
                vote_data = {
                    "approves": approves,
                    "confidence": conf,
                    "reasoning": f"Análise determinística: slippage de {slip:.4f}% dentro do limite de segurança.",
                    "engine": "Deterministic Heuristic Engine",
                }

            votes.append({
                "persona": p["id"],
                "role": p["role"],
                "weight": p["weight"],
                "approves": bool(vote_data.get("approves", False)),
                "confidence": float(vote_data.get("confidence", 0.0)),
                "reasoning": str(vote_data.get("reasoning", "Sem justificativa fornecida")),
                "engine": vote_data.get("engine", "Unknown"),
            })

        # Cálculo do Quórum Ponderado
        total_w = sum(v["weight"] for v in votes)
        approval_w = sum(v["weight"] * v["confidence"] for v in votes if v["approves"])
        consensus_score = approval_w / total_w if total_w > 0 else 0.0

        return {
            "authorized": consensus_score >= 0.55,
            "consensus_score": round(consensus_score, 3),
            "votes": votes,
        }


if __name__ == "__main__":
    swarm = MiroFishCognitiveSwarm()
    context = {
        "symbol": "USDT-BRL",
        "volume_usd": 250.0,
        "best_bid": 5.0230,
        "best_ask": 5.0680,
        "ask_vwap": 5.0720,
        "slippage_pct": 0.08,
        "spread_pct": 0.89,
        "source": "Mercado Bitcoin / AwesomeAPI",
    }
    decision = swarm.evaluate_opportunity(context)
    print("Parecer do Comitê Cognitivo Swarm:")
    print(f"Autorizado: {decision['authorized']} | Consenso: {decision['consensus_score']*100:.1f}%")
    for v in decision["votes"]:
        print(f"  [{v['persona']}]: {'APROVADO' if v['approves'] else 'REPROVADO'} ({v['confidence']*100:.0f}%) -> {v['reasoning']}")
