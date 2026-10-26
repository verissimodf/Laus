# Operação local paper

Use Python 3.11 e ambiente isolado fora da pasta sincronizada. Instale
`pip install -r requirements.lock.txt`. As versões estão congeladas para repetição;
o lock não é uma certificação de ausência de vulnerabilidades.

## Configuração

Execute na raiz `python -m scripts.bootstrap_paper` uma única vez. O comando não
sobrescreve `.env`; gera senha aleatória sem imprimi-la. Leia a senha apenas no
arquivo local para entrar no console. Não publique `.env` nem seus backups.

Para uso continuado no Windows, aponte `LAUS_STATE_DIR`, `LAUS_LEDGER_PATH` e
`LAUS_KILL_SWITCH_PATH` para diretório local fora do OneDrive. Mantenha os três
serviços apontando aos mesmos arquivos. No Docker, os caminhos são substituídos
por `/state`, em volume nomeado.

Modo permitido do worker: `shadow`, `homologation` ou `shadow_paper_trading`.
`live` é recusado. Ausência/corrupção do kill switch mantém o sistema parado.

## Iniciar

Com Docker funcional:

```sh
docker compose -f docker-compose.paper.yml config --quiet
docker compose -f docker-compose.paper.yml up --build -d --wait
docker compose -f docker-compose.paper.yml ps
```

Console: `http://127.0.0.1:8090`, HTTP Basic. O painel mostra SHADOW/PAPER e
PARAR PAPER; a ação exige confirmação. Nunca expor Basic HTTP em rede pública.
MCP usa stdio: `docker compose -f docker-compose.paper.yml --profile tools run --rm -T mcp`.
Não há servidor MCP HTTP publicado nem executor de ordens.

Alternativa local demonstrável, em dois terminais com o mesmo ambiente:

```sh
python -m core_jarvis.worker
python -m uvicorn console_ui.server:app --host 127.0.0.1 --port 8090
```

Estado inicial fica parado. Após revisar configuração e limites, execute
`python -m core_jarvis.reset_kill_switch`, informe justificativa e a confirmação
literal solicitada. No Docker execute pelo serviço worker com `exec -it`.
Reinicie o worker após reset: seu latch em memória só é liberado por reset local
no mesmo processo ou por nova inicialização. O console lê o estado persistido.

## Comandos e verificações

```sh
python -m core_jarvis.text_gateway status
python -m core_jarvis.text_gateway summary
python -m core_jarvis.text_gateway reconcile
python -m core_jarvis.text_gateway halt
python -m resilience_edge.healthcheck
python -m unittest discover -s tests -p "test_*.py"
```

`summary` exibe PnL e volume paper do dia UTC. Volume não é posição nem exposição.
`reconcile` exige soma zero das partidas e cobertura de cada lançamento.
Heartbeat atesta atividade do worker, não disponibilidade de mercado. Monitorar
também rejeições, eventos de mercado indisponível e integridade do ledger.

## Backup, restauração e rollback

Para snapshot consistente de um SQLite ativo, inclusive WAL:

```sh
python -m scripts.paper_backup /caminho/paper.db /backup/paper-snapshot.db
python -m scripts.paper_backup /caminho/events.db /backup/events-snapshot.db
python -m scripts.paper_backup /caminho/episodes.db /backup/episodes-snapshot.db
```

Cada destino deve ser novo. O utilitário usa SQLite backup e `integrity_check`.
Para um snapshot coordenado de todos os bancos e do kill switch, pare o worker
e a console primeiro. Copie também o estado de emergência e registre o commit
da aplicação. Cofre e chave mestra exigem backups separados; perder a chave
torna o conteúdo do cofre irrecuperável.

Para restaurar, mantenha os serviços parados, preserve o conjunto atual como
rollback, restaure todos os arquivos do mesmo ponto de corte em diretório novo,
ative o kill switch e execute reconciliação antes de liberar. Não copie somente
o `.db` de um processo ativo nem descarte arquivos WAL em uso.

O comando `python -m scripts.validate_deployment` ensaia autenticação, parada,
reinício e snapshot coordenado dos três bancos, validando reconciliação da cópia
restaurada e o bind real da porta. Ele mantém a instalação em emergência ativa.
O comando `python -m scripts.validate_mcp` valida o protocolo stdio em container.
As evidências desta execução estão em `docs/validation-deployment.json` e
`docs/validation-mcp.json`. Os snapshots ficam no volume, em `/state/acceptance-*`;
isso comprova restauração lógica, mas não é backup externo contra perda do volume.

Para rollback de aplicação, use checkout da versão registrada e cópia do conjunto
de dados anterior à migração; não execute `git reset --hard` nem apague volumes.
Valide autenticação, estado bloqueado, integridade e reconciliação; só depois
submeta a retomada operacional ao responsável. O teste automatizado demonstra
snapshot/restauração SQLite e o ensaio Docker coordenado desta entrega comprova
a cópia lógica dos bancos. Recuperação em outro host e rollback entre versões
ainda exigem ensaio específico.

## Observação da release

O lote 4 começa somente após aceites de infraestrutura e consistência paper.
Durante 15–30 dias acordados, registrar commit, incidentes, saúde, rejeições,
PnL recalculado, reconciliação e restaurações ensaiadas. Incidente crítico,
divergência contábil ou dados sem frescor suspendem a observação e acionam parada.
Não há aprovação automática para capital real.
