"""Run repeatable checks and write a small evidence manifest without secrets."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone


def main():
    root = Path(__file__).resolve().parents[1]
    tests = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                           cwd=root, capture_output=True, timeout=180)
    output = tests.stderr.decode("utf-8", errors="replace")
    print(output[-6000:])
    match = re.search(r"Ran (\d+) tests in ([\d.]+)s", output)
    env = os.environ.copy()
    env.update({"LAUS_CONSOLE_USERNAME": "validation-only", "LAUS_CONSOLE_PASSWORD": "validation-only-not-a-secret"})
    compose = subprocess.run(["docker", "compose", "-f", "docker-compose.paper.yml", "config", "--quiet"],
                             cwd=root, env=env, capture_output=True, timeout=30)
    docker = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                            cwd=root, capture_output=True, timeout=30)
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root).decode().splitlines()
    hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files
              if (root / name).is_file() and not name.startswith("docs/validation-")}
    deployment_path = root / "docs" / "validation-deployment.json"
    deployment = json.loads(deployment_path.read_text(encoding="utf-8")) if deployment_path.exists() else {}
    evidence = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "baseline_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip(),
                "tests": {"exit_code": tests.returncode, "count": int(match[1]) if match else None,
                          "seconds": float(match[2]) if match else None},
                "compose_config_exit_code": compose.returncode,
                "compose_config_error": compose.stderr.decode(errors="replace") if compose.returncode else None,
                "docker_daemon_available": docker.returncode == 0,
                "container_deployment_verified": bool(deployment.get("worker_restart_healthy") and docker.returncode == 0),
                "deployment_evidence": "docs/validation-deployment.json" if deployment else None,
                "remote_ci_verified": False, "supervised_acceptance": False,
                "source_sha256": hashes}
    (root / "docs" / "validation-paper.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "source_sha256"}, indent=2))
    return 0 if tests.returncode == 0 and compose.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
