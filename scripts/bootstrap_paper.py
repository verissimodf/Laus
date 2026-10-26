"""Generate local-only credentials without printing them or enabling trading."""
from pathlib import Path
import secrets


def bootstrap(root):
    root = Path(root).resolve()
    env = root / ".env"
    if env.exists():
        raise FileExistsError("Existing .env preserved")
    state = root / ".laus_state"
    state.mkdir(exist_ok=True)
    env.write_text("\n".join([
        "LAUS_ENVIRONMENT=shadow", "POSTHOG_ENABLED=false",
        f"LAUS_PROJECT_ROOT='{root.as_posix()}'",
        "LAUS_STATE_DIR=.laus_state", "LAUS_KILL_SWITCH_PATH=.laus_state/kill_switch.json",
        "LAUS_LEDGER_PATH=.laus_state/paper.db", "LAUS_CONSOLE_USERNAME=operator",
        f"LAUS_CONSOLE_PASSWORD={secrets.token_urlsafe(32)}",
        "MAX_ORDER_USD=500", "MAX_SLIPPAGE_PCT=0.50",
        "MAX_DAILY_DRAWDOWN_USD=250", "MAX_DAILY_PAPER_NOTIONAL_USD=2500", "",
    ]), encoding="utf-8")
    try:
        env.chmod(0o600)
    except OSError:
        pass
    return env


if __name__ == "__main__":
    print(f"Created {bootstrap(Path(__file__).resolve().parents[1])}; paper remains halted until local review/reset.")
