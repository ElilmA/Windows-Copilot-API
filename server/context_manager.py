"""Preserve full prompts locally while sending Copilot a bounded prompt."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path


OMITTED_MARKER = "\n\n[... omitted from upstream prompt; full input saved locally ...]\n\n"


def save_full_prompt(prompt: str, store_dir: str) -> str:
    """Persist the exact prompt and return the file path."""
    root = Path(store_dir)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = root / f"prompt-{stamp}-{uuid.uuid4().hex}.txt"
    path.write_text(prompt, encoding="utf-8")
    return str(path)


def prepare_prompt_for_copilot(prompt: str, *, store_dir: str, budget: int) -> str:
    """Save the complete prompt, then return text sized for Copilot."""
    save_full_prompt(prompt, store_dir)
    if budget <= 0 or len(prompt) <= budget:
        return prompt
    if len(OMITTED_MARKER) >= budget:
        return prompt[-budget:]
    head_budget = max(1, min(budget // 4, budget - len(OMITTED_MARKER) - 1))
    tail_budget = max(1, budget - head_budget - len(OMITTED_MARKER))
    return prompt[:head_budget] + OMITTED_MARKER + prompt[-tail_budget:]
