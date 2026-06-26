"""Tests for the minimal Responses API compatibility layer."""

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import server.api as api
from server.api import _response_conversations, _responses_payload, _responses_prompt
from server.ratelimit import TokenBucket
from server.schemas import ResponsesRequest


class FakeClient:
    def __init__(self):
        self.last_prompt = None
        self.last_conversation_id = None

    def chat(self, prompt, conversation_id=None):
        self.last_prompt = prompt
        self.last_conversation_id = conversation_id
        return type("Reply", (), {"text": "OK", "conversation_id": conversation_id or "conv-test"})()

    def stream(self, prompt, conversation_id=None):
        self.last_prompt = prompt
        self.last_conversation_id = conversation_id
        return type(
            "Stream",
            (),
            {
                "conversation_id": conversation_id or "conv-test",
                "__iter__": lambda self: iter(["O", "K"]),
            },
        )()


def _sse_events(body: str):
    events = []
    for block in body.strip().split("\n\n"):
        event = None
        data = None
        for line in block.splitlines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = line.removeprefix("data: ")
        if data and data != "[DONE]":
            events.append((event, json.loads(data)))
        elif data == "[DONE]":
            events.append((None, "[DONE]"))
    return events


class ResponsesApiTests(unittest.TestCase):
    def test_string_input_becomes_prompt_with_instructions(self):
        req = ResponsesRequest(instructions="Be concise.", input="Say OK")

        self.assertEqual(_responses_prompt(req), "Be concise.\n\nSay OK")

    def test_message_input_becomes_prompt(self):
        req = ResponsesRequest(
            input=[
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": [{"type": "input_text", "text": "Say OK"}]},
            ]
        )

        self.assertEqual(_responses_prompt(req), "Be concise.\n\nSay OK")

    def test_non_streaming_response_maps_previous_response_id(self):
        original_client = api.client
        fake = FakeClient()
        try:
            api.client = fake
            client = TestClient(api.app)

            res = client.post("/v1/responses", json={"model": "copilot", "input": "Say OK"})
            body = res.json()
            res2 = client.post(
                "/v1/responses",
                json={"model": "copilot", "input": "Again", "previous_response_id": body["id"]},
            )
        finally:
            api.client = original_client

        self.assertEqual(res.status_code, 200)
        self.assertEqual(body["object"], "response")
        self.assertEqual(body["output_text"], "OK")
        self.assertEqual(_response_conversations[body["id"]], "conv-test")
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(fake.last_conversation_id, "conv-test")

    def test_responses_route_preserves_full_prompt_before_budgeting(self):
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

                res = client.post(
                    "/v1/responses",
                    json={
                        "model": "copilot",
                        "instructions": "System: keep rules",
                        "input": ("old detail\n" * 200) + "LATEST_REQUEST",
                    },
                )
            finally:
                api.client = original_client
                api.COPILOT_MAX_PROMPT_CHARS = original_budget
                api.COPILOT_CONTEXT_STORE_DIR = original_store

            saved = list(Path(td).glob("prompt-*.txt"))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(len(saved), 1)
            self.assertIn("old detail", saved[0].read_text(encoding="utf-8"))
            self.assertLessEqual(len(fake.last_prompt), 260)
            self.assertIn("System: keep rules", fake.last_prompt)
            self.assertIn("LATEST_REQUEST", fake.last_prompt)

    def test_streaming_response_sends_completed_and_done(self):
        original_client = api.client
        original_limiter = api._rate_limiter
        try:
            api.client = FakeClient()
            api._rate_limiter = TokenBucket(0, 1)
            client = TestClient(api.app)

            with client.stream(
                "POST",
                "/v1/responses",
                json={"model": "copilot", "input": "Say OK", "stream": True},
            ) as res:
                body = res.read().decode()
        finally:
            api.client = original_client
            api._rate_limiter = original_limiter

        self.assertEqual(res.status_code, 200)
        events = _sse_events(body)
        names = [name for name, _ in events]
        self.assertIn("response.created", names)
        self.assertIn("response.output_text.delta", names)
        self.assertIn("response.completed", names)
        self.assertEqual(events[-1], (None, "[DONE]"))
        self.assertEqual(events[-2][1]["response"]["output_text"], "OK")


if __name__ == "__main__":
    unittest.main()
