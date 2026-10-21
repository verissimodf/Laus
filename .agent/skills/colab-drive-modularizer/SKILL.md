---
name: colab-drive-modularizer
description: Regras e padrões para modularização de experimentos em notebooks Jupyter (.ipynb) do Google Colab e prompts do Google AI Studio em código Python testável nos 8 pilares do Laus, respeitando as restrições de sincronização do Google Drive.
triggers:
  - "colab"
  - "notebook"
  - "ipynb"
  - "modularizar"
  - "ai studio"
  - "google drive"
  - "drive"
  - "refatorar"
---

# Colab & Drive Modularizer — Engenharia Híbrida

Esta habilidade orienta o processo de engenharia de software para transformar protótipos de prompts e códigos exploratórios gerados no **Google Colab** e **Google AI Studio** em módulos de produção para a plataforma Laus.

## 1. Restrições Rígidas do Google Drive
Como o repositório reside em pasta sincronizada pelo Google Drive para Desktop:
1. **PROIBIDO criar pastas `.venv` ou `node_modules` no diretório sincronizado:** Ambientes virtuais devem residir fora do Drive (ex.: `C:\Users\<Usuario>\.venvs\laus`).
2. **Preservação de Notebooks:** Nunca modifique a estrutura JSON interna de arquivos `.ipynb` diretamente com ferramentas que possam invalidar a sessão ativa no navegador. Prefira extrair a lógica pesada para arquivos `.py` na pasta `src/` ou no pilar correspondente.
3. **Casca de Visualização:** O notebook (`notebooks/main_colab.ipynb`) deve funcionar exclusivamente como casca fina (*thin shell*) para orquestração visual, testes exploratórios e plots.

---

## 2. Fluxo de Modularização de Código Exploratório

Sempre que o operador fornecer uma célula longa de Colab ou export do AI Studio:
1. **Identifique o Pilar Destino:**
   - Orquestração de Agentes e Intenções -> `core-jarvis/`
   - Estratégias Matemáticas e Sinais -> `agents-quant/`
   - Servidores e Conectores de Ordem -> `gateway-vault/`
   - Visualização e Interfaces -> `console-ui/`
   - Habilidades e Conectores de Dados -> `cognition-skills/`
   - Resiliência e Watchdogs -> `infra-resilience/`
   - Simulação e Validação Shadow -> `digital-twin/`
   - Contabilidade e Compliance Fiscal -> `ledger-compliance/`
   - Utilitários globais e clientes de IA -> `src/`

2. **Refatore com Tipagem e Docstrings:**
   - Converta scripts imperativos em funções puras ou classes assíncronas com Type Hints (`typing`) e Pydantic.
   - Isole chaves de API e URLs fixas em variáveis de ambiente recuperadas via `src.config.get_gemini_api_key()`.

3. **Atualize o `requirements.txt`:**
   - Adicione qualquer biblioteca externa necessária para que ela possa ser instalada no Colab via `!pip install -r requirements.txt`.

---

## 3. Padrão de Cabeçalho dos Notebooks no Colab

Os notebooks em `notebooks/` devem sempre abrir com a célula padronizada:

```python
# Célula 1 do Google Colab: Montar Drive e ativar Autoreload dos módulos .py
from google.colab import drive
import sys

drive.mount('/content/drive')

PROJECT_PATH = '/content/drive/MyDrive/Laus_Docs'
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

%load_ext autoreload
%autoreload 2
```

Dessa forma, qualquer alteração salva nos módulos `.py` pelo Antigravity Desktop reflete instantaneamente nas execuções de células no Colab sem necessidade de reiniciar o runtime.
