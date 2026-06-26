"""Server configuration — shared constants."""

import os

# The single model id this bridge advertises (Copilot has no model selector).
MODEL_NAME = "copilot"

# Self-imposed rate limit (Copilot publishes none). Tune to whatever ceiling the
# probe in tests/ratelimit.py shows your account tolerates.
#   RATE_LIMIT_RPM   requests/minute the bridge will accept; 0 disables limiting.
#   RATE_LIMIT_BURST max requests allowed back-to-back before pacing kicks in.
# Default 12 rpm sits safely below the ~15 rpm where one account starts seeing
# upstream 502s, so the limiter only bites when callers try to exceed that.
RATE_LIMIT_RPM = float(os.environ.get("RATE_LIMIT_RPM", "12"))  # 12 rpm ≈ 5s per call
RATE_LIMIT_BURST = int(os.environ.get("RATE_LIMIT_BURST", "4"))

# Copilot can reject very large single-message prompts. Keep the full text on
# disk, but send only a bounded prompt upstream. Set to 0 to send the full text.
COPILOT_MAX_PROMPT_CHARS = int(os.environ.get("COPILOT_MAX_PROMPT_CHARS", "6000"))
COPILOT_CONTEXT_STORE_DIR = os.environ.get("COPILOT_CONTEXT_STORE_DIR", ".context-store")
