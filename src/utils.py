"""
Módulo de Funções Utilitárias e Processamento de Dados.

Contém helpers para manipulação de arquivos, formatação de respostas de modelos,
sanitização de JSON e utilitários gerais compatíveis com execução local e Colab.
Regras definidas em AGENTS.md.
"""
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union


def clean_json_markdown(raw_text: str) -> str:
    """
    Remove blocos de formatação markdown (```json ... ```) frequentemente
    retornados por LLMs, deixando apenas a string JSON pura.

    Args:
        raw_text: Texto potencialmente envolvido por markdown backticks.

    Returns:
        str: Texto sanitizado contendo apenas o corpo JSON.
    """
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.search(pattern, raw_text.strip(), flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw_text.strip()


def parse_safe_json(raw_text: str) -> Dict[str, Any]:
    """
    Decodifica com segurança uma string em JSON, limpando eventuais marcações markdown.

    Args:
        raw_text: String contendo JSON.

    Returns:
        Dict[str, Any]: Estrutura deserializada.

    Raises:
        json.JSONDecodeError: Se o conteúdo não for um JSON válido.
    """
    cleaned = clean_json_markdown(raw_text)
    return json.loads(cleaned)


def ensure_directory(path: Union[str, Path]) -> Path:
    """
    Garante que um diretório exista, criando-o caso necessário.

    Args:
        path: Caminho do diretório.

    Returns:
        Path: Instância de Path do diretório garantido.
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def save_json(
    data: Any,
    file_path: Union[str, Path],
    indent: int = 2,
    ensure_ascii: bool = False,
) -> None:
    """
    Salva dados serializáveis em arquivo JSON com formatação legível.

    Args:
        data: Objeto Python serializável.
        file_path: Destino do arquivo.
        indent: Espaçamento de indentação.
        ensure_ascii: Se caracteres não-ASCII devem ser escapados.
    """
    dest = Path(file_path)
    ensure_directory(dest.parent)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)


def load_json(file_path: Union[str, Path]) -> Any:
    """
    Carrega dados de um arquivo JSON com codificação UTF-8.

    Args:
        file_path: Caminho do arquivo a ser lido.

    Returns:
        Any: Dados parseados do JSON.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
