"""FastAPI app wiring Copilot onto the OpenAI Chat Completions API."""

import threading
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from copilot import CopilotClient
from copilot.driver import ClearanceRequired

from .config import (
    COPILOT_CONTEXT_STORE_DIR,
    COPILOT_MAX_PROMPT_CHARS,
    MODEL_NAME,
    RATE_LIMIT_BURST,
    RATE_LIMIT_RPM,
)
from .context_manager import prepare_prompt_for_copilot
from .openai_format import (
    completion_response,
    named_sse_event,
    new_id,
    new_response_id,
    response_response,
    sse_event,
    stream_chunk,
)
from .prompt import content_text, messages_to_prompt
from .ratelimit import TokenBucket
from .schemas import ChatCompletionRequest, ChatMessage, ResponsesRequest

app = FastAPI(title="Copilot OpenAI-compatible API", version="1.0.0")
# Server runs headless and must never pop a visible browser mid-request. With
# both recovery passes disabled, an expired clearance surfaces immediately as a
# 503 (see ClearanceRequired handling below) so an operator can re-clear out of
# band (`python -m copilot login`). Headless auto-solve is intentionally off:
# it's unreliable on low-trust egress and a failed pass can wedge the session.
client = CopilotClient(interactive_clear=False, headless_clear=False)

_CLEARANCE_HELP = (
    "Cloudflare clearance expired and could not be refreshed headlessly. "
    "Re-clear in a browser: run `python -m copilot login` (or `python tests/diagnostic.py`) "
    "and pass the 'verify you're human' check, then retry."
)

# Self-imposed rate limit on top of the concurrency lock below: this caps
# requests-per-minute, the lock caps requests-in-flight. See server/ratelimit.py.
_rate_limiter = TokenBucket(RATE_LIMIT_RPM, RATE_LIMIT_BURST)


def _rate_limited_response():
    """Spend a token; return an OpenAI-shaped 429 if none left, else ``None``."""
    allowed, wait = _rate_limiter.try_acquire()
    if allowed:
        return None
    secs = max(1, round(wait))
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(secs)},
        content={"error": {
            "message": (
                f"Rate limit exceeded (>{RATE_LIMIT_RPM:g} req/min). "
                f"Retry in {secs}s."
            ),
            "type": "rate_limit_error",
            "code": "rate_limit_exceeded",
        }},
    )

# Copilot's per-account chat socket doesn't tolerate concurrent conversations
# from one process (parallel requests error out or hang). This server bridges a
# single signed-in account, so we serialize upstream calls: concurrent HTTP
# requests queue here and run one at a time. Predictable, at the cost of
# parallelism — fine for a personal bridge.
_upstream_lock = threading.Lock()
_response_conversations = {}


def _responses_prompt(req: ResponsesRequest) -> str:
    parts = []
    if req.instructions:
        parts.append(req.instructions)

    if isinstance(req.input, str):
        parts.append(req.input)
    else:
        messages = []
        for item in req.input:
            if isinstance(item, dict) and "role" in item:
                content = item.get("content")
                if isinstance(content, list):
                    content = [
                        {"type": "text", "text": part.get("text", "")}
                        if isinstance(part, dict) and part.get("type") in {"input_text", "output_text"}
                        else part
                        for part in content
                    ]
                messages.append(ChatMessage(role=item.get("role", "user"), content=content))
            elif isinstance(item, dict):
                parts.append(content_text([item]))
            else:
                parts.append(str(item))
        if messages:
            parts.append(messages_to_prompt(messages))

    return "\n\n".join(part for part in parts if part)


def _responses_payload(text: str, model: str, conversation_id=None) -> dict:
    payload = response_response(text, model, conversation_id)
    if conversation_id is not None:
        _response_conversations[payload["id"]] = conversation_id
    return payload


def _stream(prompt: str, model: str, conversation_id=None):
    """Yield OpenAI ``chat.completion.chunk`` SSE events for ``prompt``.

    ``conversation_id`` continues an existing Copilot thread; ``None`` starts a
    fresh one (its id is emitted on the final chunk).
    """
    cid = new_id()
    created = int(time.time())
    try:
        with _upstream_lock:  # one upstream chat at a time (released on disconnect)
            yield sse_event(stream_chunk(cid, created, model, {"role": "assistant"}))
            stream = client.stream(prompt, conversation_id=conversation_id)
            for piece in stream:
                if isinstance(piece, str) and piece:
                    yield sse_event(stream_chunk(cid, created, model, {"content": piece}))
            # Copilot's conversation id is known once the stream has run; emit it
            # on the final chunk so callers can track the upstream thread.
            yield sse_event(
                stream_chunk(
                    cid, created, model, {}, finish="stop",
                    conversation_id=stream.conversation_id,
                )
            )
    except ClearanceRequired:
        yield sse_event(
            stream_chunk(cid, created, model, {"content": f"\n[error: {_CLEARANCE_HELP}]"}, finish="error")
        )
    except Exception as exc:  # surface errors to the client instead of hanging
        yield sse_event(
            stream_chunk(cid, created, model, {"content": f"\n[error: {exc}]"}, finish="error")
        )
    yield "data: [DONE]\n\n"


def _prepare_prompt(prompt: str) -> str:
    return prepare_prompt_for_copilot(
        prompt,
        store_dir=COPILOT_CONTEXT_STORE_DIR,
        budget=COPILOT_MAX_PROMPT_CHARS,
    )


def _response_stream(prompt: str, model: str, conversation_id=None):
    rid = new_response_id()
    created = int(time.time())
    item_id = f"msg_{uuid.uuid4().hex}"
    text = []
    final_conversation_id = conversation_id

    def response_object(status: str, output_text: str = "") -> dict:
        return {
            "id": rid,
            "object": "response",
            "created_at": created,
            "status": status,
            "model": model,
            "conversation_id": final_conversation_id,
            "output": [],
            "output_text": output_text,
            "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        }

    def event(name: str, payload: dict) -> str:
        body = {"type": name}
        body.update(payload)
        return named_sse_event(name, body)

    yield event("response.created", {"response": response_object("in_progress")})
    yield event(
        "response.output_item.added",
        {
            "output_index": 0,
            "item": {"id": item_id, "type": "message", "status": "in_progress", "role": "assistant", "content": []},
        },
    )
    yield event(
        "response.content_part.added",
        {"item_id": item_id, "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}},
    )

    try:
        with _upstream_lock:
            stream = client.stream(prompt, conversation_id=conversation_id)
            for piece in stream:
                if isinstance(piece, str) and piece:
                    text.append(piece)
                    yield event(
                        "response.output_text.delta",
                        {"item_id": item_id, "output_index": 0, "content_index": 0, "delta": piece},
                    )
            final_conversation_id = stream.conversation_id
    except ClearanceRequired:
        text.append(f"[error: {_CLEARANCE_HELP}]")
    except Exception as exc:
        text.append(f"[error: {exc}]")

    output_text = "".join(text)
    final_part = {"type": "output_text", "text": output_text, "annotations": []}
    final_item = {
        "id": item_id,
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [final_part],
    }
    final_response = response_object("completed", output_text)
    final_response["conversation_id"] = final_conversation_id
    final_response["output"] = [final_item]
    if final_conversation_id is not None:
        _response_conversations[rid] = final_conversation_id

    yield event(
        "response.output_text.done",
        {"item_id": item_id, "output_index": 0, "content_index": 0, "text": output_text},
    )
    yield event(
        "response.content_part.done",
        {"item_id": item_id, "output_index": 0, "content_index": 0, "part": final_part},
    )
    yield event("response.output_item.done", {"output_index": 0, "item": final_item})
    yield event("response.completed", {"response": final_response})
    yield "data: [DONE]\n\n"


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {"id": MODEL_NAME, "object": "model", "created": 0, "owned_by": "microsoft"}
        ],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest):
    prompt = messages_to_prompt(req.messages)
    if not prompt.strip():
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "no text content in messages", "type": "invalid_request_error"}},
        )
    model = req.model or MODEL_NAME

    # Enforce the per-minute ceiling before touching the upstream lock, so excess
    # callers get a fast 429 instead of piling up behind the serialized queue.
    limited = _rate_limited_response()
    if limited is not None:
        return limited

    prompt = _prepare_prompt(prompt)

    if req.stream:
        return StreamingResponse(
            _stream(prompt, model, req.conversation_id), media_type="text/event-stream"
        )

    try:
        with _upstream_lock:  # serialize: one upstream chat at a time
            reply = client.chat(prompt, conversation_id=req.conversation_id)
    except ClearanceRequired:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": _CLEARANCE_HELP, "type": "clearance_required"}},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": str(exc), "type": "upstream_error"}},
        )
    return completion_response(reply.text, model, reply.conversation_id)


@app.post("/v1/responses")
def responses(req: ResponsesRequest):
    prompt = _responses_prompt(req)
    if not prompt.strip():
        return JSONResponse(
            status_code=400,
            content={"error": {"message": "no text content in input", "type": "invalid_request_error"}},
        )
    model = req.model or MODEL_NAME
    conversation_id = req.conversation_id or _response_conversations.get(req.previous_response_id)

    limited = _rate_limited_response()
    if limited is not None:
        return limited

    prompt = _prepare_prompt(prompt)

    if req.stream:
        return StreamingResponse(
            _response_stream(prompt, model, conversation_id), media_type="text/event-stream"
        )

    try:
        with _upstream_lock:
            reply = client.chat(prompt, conversation_id=conversation_id)
    except ClearanceRequired:
        return JSONResponse(
            status_code=503,
            content={"error": {"message": _CLEARANCE_HELP, "type": "clearance_required"}},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error": {"message": str(exc), "type": "upstream_error"}},
        )
    return _responses_payload(reply.text, model, reply.conversation_id)


@app.get("/")
def root():
    return {"service": "Copilot OpenAI-compatible API", "endpoints": ["/v1/models", "/v1/chat/completions", "/v1/responses"]}
