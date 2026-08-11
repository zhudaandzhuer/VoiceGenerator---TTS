from __future__ import annotations

import os
import unittest
from pathlib import Path

import voice_studio_server as studio


class RuntimeMimoSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.old_runtime = dict(studio.RUNTIME_MIMO_SETTINGS)
        self.old_api_key = os.environ.pop("MIMO_API_KEY", None)
        self.old_base_url = os.environ.pop("MIMO_BASE_URL", None)
        studio.RUNTIME_MIMO_SETTINGS.update({"apiKey": "", "baseUrl": ""})

    def tearDown(self) -> None:
        studio.RUNTIME_MIMO_SETTINGS.clear()
        studio.RUNTIME_MIMO_SETTINGS.update(self.old_runtime)
        if self.old_api_key is not None:
            os.environ["MIMO_API_KEY"] = self.old_api_key
        else:
            os.environ.pop("MIMO_API_KEY", None)
        if self.old_base_url is not None:
            os.environ["MIMO_BASE_URL"] = self.old_base_url
        else:
            os.environ.pop("MIMO_BASE_URL", None)

    def test_runtime_key_is_used_without_writing_env_file(self) -> None:
        env_path = Path(studio.ROOT) / "scripts" / ".env"
        before = env_path.read_bytes() if env_path.exists() else None
        status = studio.configure_runtime_mimo({
            "apiKey": "test-secret-key",
            "baseUrl": "https://example.invalid/v1/",
        })
        self.assertTrue(status["configured"])
        self.assertEqual(status["source"], "runtime")
        self.assertNotIn("apiKey", status)
        self.assertNotIn("test-secret-key", repr(status))
        self.assertEqual(
            studio.api_key_and_base_url(),
            ("test-secret-key", "https://example.invalid/v1"),
        )
        after = env_path.read_bytes() if env_path.exists() else None
        self.assertEqual(before, after)

    def test_clear_removes_runtime_key(self) -> None:
        studio.configure_runtime_mimo({"apiKey": "temporary-key"})
        status = studio.configure_runtime_mimo({"clear": True})
        self.assertFalse(status["configured"])
        with self.assertRaisesRegex(RuntimeError, "API 設定"):
            studio.api_key_and_base_url()

    def test_invalid_base_url_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Base URL"):
            studio.configure_runtime_mimo({"apiKey": "x", "baseUrl": "file:///tmp/key"})

    def test_token_plan_key_defaults_to_sgp_endpoint(self) -> None:
        status = studio.configure_runtime_mimo({"apiKey": "tp-test-token", "baseUrl": studio.DEFAULT_BASE_URL})
        self.assertEqual(status["keyType"], "token-plan")
        self.assertEqual(status["baseUrl"], studio.TOKEN_PLAN_BASE_URLS["sgp"])
        self.assertEqual(studio.api_key_and_base_url()[1], studio.TOKEN_PLAN_BASE_URLS["sgp"])

    def test_key_and_endpoint_families_cannot_be_mixed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Token Plan"):
            studio.configure_runtime_mimo({"apiKey": "tp-test-token", "baseUrl": "https://example.com/v1"})
        with self.assertRaisesRegex(ValueError, "按量"):
            studio.configure_runtime_mimo({"apiKey": "sk-test-token", "baseUrl": studio.TOKEN_PLAN_BASE_URLS["sgp"]})


if __name__ == "__main__":
    unittest.main()
