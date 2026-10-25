import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(
    0,
    str(project_root / "cognition_skills" / "skills" / "posthog_telemetry" / "scripts"),
)
from emit_posthog_event import capture_laus_event


class TestPostHogTelemetry(unittest.TestCase):
    def test_capture_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "emit_posthog_event.urllib.request.urlopen"
        ) as urlopen:
            payload = capture_laus_event("laus_test", "test", {"status": "OK"})
        urlopen.assert_not_called()
        self.assertEqual(payload["event"], "laus_test")

    def test_opt_in_sends_project_token_and_only_allowed_properties(self):
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        with (
            patch.dict(
                os.environ,
                {
                    "POSTHOG_ENABLED": "true",
                    "POSTHOG_API_KEY": "phc-project-token",
                    "POSTHOG_HOST": "http://posthog.local:8000",
                },
                clear=True,
            ),
            patch("emit_posthog_event.urllib.request.urlopen", return_value=response) as urlopen,
        ):
            payload = capture_laus_event(
                "laus_test",
                "test-agent",
                {"symbol": "USDT-BRL", "status": "OK", "raw_prompt": "must not leave process"},
            )

        urlopen.assert_called_once()
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://posthog.local:8000/i/v0/e/")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["token"], "phc-project-token")
        self.assertEqual(sent["properties"]["symbol"], "USDT-BRL")
        self.assertNotIn("raw_prompt", sent["properties"])
        self.assertNotIn("token", payload)


if __name__ == "__main__":
    unittest.main()
