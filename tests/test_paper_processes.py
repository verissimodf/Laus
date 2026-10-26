import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from console_ui import server


class PaperProcesses(unittest.TestCase):
    def test_console_does_not_hide_worker_latch_after_external_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "kill.json"
            path.write_text('{"active":false}', encoding="utf-8")
            (path.parent / "worker.status.json").write_text(json.dumps({
                "timestamp": time.time(), "emergency_stop": True, "reason": "restart required"
            }), encoding="utf-8")
            with patch.object(server, "STATE_PATH", str(path)):
                self.assertTrue(server.get_system_state()["kill_switch"])

    def test_emergency_requires_auth_header_and_confirmation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "kill.json"
            with patch.object(server, "STATE_PATH", str(path)), patch.dict(os.environ, {
                "LAUS_CONSOLE_USERNAME": "test-user", "LAUS_CONSOLE_PASSWORD": "test-pass", "POSTHOG_ENABLED": "false"
            }):
                client = TestClient(server.app)
                body = {"confirmation": "HALT PAPER", "reason": "test operator"}
                self.assertEqual(client.post("/api/emergency", json=body).status_code, 401)
                self.assertEqual(client.post("/api/emergency", json=body, auth=("test-user", "test-pass")).status_code, 400)
                result = client.post("/api/emergency", json=body, auth=("test-user", "test-pass"),
                                     headers={"X-Laus-Action": "activate-emergency"})
                self.assertEqual(result.status_code, 200)
                self.assertTrue(json.loads(path.read_text())["active"])
                self.assertEqual(client.post("/api/reset", auth=("test-user", "test-pass")).status_code, 404)

    def test_worker_restart_and_console_process(self):
        import base64
        import urllib.error
        import urllib.request
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder)
            env = os.environ.copy()
            env.update({"LAUS_ENVIRONMENT": "shadow", "LAUS_STATE_DIR": str(state),
                        "LAUS_KILL_SWITCH_PATH": str(state / "kill.json"), "LAUS_LEDGER_PATH": str(state / "paper.db"),
                        "LAUS_CONSOLE_USERNAME": "smoke", "LAUS_CONSOLE_PASSWORD": "process-only",
                        "POSTHOG_ENABLED": "false"})
            for _ in range(2):
                completed = subprocess.run([sys.executable, "-m", "core_jarvis.worker", "--cycles", "1"],
                                           cwd=root, env=env, capture_output=True, timeout=45)
                self.assertEqual(completed.returncode, 0, completed.stderr.decode(errors="replace"))
                self.assertTrue((state / "worker.heartbeat").is_file())
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            process = subprocess.Popen([sys.executable, "-m", "uvicorn", "console_ui.server:app", "--host", "127.0.0.1",
                                        "--port", str(port)], cwd=root, env=env,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                url = f"http://127.0.0.1:{port}/"
                deadline = time.monotonic() + 30
                while True:
                    try:
                        urllib.request.urlopen(url, timeout=1)
                    except urllib.error.HTTPError as exc:
                        self.assertEqual(exc.code, 401)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            self.fail("Console process did not start")
                        time.sleep(0.1)
                auth = base64.b64encode(b"smoke:process-only").decode()
                with urllib.request.urlopen(urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})) as response:
                    body = response.read().decode()
                self.assertIn("HALTED", body)
                self.assertIn("SHADOW / PAPER TRADING", body)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
