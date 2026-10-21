"""
Pacote src - Módulos do Sistema de IA e Agentes Antigravity / Colab.

Estrutura organizada conforme as diretrizes do AGENTS.md:
- config: Resolução e compatibilidade de credenciais híbridas (Local / Colab)
- ai_studio_client: Cliente e wrappers oficiais Google GenAI SDK (google-genai) e Interactions API
- prompts: Centralização de templates e system instructions
- utils: Utilitários auxiliares de dados, arquivos e JSON
"""

from src.config import (
    DEFAULT_MODEL_FAST,
    DEFAULT_MODEL_INTERACTION,
    DEFAULT_MODEL_REASONING,
    get_gemini_api_key,
)
from src.ai_studio_client import (
    DEFAULT_INTERACTION_GENERATION_CONFIG,
    DEFAULT_INTERACTION_TOOLS,
    create_interaction,
    generate_structured,
    generate_text,
    generate_text_stream,
    get_client,
    run_interaction,
)
from src.prompts import (
    AGENTIC_TASK_PROMPT_TEMPLATE,
    CODE_ANALYSIS_SYSTEM_INSTRUCTION,
    DATA_EXTRACTION_SYSTEM_INSTRUCTION,
    DEFAULT_SYSTEM_INSTRUCTION,
    format_prompt,
)
from src.utils import (
    clean_json_markdown,
    ensure_directory,
    load_json,
    parse_safe_json,
    save_json,
)

__all__ = [
    # Config
    "get_gemini_api_key",
    "DEFAULT_MODEL_FAST",
    "DEFAULT_MODEL_REASONING",
    "DEFAULT_MODEL_INTERACTION",
    # AI Studio Client
    "get_client",
    "generate_text",
    "generate_text_stream",
    "generate_structured",
    "create_interaction",
    "run_interaction",
    "DEFAULT_INTERACTION_TOOLS",
    "DEFAULT_INTERACTION_GENERATION_CONFIG",
    # Prompts
    "DEFAULT_SYSTEM_INSTRUCTION",
    "CODE_ANALYSIS_SYSTEM_INSTRUCTION",
    "DATA_EXTRACTION_SYSTEM_INSTRUCTION",
    "AGENTIC_TASK_PROMPT_TEMPLATE",
    "format_prompt",
    # Utils
    "clean_json_markdown",
    "parse_safe_json",
    "ensure_directory",
    "save_json",
    "load_json",
]
