# Diretrizes do Agente (AGENTS.md)

## 1. Visão Geral do Projeto e Ambiente
Este projeto utiliza um fluxo híbrido que integra três ambientes sincronizados via **Google Drive para Desktop**:
- **Google Antigravity (Desktop):** Ambiente principal para engenharia de software, criação de módulos Python (`.py`), refatoração, testes e integração de APIs.
- **Google Colab (Nuvem):** Ambiente de execução interativa e uso de GPU/TPU através de notebooks (`.ipynb`).
- **Google AI Studio:** Ambiente de prototipagem de prompts, ajustes de parâmetros de modelo e geração de esquemas estruturados (JSON/Pydantic).

---

## 2. Regras Críticas de Sincronização (Google Drive)
Como este workspace está localizado dentro de uma pasta sincronizada pelo Google Drive, o agente **DEVE** seguir rigorosamente estas restrições:
1. **PROIBIDO criar ambientes virtuais locais na pasta do projeto:** Nunca execute `python -m venv .venv` ou instale `node_modules` dentro deste diretório. Ambientes virtuais devem residir fora do Google Drive (ex: `C:\Users\<Usuario>\.venvs\<nome_do_projeto>` ou `~/.venvs/<nome_do_projeto>`).
2. **Cuidado com edição de arquivos `.ipynb`:** Evite modificar diretamente a estrutura JSON bruta de arquivos `.ipynb` para não corromper notebooks abertos no navegador (Colab). Prefira extrair a lógica pesada para arquivos `.py` na pasta `src/` e apenas importá-los no notebook.
3. **Cache e arquivos temporários:** Ao criar scripts que geram grandes volumes de cache, checkpoints ou logs temporários, direcione-os para uma pasta local fora do Drive ou garanta que sejam compactados.

---

## 3. Arquitetura Recomendada do Diretório
Ao criar ou organizar arquivos, mantenha a seguinte estrutura:

```text
├── AGENTS.md                 # Este arquivo de instruções para o Antigravity
├── .env                      # Chaves de API locais (NÃO compartilhar/commitar)
├── requirements.txt          # Dependências do projeto (instaladas no Colab e local)
├── notebooks/                # Notebooks (.ipynb) executados no Google Colab
│   └── main_colab.ipynb      # Notebook principal que importa os módulos de src/
├── src/                      # Código-fonte modularizado mantido pelo Antigravity
│   ├── __init__.py
│   ├── config.py             # Carregamento de variáveis (.env / userdata do Colab)
│   ├── ai_studio_client.py   # Integração com a API Gemini (SDK google-genai)
│   ├── prompts.py            # System instructions e templates vindos do AI Studio
│   └── utils.py              # Funções auxiliares e processamento de dados
└── data/                     # Datasets leves, entradas e resultados exportados
```

---

## 4. Padrões de Integração com o Google AI Studio (SDK Oficial)
Sempre que implementar ou atualizar chamadas para modelos Gemini exportados do Google AI Studio:
- **SDK Obrigatório:** Utilize exclusivamente o novo SDK `google-genai` (`from google import genai` e `from google.genai import types`). **NÃO** utilize a biblioteca legada `google-generativeai`.
- **Inicialização do Cliente:**
  ```python
  from google import genai
  from google.genai import types
  
  # O cliente busca automaticamente a variável de ambiente GEMINI_API_KEY
  client = genai.Client()
  ```
- **Modelos Padrão:** Utilize `gemini-2.5-flash` para tarefas gerais/rápidas e `gemini-2.5-pro` para raciocínio complexo e codificação, a menos que especificado de outra forma no prompt do AI Studio.
- **Separação de Prompts:** Todo *System Instruction* ou *Few-Shot Prompt* refinado no Google AI Studio deve ser salvo como constante ou função limpa dentro de `src/prompts.py`, mantendo a lógica de chamada separada em `src/ai_studio_client.py`.

---

## 5. Compatibilidade Híbrida de Credenciais (Local vs. Colab)
Qualquer módulo em `src/` deve funcionar tanto no computador local (Antigravity) quanto no Google Colab sem precisar alterar o código. Use o seguinte padrão em `src/config.py` para recuperar a `GEMINI_API_KEY`:

```python
import os

def get_gemini_api_key() -> str:
    # 1. Tenta carregar dos Secrets do Google Colab, se estiver rodando na nuvem
    try:
        from google.colab import userdata
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
        raise ValueError("GEMINI_API_KEY não encontrada no .env local nem nos Secrets do Colab.")
    return key
```

---

## 6. Padrão de Cabeçalho para Notebooks no Google Colab
Quando solicitado a preparar o código para uso no Colab, oriente ou estruture a primeira célula do notebook (`notebooks/main_colab.ipynb`) com o bloco de montagem e *autoreload* abaixo. Isso garante que qualquer alteração salva pelo Antigravity nos arquivos `.py` reflita instantaneamente no Colab:

```python
# Célula 1 do Google Colab: Montar Drive e ativar Autoreload dos módulos .py
from google.colab import drive
import sys

drive.mount('/content/drive')

# Ajuste para o caminho exato da pasta do projeto no seu Drive
PROJECT_PATH = '/content/drive/MyDrive/ Caminho_Da_Sua_Pasta '
if PROJECT_PATH not in sys.path:
    sys.path.append(PROJECT_PATH)

%load_ext autoreload
%autoreload 2
```

---

## 7. Fluxo de Trabalho do Agente
1. **Compreensão:** Antes de alterar múltiplos arquivos, leia a estrutura atual em `src/` e verifique como os módulos estão sendo chamados no notebook do Colab.
2. **Modularização:** Se o usuário colar um código bruto do AI Studio ou uma célula longa do Colab, refatore-o em funções tipadas (Type Hints) e documentadas (Docstrings) dentro de `src/`.
3. **Verificação:** Garanta que novas bibliotecas adicionadas ao código em `src/` sejam registradas no arquivo `requirements.txt` para fácil instalação no Colab (`!pip install -r requirements.txt`).

---

## 8. Active Skills & MCP Registry

### 8.1. Plugins & Servidores MCP Locais
Configurados em `.antigravity/mcp_config.json` e espelhados em `.idx/mcp.json`:
- **`postgres`:** `@modelcontextprotocol/server-postgres` -> Conexão com o banco contábil via `DATABASE_URL`.
- **`github`:** `@modelcontextprotocol/server-github` -> Acesso seguro ao versionamento via `GITHUB_PERSONAL_ACCESS_TOKEN`.
- **`fetch`:** `@modelcontextprotocol/server-fetch` -> Inspeção direta de dados macro (`AwesomeAPI` e `BrasilAPI`).
- **`docker`:** `mcp/docker` -> Auditoria e telemetria de containers do `docker-compose.yml`.

### 8.2. Skills de Engenharia do Antigravity (`.agent/skills/`)
Habilidades de meta-engenharia ativadas no workspace:
1. `ui-design-system-enforcer` (`.agent/skills/ui-design-system-enforcer/SKILL.md`): Exige leitura obrigatória de `docs/design-system.md`, tipografia tabular `font-mono tabular-nums`, estética dark e destaque permanente do Kill Switch e Shadow Mode no `console_ui/`.
2. `mcp-ccxt-builder` (`.agent/skills/mcp-ccxt-builder/SKILL.md`): Padronização de ferramentas MCP em `gateway_vault/mcp_servers/` com validação determinística pelo `risk_guardrail`.
3. `colab-drive-modularizer` (`.agent/skills/colab-drive-modularizer/SKILL.md`): Converte código de notebooks `.ipynb` e prompts do AI Studio em módulos `.py` tipados, respeitando as restrições do Google Drive.

### 8.3. Skills Operacionais dos Agentes (`cognition_skills/skills/`)
Catálogo operacional baseado no padrão `agentskills.io` com Descoberta Progressiva (*Progressive Disclosure*), indexado em [`cognition_skills/skills/REGISTRY.json`](cognition_skills/skills/REGISTRY.json):
- `macro-brazil` (`cognition_skills/skills/macro_brazil/SKILL.md`): Cotações AwesomeAPI USD-BRL, validação bancária BrasilAPI e spread de stablecoin USDT/BRL.
- `mirofish-swarm-validator` (`cognition_skills/skills/mirofish_swarm_validator/SKILL.md`): Consenso Swarm e estresse em sandbox do Gêmeo Digital.
- `risk-mpc-guardrail` (`cognition_skills/skills/risk_mpc_guardrail/SKILL.md`): Travas determinísticas de drawdown, RTT e assinatura MPC 2-de-3.
- `tax-ledger-in1888` (`cognition_skills/skills/tax_ledger_in1888/SKILL.md`): Partidas dobradas, apuração de ganho de capital e regras da IN 1888.
- `posthog-telemetry` (`cognition_skills/skills/posthog_telemetry/SKILL.md`): Telemetria de decisões, PnL e feature flags no PostHog self-hosted.
