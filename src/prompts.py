"""
Módulo de Prompts e System Instructions.

Centraliza todas as System Instructions, templates e Few-Shot Prompts refinados
no Google AI Studio, mantendo a lógica de chamada isolada em ai_studio_client.py.
Regras definidas em AGENTS.md.
"""
from typing import Any, Dict


# System Instructions padrão
DEFAULT_SYSTEM_INSTRUCTION: str = (
    "Você é um assistente técnico especialista em engenharia de software e análise quantitativa. "
    "Responda de forma concisa, precisa, orientada a código limpo e padrões de arquitetura."
)

CODE_ANALYSIS_SYSTEM_INSTRUCTION: str = (
    "Você é um engenheiro de software sênior focado em refatoração, boas práticas e tipagem estrita em Python. "
    "Analise o código fornecido, aponte potenciais gargalos, incompatibilidades e sugira melhorias com Type Hints."
)

DATA_EXTRACTION_SYSTEM_INSTRUCTION: str = (
    "Você é um extrator de dados estruturados. Extraia com precisão as informações solicitadas "
    "seguindo rigorosamente o esquema fornecido, sem comentários adicionais."
)

AGENTIC_TASK_PROMPT_TEMPLATE: str = (
    "Por favor, execute a seguinte tarefa utilizando as ferramentas disponíveis "
    "(busca na web, execução de código e contexto de URL) conforme necessário:\n\n{task}"
)


def format_prompt(template: str, **kwargs: Any) -> str:
    """
    Formata um template de prompt com as variáveis fornecidas.

    Args:
        template: String com marcadores de interpolação no padrão str.format ({var}).
        **kwargs: Variáveis a serem interpoladas no template.

    Returns:
        str: Prompt formatado.
    """
    return template.format(**kwargs)
