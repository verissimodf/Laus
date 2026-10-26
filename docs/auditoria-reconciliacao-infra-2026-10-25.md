# Auditoria de reconciliação — Laus
Data: 2026-10-25
Base auditada: `main` em `c358b60e9c892ada73c0d8eceef4fe40b635108c`
Relatório confrontado: arquivo de relatório operacional fornecido nesta análise.

## Veredicto
**RECONCILIAÇÃO NÃO COMPROVADA NO REPOSITÓRIO PÚBLICO.**

A branch main publicada não contém a configuração de infraestrutura descrita no relatório operacional. Isso prova divergência de versionamento/documentação, mas não prova por si só que o host de produção esteja incorreto. As afirmações de estado real do host (nginx ativo, portas escutando, systemd active, healthchecks e respostas HTTP) não podem ser verificadas apenas pelo repositório público.

## Achados

### P0 — INC-01: Compose diverge de produção descrita
Arquivo: [docker-compose.yml](https://github.com/verissimodf/Laus/blob/main/docker-compose.yml)
SHA: `69c5a2c713ee5966e262ed8760acca7c2b1b989d`

A main usa Redis 127.0.0.1:6379, Qdrant 6333/6334, PostgreSQL 5432, Freqtrade 8080 e PostHog 8000. Não define os serviços `laus_auth` e `laus_console` relatados. O Compose não publica explicitamente a console FastAPI do código. A configuração Redis não exige `REDIS_PASSWORD` e a configuração Qdrant não declara uma API key. O PostHog ocupa a porta publicada 8000, diferente do esquema descrito no relatório.

**Ação:** alinhar os manifestos versionados ao desenho operacional aprovado: serviços, portas loopback, autenticação, credenciais, healthchecks, dependências e volumes. Não ajustar apenas os números; representar todos os serviços necessários ou declarar claramente serviços externos ao Compose.

### P0 — INC-02: artefatos operacionais relatados ausentes nos caminhos consultados
O relatório cita:
- `scripts/tailnet_relay.mjs`
- `deploy/systemd/laus-tailnet-relay.service`
- `docs/INFRAESTRUTURA.md`

Esses três caminhos retornaram 404 na `main` pública. Podem existir apenas no host ou em uma árvore local não publicada.

**Ação:** versionar script do relé, unit systemd, procedimento de instalação/rollback, documentação e testes fail-closed; declarar dependências e validar explicitamente que o listener só se vincula ao IP da tailnet.

### P1 — INC-03: contrato de ambiente incompatível
Arquivo: [.env.example](https://github.com/verissimodf/Laus/blob/main/.env.example)
SHA: `e37acca90dfb66467190188fbcafe7f2f609977d`

O exemplo declara `REDIS_URL`, `QDRANT_HOST`, `QDRANT_PORT`, credenciais da console e `POSTGRES_PASSWORD`, mas não apresenta o conjunto de variáveis citado no relatório para autenticação Redis/Qdrant e configuração Freqtrade. O Compose público exige `POSTGRES_PASSWORD`, mas não exige senha Redis nem API key Qdrant.

**Ação:** consolidar contrato de variáveis por serviço; validar obrigatoriedade no boot; não colocar segredos reais no repositório. Se PAT/Gemini/Basic password foram expostos em texto claro, revogar/rotacionar — apagar o texto não invalida credenciais já expostas.

### P1 — INC-04: documentação confunde arquitetura-alvo e implementação
Arquivos: [README.md](https://github.com/verissimodf/Laus/blob/main/README.md), [ARCHITECTURE.md](https://github.com/verissimodf/Laus/blob/main/ARCHITECTURE.md).

O README tem ressalva explícita de que o projeto é experimental/paper, sem envio de ordens e sem ledger de partidas dobradas nem conformidade fiscal real. Entretanto, outras seções descrevem TSS/MPC, execução de exchange, cofre de chaves, GraphRAG, frontend Next.js/React e funcionalidades de console como parte da plataforma. Isso pode induzir decisão equivocada.

**Ação:** criar matriz de capacidade por pilar: IMPLEMENTADO, PARCIAL, PLANEJADO, NÃO VALIDADO; separar arquitetura-alvo dos controles e funcionalidades testados. Atualizar diagrama e roteiro para refletir o código real.

### P1 — INC-05: console real diverge do produto descrito
Arquivo: [console_ui/server.py](https://github.com/verissimodf/Laus/blob/main/console_ui/server.py)
SHA: `1e7d4aa121e47ab35c7400d15caafe0d902f1357`

A console é uma página HTML/FastAPI de leitura de métricas paper do SQLite e do estado do kill switch. Não é um frontend Next.js/React, não fornece o cofre de chaves descrito nem ação de liquidação financeira. O backend MCP [official_server.py](https://github.com/verissimodf/Laus/blob/main/gateway_vault/mcp_servers/official_server.py) limita-se a leitura, simulação e validação restrita; declara não oferecer submissão de ordens nem liquidação.

**Ação:** manter o painel classificado como monitoramento até implementar e testar recursos administrativos; não tratar como interface de execução ou custódia.

### P0 — INC-06: verificações de segurança externas não são comprováveis via código publicado
O relatório afirma que hostname público responde 403, a tailnet retorna 200/401 conforme autenticação, os listeners estão nas interfaces certas, nginx foi reiniciado para reabrir bind mount e o relé é systemd active. Essas são afirmações sobre o host e a rede em execução. O repositório, isoladamente, não as comprova; os scripts/unit necessários não foram encontrados nos caminhos mencionados.

**Ação:** anexar evidência reproduzível com timestamp, commit/image SHA, configuração nginx efetiva, `docker compose config`, portas/listeners, estado systemd, resultados dos probes externo/host/tailnet e teste com Tailscale desligado.

### P1 — INC-07: integração dos commits locais não comprovada
O relatório afirma commit local `808f2c9` e árvore três commits à frente sem push. A branch pública consultada está em `c358b60e9c892ada73c0d8eceef4fe40b635108c`, merge PR #29, e o workflow de testes associado concluiu com sucesso. A main pública não demonstra os ajustes operacionais mencionados no relatório.

**Ação:** inspecionar no host o SHA e a árvore local exatos; comparar com origin/main; publicar via PR após revisão. Não considerar os ajustes publicados enquanto os caminhos e conteúdo não aparecerem no commit remoto.

## Pontos positivos verificados no código público
- [tests/test_console_security.py](https://github.com/verissimodf/Laus/blob/main/tests/test_console_security.py) cobre Basic Auth obrigatório, credenciais ausentes (fail-closed) e escape de conteúdo HTML.
- [GitHub Actions](https://github.com/verissimodf/Laus/actions/runs/40236763728) concluiu com sucesso o workflow Python Tests no commit `c358b60e9c892ada73c0d8eceef4fe40b635108c`.
- `official_server.py` declara explicitamente ausência de submissão de ordens e liquidação; esse limite reduz ambiguidade no gateway MCP.
- `README.md` ressalva que ledger e PnL são estimativas paper, não contabilidade estatutária.

## Plano de correção recomendado
1. **P0 — Baseline de produção:** obter do host os SHA local/remoto, `docker compose config`, `docker ps`, listeners, unit systemd e nginx efetivo; reconciliar contra arquivos versionados.
2. **P0 — Segredos:** revogar/rotacionar credenciais que tenham sido expostas (PAT, Gemini, Basic, Redis/Qdrant); garantir que `.env` não é rastreado nem incluído nos logs/artefatos.
3. **P0 — Acesso remoto:** versionar relé e unit; provar fail-closed, loopback binding e ausência de rota pública da console.
4. **P1 — Configuração reproduzível:** atualizar Compose e `.env.example` como uma mudança coerente, adicionando healthchecks e versões de imagens fixadas/digest aprovados.
5. **P1 — Documentação:** revisar README/ARCHITECTURE e adicionar `docs/INFRAESTRUTURA.md` com matriz de estado real, portas, auth, rollback, validação e recuperação do bind mount.
6. **P1 — CI de infraestrutura:** adicionar validação de Compose e testes/contratos para garantir que serviços, portas e env vars esperados continuem alinhados.
7. **Gate de release:** PR com teste verde e revisão; depois deploy controlado e probes de host/tailnet/WAN. Não concluir deploy PASS apenas com testes unitários.

## Limites desta auditoria
Não se executou comando no host de produção, não se verificou o `.env` real e não se editou nem publicou alteração em `main`. Os findings distinguem divergência da branch pública de fatos que só o host pode confirmar.
