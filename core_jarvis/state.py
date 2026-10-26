"""Single location and fail-closed reader for the cross-process emergency latch."""
import json
import os
from pathlib import Path


def kill_switch_path():
    root = Path(os.environ.get("LAUS_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
    path = Path(os.environ.get("LAUS_KILL_SWITCH_PATH", ".laus_state/kill_switch.json"))
    return path if path.is_absolute() else root / path


def read_kill_switch(path):
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not isinstance(state.get("active"), bool):
            raise ValueError("Invalid emergency state")
        return state["active"], state.get("reason")
    except FileNotFoundError:
        return True, "KILL_SWITCH_NOT_INITIALIZED"
    except (OSError, ValueError):
        return True, "KILL_SWITCH_STATE_UNREADABLE"
