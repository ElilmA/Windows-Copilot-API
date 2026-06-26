"""Tests for Copilot auth cache validation."""

import json
import tempfile
import time
import unittest
from base64 import urlsafe_b64encode
from pathlib import Path
from unittest.mock import patch

from copilot.auth import _looks_like_chat_token, load_auth


def _b64_json(data):
    return urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


def _compact_token(header, segments):
    return ".".join([_b64_json(header), *segments])


class AuthTests(unittest.TestCase):
    def test_load_auth_rejects_encrypted_token_cache(self):
        encrypted_like = "a.b.c.d.e"
        with tempfile.TemporaryDirectory() as td:
            auth_path = Path(td) / "token.json"
            auth_path.write_text(
                json.dumps({"cookies": {}, "access_token": encrypted_like, "saved_at": 9999999999}),
                encoding="utf-8",
            )

            with patch("copilot.browser.BrowserCopilot") as browser:
                bot = browser.return_value
                bot.acquire_chat_token.return_value = None
                bot.region_blocked.return_value = False
                bot.close.return_value = None

                with self.assertRaises(RuntimeError):
                    load_auth(path=str(auth_path), profile_dir=str(Path(td) / "profile"), auto_login=False)

    def test_chat_token_shape_accepts_jws_and_jwe(self):
        jws = _compact_token({"alg": "RS256", "typ": "JWT"}, ["payload", "sig"])
        jwe = _compact_token({"alg": "dir", "enc": "A256GCM"}, ["ek", "iv", "cipher", "tag"])

        self.assertTrue(_looks_like_chat_token(jws))
        self.assertTrue(_looks_like_chat_token(jwe))
        self.assertFalse(_looks_like_chat_token("a.b.c.d.e"))
        self.assertFalse(_looks_like_chat_token("opaque-access-token"))

    def test_load_auth_accepts_fresh_chat_jwe_cache(self):
        chat_jwe = _compact_token({"alg": "dir", "enc": "A256GCM"}, ["ek", "iv", "cipher", "tag"])
        with tempfile.TemporaryDirectory() as td:
            auth_path = Path(td) / "token.json"
            auth_path.write_text(
                json.dumps({"cookies": {"MS0": "cookie"}, "access_token": chat_jwe, "saved_at": time.time()}),
                encoding="utf-8",
            )

            with patch("copilot.browser.BrowserCopilot") as browser:
                auth = load_auth(path=str(auth_path), profile_dir=str(Path(td) / "profile"), auto_login=False)

            browser.assert_not_called()
            self.assertEqual(auth["access_token"], chat_jwe)


if __name__ == "__main__":
    unittest.main()
