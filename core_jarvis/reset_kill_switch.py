"""Local, interactive reset path for the persisted Laus kill switch.

Run from the repository root with:
    python -m core_jarvis.reset_kill_switch
"""
from pathlib import Path

from dotenv import load_dotenv

from core_jarvis.orchestrator import JarvisOrchestrator


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)

    orchestrator = JarvisOrchestrator()
    if not orchestrator.emergency_stop:
        print("Kill switch já está inativo; nenhuma alteração foi feita.")
        return 0

    print(f"Kill switch ativo. Motivo: {orchestrator.emergency_stop_reason}")
    try:
        reason = input("Motivo da revisão operacional: ")
        confirmation = input("Digite exatamente RESET KILL SWITCH para liberar: ")
    except EOFError:
        print("Entrada encerrada; kill switch permanece ativo.")
        return 2

    try:
        reset = orchestrator.reset_kill_switch(confirmation, reason)
    except ValueError as exc:
        print(f"Reset cancelado: {exc}")
        return 2
    except OSError as exc:
        print(f"Não foi possível persistir o reset; kill switch permanece ativo: {exc}")
        return 1

    if reset:
        print("Kill switch resetado. A justificativa foi gravada no estado local.")
    else:
        print("Kill switch já está inativo; nenhuma alteração foi feita.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
