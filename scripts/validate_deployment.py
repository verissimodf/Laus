"""Smoke, restart and coordinated SQLite restore checks against paper Compose."""
import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "docker-compose.paper.yml"]


def docker(*arguments):
    completed = subprocess.run(COMPOSE + list(arguments), cwd=ROOT, capture_output=True, timeout=180)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace")[-3000:])
    return completed.stdout.decode(errors="replace")


def main():
    credentials = dotenv_values(ROOT / ".env")
    auth = base64.b64encode((credentials["LAUS_CONSOLE_USERNAME"] + ":" + credentials["LAUS_CONSOLE_PASSWORD"]).encode()).decode()
    url = "http://127.0.0.1:8090"
    try:
        urllib.request.urlopen(url, timeout=10)
        raise AssertionError("Unauthenticated dashboard was accessible")
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    request = urllib.request.Request(url, headers={"Authorization": "Basic " + auth})
    with urllib.request.urlopen(request, timeout=10) as response:
        assert "SHADOW / PAPER TRADING" in response.read().decode()
    request = urllib.request.Request(url + "/api/emergency",
        data=json.dumps({"confirmation": "HALT PAPER", "reason": "Deployment validation: paper paused"}).encode(),
        headers={"Authorization": "Basic " + auth, "Content-Type": "application/json",
                 "X-Laus-Action": "activate-emergency"}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        assert json.load(response)["kill_switch"] is True

    docker("restart", "worker")
    docker("up", "-d", "--wait", "--wait-timeout", "90")
    docker("exec", "-T", "worker", "python", "-m", "resilience_edge.healthcheck")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = "/state/acceptance-" + stamp
    # Stop both database users for a coordinated snapshot, preserving named volumes.
    docker("stop", "worker", "console")
    try:
        code = '''import json, pathlib, shutil, sqlite3
from scripts.paper_backup import backup
from accounting_ledger.ledger_engine import AccountingLedger
destination=pathlib.Path(DESTINATION)
destination.mkdir()
for name in ('paper.db','events.db','episodes.db'):
    backup(pathlib.Path('/state')/name,destination/name)
shutil.copy2('/state/kill_switch.json',destination/'kill_switch.json')
original=AccountingLedger('/state/paper.db')
restored=AccountingLedger(str(destination/'paper.db'))
assert original.get_summary()==restored.get_summary()
assert restored.reconcile()['balanced']
assert json.loads((destination/'kill_switch.json').read_text())['active']
original.conn.close()
restored.conn.close()
print(json.dumps({'snapshot':str(destination),'restore_balanced':True,'emergency_halted':True}))
'''.replace("DESTINATION", repr(snapshot_path))
        restore = json.loads(docker("run", "--rm", "--no-deps", "worker", "python", "-c", code))
    finally:
        docker("up", "-d", "--wait", "--wait-timeout", "90")
    # Inspect actual port bindings, not just the YAML declaration.
    console_id = docker("ps", "-q", "console").strip()
    inspection = subprocess.check_output(["docker", "inspect", console_id], cwd=ROOT)
    config = json.loads(inspection)[0]
    bindings = config["NetworkSettings"]["Ports"]["8090/tcp"]
    assert bindings and all(b["HostIp"] == "127.0.0.1" for b in bindings)
    assert config["Config"]["User"] == "laus"
    service_output = docker("ps", "--format", "json")
    try:
        services = json.loads(service_output)
    except json.JSONDecodeError:
        services = [json.loads(line) for line in service_output.splitlines() if line.strip()]
    result = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "unauthenticated_status": 401, "authenticated_status": 200,
              "worker_restart_healthy": True, "restore": restore,
              "console_bindings": bindings, "image_id": config["Image"],
              "services": services,
              "mode": "paper", "emergency_halted": True,
              "live_execution_enabled": False, "remote_ci_verified": False,
              "supervised_acceptance": False}
    (ROOT / "docs" / "validation-deployment.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "services"}, indent=2))


if __name__ == "__main__":
    main()
