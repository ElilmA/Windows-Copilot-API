"""Tests for local prompt preservation before sending to Copilot."""

import tempfile
import unittest
from pathlib import Path

from server.context_manager import prepare_prompt_for_copilot


class ContextManagerTests(unittest.TestCase):
    def test_prepare_prompt_saves_full_input_and_sends_budgeted_text(self):
        with tempfile.TemporaryDirectory() as td:
            prompt = "System: keep rules\n\n" + ("old detail\n" * 200) + "\nUser: LATEST_REQUEST"

            selected = prepare_prompt_for_copilot(prompt, store_dir=td, budget=240)
            saved = list(Path(td).glob("prompt-*.txt"))

            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(encoding="utf-8"), prompt)
            self.assertLessEqual(len(selected), 240)
            self.assertIn("System: keep rules", selected)
            self.assertIn("LATEST_REQUEST", selected)


if __name__ == "__main__":
    unittest.main()

