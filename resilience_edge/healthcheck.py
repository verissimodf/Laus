"""Exit nonzero if the paper worker heartbeat is missing or stale."""
import os
from pathlib import Path
import time


def healthy():
    try:
        heartbeat = Path(os.environ.get("LAUS_STATE_DIR", ".laus_state")) / "worker.heartbeat"
        age = time.time() - float(heartbeat.read_text(encoding="utf-8"))
        return 0 <= age < 60
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if healthy() else 1)
