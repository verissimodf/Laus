"""
Módulo de Configuração e Gerenciamento de Credenciais Híbridas.

Compatível com execução local (Google Antigravity Desktop) e nuvem (Google Colab).
Regras definidas em AGENTS.md.
"""
import os
from typing import Optional

# Modelos padrão recomendados no AGENTS.md
DEFAULT_MODEL_FAST: str = "gemini-2.5-flash"
DEFAULT_MODEL_REASONING: str = "gemini-2.5-pro"
DEFAULT_MODEL_INTERACTION: str = "models/gemini-3.8-flash"


def get_gemini_api_key() -> str:
    """
    Recupera a chave da API Gemini de forma híbrida e transparente.

    1. Tenta carregar dos Secrets do Google Colab (userdata), se estiver rodando na nuvem.
    2. Tenta carregar do arquivo .env local no Antigravity Desktop via python-dotenv.
    3. Verifica se a variável já existe no os.environ.

    Returns:
        str: Chave da API Gemini.

    Raises:
        ValueError: Se a GEMINI_API_KEY não for encontrada nem no ambiente local nem no Colab.
    """
    # 1. Tenta carregar dos Secrets do Google Colab, se estiver rodando na nuvem
    try:
        from google.colab import userdata  # type: ignore
        key = userdata.get("GEMINI_API_KEY")
        if key:
            os.environ["GEMINI_API_KEY"] = key
            return key
    except ImportError:
        pass

    # 2. Tenta carregar do arquivo .env local no Antigravity Desktop
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "GEMINI_API_KEY não encontrada no .env local nem nos Secrets do Colab."
        )
    return key
