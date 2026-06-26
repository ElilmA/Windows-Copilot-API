"""Route-level coverage for prompt preservation."""

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server.api as api


class FakeClient:
    def __init__(self):
        self.last_prompt = None

    def chat(self, prompt, conversation_id=None):
        self.last_prompt = prompt
        return type("Reply", (), {"text": "OK", "conversation_id": conversation_id})()

    def stream(self, prompt, conversation_id=None):
        self.last_prompt = prompt
        return iter(())


class ApiContextTests(unittest.TestCase):
    def test_chat_route_preserves_full_prompt_before_budgeting_upstream_text(self):
        original_client = api.client
        original_budget = api.COPILOT_MAX_PROMPT_CHARS
        original_store = api.COPILOT_CONTEXT_STORE_DIR
        fake = FakeClient()

        with tempfile.TemporaryDirectory() as td:
            try:
                api.client = fake
                api.COPILOT_MAX_PROMPT_CHARS = 260
                api.COPILOT_CONTEXT_STORE_DIR = td
                client = TestClient(api.app)

                response = client.post(
                    "/v1/chat/completions",
                    json={
                        "messages": [
                            {"role": "system", "content": "System: keep rules"},
                            {"role": "user", "content": ("old detail\n" * 200) + "LATEST_REQUEST"},
                        ]
                    },
                )
            finally:
                api.client = original_client
                api.COPILOT_MAX_PROMPT_CHARS = original_budget
                api.COPILOT_CONTEXT_STORE_DIR = original_store

            saved = list(Path(td).glob("prompt-*.txt"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(saved), 1)
            self.assertIn("old detail", saved[0].read_text(encoding="utf-8"))
            self.assertLessEqual(len(fake.last_prompt), 260)
            self.assertIn("System: keep rules", fake.last_prompt)
            self.assertIn("LATEST_REQUEST", fake.last_prompt)


if __name__ == "__main__":
    unittest.main()

