from __future__ import annotations

"""
Módulo de Integração com a API Gemini / Google AI Studio.

Utiliza exclusivamente o SDK oficial google-genai (from google import genai).
Configuração de modelos, chamadas síncronas, streaming, saídas estruturadas
e suporte à nova Interactions API (Agentes com Code Execution, Search e Thinking).
Regras definidas em AGENTS.md.
"""
from typing import Any, Dict, Iterator, List, Optional, Type, Union
import logging

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    from pydantic import BaseModel
except ImportError:
    class BaseModel:
        pass

from src.config import (
    DEFAULT_MODEL_FAST,
    DEFAULT_MODEL_INTERACTION,
    DEFAULT_MODEL_REASONING,
    get_gemini_api_key,
)
from src.prompts import DEFAULT_SYSTEM_INSTRUCTION

logger = logging.getLogger("AIStudioClient")

# Ferramentas padrão para a Interactions API
DEFAULT_INTERACTION_TOOLS: List[Dict[str, str]] = [
    {"type": "code_execution"},
    {"type": "google_search"},
    {"type": "url_context"},
]

# Configuração padrão de geração para raciocínio estendido (Thinking)
DEFAULT_INTERACTION_GENERATION_CONFIG: Dict[str, Any] = {
    "max_output_tokens": 65536,
    "thinking_level": "medium",
}


def get_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Inicializa e retorna uma instância do cliente oficial Google GenAI.

    Se a chave não for fornecida explicitamente, ela será buscada de forma
    híbrida através de get_gemini_api_key() (.env local ou Secrets do Colab).

    Args:
        api_key: Chave opcional da API Gemini.

    Returns:
        genai.Client: Cliente configurado.
    """
    if genai is None:
        raise ImportError(
            "O SDK oficial 'google-genai' não está instalado neste ambiente. "
            "Execute 'pip install google-genai' ou execute este notebook no Google Colab."
        )
    effective_key = api_key or get_gemini_api_key()
    return genai.Client(api_key=effective_key)


def generate_text(
    prompt: str,
    system_instruction: Optional[str] = DEFAULT_SYSTEM_INSTRUCTION,
    model: str = DEFAULT_MODEL_FAST,
    temperature: Optional[float] = None,
    client: Optional[genai.Client] = None,
) -> str:
    """
    Executa a geração de conteúdo de texto via Gemini.

    Args:
        prompt: Conteúdo textual da consulta/instrução.
        system_instruction: Instrução de sistema (definida em prompts.py).
        model: Identificador do modelo ('gemini-2.5-flash' ou 'gemini-2.5-pro').
        temperature: Parâmetro opcional de aleatoriedade/criatividade.
        client: Instância opcional pré-existente de genai.Client.

    Returns:
        str: Resposta textual gerada pelo modelo.
    """
    ai_client = client or get_client()

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )

    response = ai_client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )

    return response.text or ""


def generate_text_stream(
    prompt: str,
    system_instruction: Optional[str] = DEFAULT_SYSTEM_INSTRUCTION,
    model: str = DEFAULT_MODEL_FAST,
    temperature: Optional[float] = None,
    client: Optional[genai.Client] = None,
) -> Iterator[str]:
    """
    Executa geração de texto em modo streaming (síncrono por chunks).

    Args:
        prompt: Conteúdo textual da consulta.
        system_instruction: Instrução de sistema.
        model: Identificador do modelo.
        temperature: Parâmetro opcional de temperatura.
        client: Instância opcional de genai.Client.

    Yields:
        str: Pedaços de texto conforme chegam do modelo.
    """
    ai_client = client or get_client()

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )

    for chunk in ai_client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=config,
    ):
        if chunk.text:
            yield chunk.text


def generate_structured(
    prompt: str,
    response_schema: Union[Type[BaseModel], Dict[str, Any]],
    system_instruction: Optional[str] = None,
    model: str = DEFAULT_MODEL_FAST,
    temperature: Optional[float] = None,
    client: Optional[genai.Client] = None,
) -> str:
    """
    Executa geração com saída estruturada estrita (JSON Schema / Pydantic).

    Args:
        prompt: Instrução/pergunta. Não duplique o esquema no prompt de texto.
        response_schema: Classe Pydantic BaseModel ou dicionário JSON Schema.
        system_instruction: Instrução de sistema opcional.
        model: Identificador do modelo.
        temperature: Parâmetro opcional de temperatura.
        client: Instância opcional de genai.Client.

    Returns:
        str: Resposta em JSON puro validado pelo esquema fornecido.
    """
    ai_client = client or get_client()

    if isinstance(response_schema, type) and issubclass(response_schema, BaseModel):
        schema_dict = response_schema.model_json_schema()
    else:
        schema_dict = response_schema

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        response_mime_type="application/json",
        response_json_schema=schema_dict,
    )

    response = ai_client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )

    return response.text or "{}"


def create_interaction(
    input_text: Union[str, List[Any]],
    model: str = DEFAULT_MODEL_INTERACTION,
    tools: Optional[List[Dict[str, Any]]] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    previous_interaction_id: Optional[str] = None,
    client: Optional[genai.Client] = None,
    **kwargs: Any,
) -> Any:
    """
    Cria uma interação via Gemini Interactions API com suporte a ferramentas e raciocínio.

    Args:
        input_text: Texto ou lista de entradas para a interação.
        model: Identificador do modelo ('models/gemini-3.8-flash' por padrão).
        tools: Lista de ferramentas (code_execution, google_search, url_context).
        generation_config: Configurações de raciocínio (thinking_level, max_output_tokens).
        previous_interaction_id: ID opcional de interação prévia para manter estado/conversa.
        client: Instância opcional de genai.Client.
        **kwargs: Parâmetros adicionais repassados para client.interactions.create.

    Returns:
        Any: Objeto Interaction retornado pelo SDK.
    """
    ai_client = client or get_client()

    effective_tools = tools if tools is not None else DEFAULT_INTERACTION_TOOLS
    effective_gen_config = (
        generation_config
        if generation_config is not None
        else DEFAULT_INTERACTION_GENERATION_CONFIG
    )

    call_params: Dict[str, Any] = {
        "model": model,
        "input": input_text,
        "tools": effective_tools,
        "generation_config": effective_gen_config,
        **kwargs,
    }

    if previous_interaction_id:
        call_params["previous_interaction_id"] = previous_interaction_id

    return ai_client.interactions.create(**call_params)


def run_interaction(
    input_text: Union[str, List[Any]],
    model: str = DEFAULT_MODEL_INTERACTION,
    tools: Optional[List[Dict[str, Any]]] = None,
    generation_config: Optional[Dict[str, Any]] = None,
    previous_interaction_id: Optional[str] = None,
    client: Optional[genai.Client] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Executa uma interação completa e retorna um dicionário estruturado com o
    último passo executado (interaction.steps[-1]), texto sintetizado e metadados.

    Args:
        input_text: Entrada de prompt ou comando.
        model: Modelo Gemini ('models/gemini-3.8-flash').
        tools: Ferramentas habilitadas (code_execution, google_search, url_context).
        generation_config: Configurações de raciocínio (thinking_level, tokens).
        previous_interaction_id: ID para continuação de contexto da interação.
        client: Instância opcional de genai.Client.
        **kwargs: Argumentos adicionais repassados à API.

    Returns:
        Dict[str, Any]: Dicionário contendo:
            - 'interaction': O objeto Interaction completo.
            - 'last_step': Último passo executado (steps[-1]), se houver.
            - 'output_text': Texto sintetizado final gerado.
            - 'interaction_id': Identificador único da interação.
    """
    interaction = create_interaction(
        input_text=input_text,
        model=model,
        tools=tools,
        generation_config=generation_config,
        previous_interaction_id=previous_interaction_id,
        client=client,
        **kwargs,
    )

    steps = getattr(interaction, "steps", None) or []
    last_step = steps[-1] if steps else None
    output_text = getattr(interaction, "output_text", None)
    interaction_id = getattr(interaction, "id", None)

    return {
        "interaction": interaction,
        "last_step": last_step,
        "output_text": output_text,
        "interaction_id": interaction_id,
    }
