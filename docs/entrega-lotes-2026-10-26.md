# Execução dos lotes do relatório — Laus

Data: 26/10/2026. Baseline: `88cb9f12ffbdfb8afb1e5705e9c529aeab2488d1`.
Repositório: `verissimodf/Laus`, conforme o relatório anexado. A referência anterior
a AssistentePessoal não corresponde ao escopo nem ao código deste relatório.

## Estado da entrega

Esta entrega implementa uma base integrada **paper** e correções nos lotes 0–3,
com incrementos do lote 5. Não constitui homologação financeira, fiscal ou live.
O Compose paper é separado da infraestrutura-alvo antiga para não pressupor
que Redis, PostgreSQL, Qdrant e PostHog estejam integrados ao runtime existente.
Nenhum período de observação é contado por testes sintéticos.

| Lote | Implementação entregue | Aceite que ainda falta |
|---|---|---|
| 0 — Baseline | Checkout identificado, matriz abaixo, dependências congeladas, CI ampliada | CI remota verde no commit final; faturamento/limites pertencem ao administrador GitHub |
| 1 — Operação | Dockerfile não-root, Compose paper, worker e console saudáveis, MCP stdio validado, volume compartilhado, heartbeat, kill switch único; build/start/restart e snapshot coordenado demonstrados | Inspeção WAN/Tailscale e recuperação em outro host |
| 2 — Paper | Cotação propagada, custos líquidos sem duplicação, bid de venda, evidência do modelo, rejeições duráveis, idempotência e partidas balanceadas | Livro de posições e inventário por ativo com reservas e fills parciais; validação econômica do modelo USD/USDT |
| 3 — Homologação | Eventos SQLite duráveis, ack por consumidor, outbox atômica, replay determinístico, drawdown histórico, Sharpe explícito, backup/restauração SQLite | Redis/NATS distribuído, dados históricos certificados, walk-forward com otimização, caos de containers e rollback operacional do conjunto |
| 4 — Release | Critérios e roteiro de observação definidos abaixo | 15–30 dias supervisionados, aceite formal e tag de release com CI verde |
| 5 — Integral | Cofre AES-256-GCM local, runtime com permissões explícitas, memória SQLite de decisões e comandos de texto | Voz/STT/TTS, GraphRAG/Qdrant, administração completa, assinatura MPC/TSS, execução real e revisão fiscal especializada |

## Matriz de requisitos e evidências

Responsável técnico proposto: mantenedor de engenharia. Aceite operacional:
operador do host. Aceites fiscal e criptográfico requerem especialistas designados
pelo responsável do projeto; não há nomes ou aprovações presumidos.

| ID | Requisito obrigatório / critério de aceite | Evidência atual | Estado |
|---|---|---|---|
| P1.1 | Evento sobrevive a reinício; consumidor só confirma após sucesso | `core_jarvis/durable_bus.py`, teste de falha após commit e antes do ack | Implementado localmente, at-least-once |
| P1.2 | Emergência persistente comum, ausência/corrupção bloqueiam | `core_jarvis/state.py`, `orchestrator.py`, console, testes de concordância | Implementado |
| P1.3 | Gateway de texto com permissões e histórico | `core_jarvis/text_gateway.py`, `cognition_skills/runtime.py` | Implementado localmente |
| P1.4 | Gateway de voz e cancelamento/barge-in testados | Sem implementação | Pendente |
| P2.1 | Detector → proposta → ledger usa mesma cotação e spread | `fiat_ask`, custos e `paper_execution`, teste de callback | Implementado para estimativa de round-trip |
| P2.2 | Valor observado de venda usa bids | `fetch_crypto_book_depth_async` | Implementado |
| P2.3 | Inventário, reservas e fills parciais reconciliados com capital | Modelo atual registra round-trip fechado hipotético | Pendente |
| P2.4 | Freqtrade integrado ao mesmo livro de posições | Freqtrade permanece dry-run independente, API desativada | Pendente |
| P3.1 | Limites por ordem e limites diários concorrentes | Guardrail e transação SQLite, suíte anterior preservada | Implementado paper |
| P3.2 | Credenciais cifradas e adulteração detectável | `credential_vault.py`, AES-256-GCM, teste chave errada/adulteração | Componente entregue; integração com provedores pendente |
| P3.3 | Assinatura distribuída e execução isolada | Não implementadas; MCP só lê, simula e valida por ordem | Pendente e live bloqueado |
| P4.1 | Console autenticado e dados escapados | Testes HTTP Basic/XSS, métricas indisponíveis sinalizadas | Implementado |
| P4.2 | Parada explícita, autenticada, persistida, sem reset remoto | `/api/emergency`, cabeçalho customizado e confirmação; botão no painel | Implementado paper |
| P4.3 | Telemetria, custos e feature flags integrados | PostHog opt-in e evento de emergência; sem serviço PostHog validado | Parcial |
| P5.1 | Markdown não concede execução; permissões negadas por padrão | `SkillRuntime.register/invoke`, testes de negação | Implementado no novo runtime; catálogo legado não convertido |
| P5.2 | Decisões consultáveis após reinício | `paper_decisions`, `episodes.db`, integração no worker | Implementado SQLite; sem GraphRAG |
| P6.1 | Serviços executáveis com persistência e saúde | `docker-compose.paper.yml`, Dockerfile, heartbeat, `validation-deployment.json` | Build e serviços saudáveis demonstrados no host |
| P6.2 | Portas administrativas sem bind WAN | Bind real da console inspecionado em `127.0.0.1:8090`; MCP por stdio validado | Bind dos containers comprovado; firewall/host/Tailscale pendentes |
| P6.3 | Recuperação sem duplicar lançamentos | Ack, proposal_id único, outbox, backup SQLite | Testado em processo e banco; caos Docker pendente |
| P7.1 | Máximo drawdown da trajetória e Sharpe com unidade explícita | `performance_metrics`, testes de perda/recuperação | Implementado; Sharpe por operação, não anualizado |
| P7.2 | Replay reproduzível e janelas cronológicas sem futuro no passado | `replay(seed)`, `walk_forward` | Validador de estratégia fixa; sem otimizador nem dataset histórico |
| P7.3 | Produção exige todas as evidências de homologação | `eligible_for_production=False` incondicional | Promoção bloqueada |
| P8.1 | Lançamentos atômicos com débito = crédito | `paper_postings`, valores inteiros em microUSD; perdas também balanceiam | Implementado para PnL paper, sem inventário patrimonial |
| P8.2 | Reconciliação identifica legado sem partidas | `AccountingLedger.reconcile` | Implementado; não cria histórico fictício |
| P8.3 | Regras fiscais vigentes e exportação oficial | Provisão legada de 15% continua apenas ilustrativa, rotulada na UI | Pendente de revisão especializada e atualização normativa |

## Alterações críticas

- Arquivo antigo `console_ui/specs/global_state.json` deixou de controlar o console.
  Estado único: `LAUS_KILL_SWITCH_PATH`, relativo a `LAUS_PROJECT_ROOT` ou absoluto.
  Estado ausente fica bloqueado até revisão e reset local explícito.
- O callback usa `proposal.fiat_ask` e `net_spread_bps`; o ledger não desconta a taxa
  legada novamente. Quando o detector fornece spread bruto, os custos totais são
  discriminados no lançamento. Overrides explícitos continuam disponíveis para
  cenários offline pelo método Python; não são expostos no worker nem no MCP.
- `paper_execution` é uma estimativa econômica do round-trip, não um fill de
  corretora. USD e USDT seguem a hipótese de paridade do modelo legado. Slippage
  e custos do detector ainda precisam de calibração com uma rota econômica real.
- A outbox é gravada junto com o lançamento. A entrega é pelo menos uma vez;
  consumidores devem deduplicar pelo lançamento/proposta. O worker descarta
  propostas recuperadas com mais de dez segundos e audita a rejeição.
- SQLite é backend local deliberado desta entrega. Não se anuncia Redis Streams,
  PostgreSQL contábil, rede privada verificada nem memória vetorial como prontos.
- Os novos lançamentos preservam o banco legado; reconciliação acusa entradas
  antigas sem partidas. Não há backfill financeiro sem revisão das evidências.

## Verificação e limitações do ambiente

Comandos reproduzíveis e procedimentos estão em `operacao-paper.md`.
Console implantada: `http://127.0.0.1:8090`. Usuário `operator`; senha aleatória
armazenada somente no `.env` local ignorado pelo Git. Worker permanece em paper
com emergência ativa. Volumes e containers foram preservados para inspeção.
O ambiente Python foi instalado fora do OneDrive. Não foi criado `.venv` local.
Na primeira execução faltavam FastAPI e python-dotenv. Após instalação e correções,
a suíte final passou com 82 testes no Windows. O resultado reexecutável fica em
`validation-paper.json`; a suíte também foi executada na imagem Linux.

O Docker inicialmente parecia indisponível dentro do sandbox. A inicialização
fora dele funcionou e o daemon respondeu com versão `29.9.1`. A imagem foi
construída, worker e console ficaram saudáveis, e foram demonstrados autenticação,
restart e snapshot/restauração coordenados com reconciliação balanceada.
`validation-deployment.json` registra bind real, imagem e resultado do ensaio.
`validation-mcp.json` registra o handshake/listagem de quatro ferramentas e uma
validação de proposta pelo MCP stdio containerizado, sem envio de ordens.
O servidor MCP `codebase-memory` não está exposto nesta sessão. Nenhum plugin
adicional foi instalado sem uma necessidade concreta identificada.

## Critérios para avançar

1. Executar CI no commit final e resolver eventuais restrições administrativas.
2. Preservar os ensaios Docker já demonstrados e completar recuperação em outro
   host, inspeção da rede privada e rollback entre versões da aplicação.
3. Completar inventário/posições e validar com cenários de falta de capital,
   falta de liquidez, fills parciais e custos de cada perna.
4. Rodar replay com dados históricos identificados e validar a base temporal do
   Sharpe; não comparar Sharpe por operação a Sharpe anualizado.
5. Iniciar observação supervisionada de 15–30 dias com incidentes e evidências
   diárias, reconciliação sem divergência e critérios de parada explícitos.
6. Só emitir tag de release paper após aceite formal. Escopo live/fiscal/voz é
   condicionado aos requisitos pendentes acima e não decorre dessa tag.
