"""Builders for the OpenAI wire shapes (completions, SSE chunks)."""

import json
import time
import uuid


def new_id() -> str:
    """A fresh ``chatcmpl-...`` id, as the OpenAI API returns."""
    return f"chatcmpl-{uuid.uuid4().hex}"


def new_response_id() -> str:
    """A fresh ``resp_...`` id for Responses API compatibility."""
    return f"resp_{uuid.uuid4().hex}"


def completion_response(text: str, model: str, conversation_id=None) -> dict:
    """A non-streaming ``chat.completion`` object.

    ``conversation_id`` is Copilot's own conversation id, surfaced as an extra
    top-level field (not part of OpenAI's schema, so standard clients ignore it)
    for callers that want to track the upstream thread.
    """
    return {
        "id": new_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "conversation_id": conversation_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def response_response(text: str, model: str, conversation_id=None) -> dict:
    """A minimal non-streaming ``response`` object."""
    return {
        "id": new_response_id(),
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": model,
        "conversation_id": conversation_id,
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
        "output_text": text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    }


def sse_event(payload: dict) -> str:
    """Serialize a payload as a Server-Sent Events ``data:`` line."""
    return f"data: {json.dumps(payload)}\n\n"


def named_sse_event(event: str, payload: dict) -> str:
    """Serialize a named Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def stream_chunk(
    cid: str, created: int, model: str, delta: dict, finish=None, conversation_id=None
) -> dict:
    """A single ``chat.completion.chunk`` object for streaming responses.

    ``conversation_id`` (Copilot's upstream id) is added as an extra top-level
    field when known — typically only on the final chunk, since a new
    conversation's id isn't available until the stream has started.
    """
    chunk = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }
    if conversation_id is not None:
        chunk["conversation_id"] = conversation_id
    return chunk
