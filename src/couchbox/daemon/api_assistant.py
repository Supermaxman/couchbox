"""The voice assistant's model for the TV apps: a plain chat completion (no tools), for
summaries and short answers (Search's "Summarize"). couchboxd makes the call because it holds
the model's API key, which the apps (the TV user) can't read."""

from typing import Any

from couchbox import settings

from .api import UserError, method
from .api_extra import _auth

MAX_MESSAGES = 8
MAX_CHARS = 60_000  # of all the messages: about 15k tokens


@method("assistant.complete")
def complete(messages: list[dict[str, Any]], max_tokens: int = 500) -> dict[str, Any]:
    import requests

    s = settings.load()
    if not (s["voice.llm.url"] and s["voice.llm.model"]):
        raise UserError("The assistant isn't set up (Settings → Voice).")
    msgs = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in messages[-MAX_MESSAGES:]
        if isinstance(m, dict) and m.get("role") in ("system", "user", "assistant")
    ]
    if not msgs or sum(len(m["content"]) for m in msgs) > MAX_CHARS:
        raise UserError("Nothing to ask, or too much at once.")
    # thinking models count their reasoning against max_tokens: the callers leave room for it
    body = {"model": s["voice.llm.model"], "messages": msgs, "max_tokens": max(16, min(int(max_tokens), 4000))}
    try:
        r = requests.post(f"{s['voice.llm.url'].rstrip('/')}/chat/completions", json=body, timeout=110, headers=_auth("voice.llm.api_key"))
    except requests.RequestException as e:
        raise UserError(f"The assistant isn't answering ({e.__class__.__name__}).") from None
    if r.status_code >= 400:
        raise UserError(f"The assistant said {r.status_code}.")
    try:
        choice = r.json()["choices"][0]
        msg = choice["message"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise UserError("The assistant's answer couldn't be read.") from None
    if not (msg.get("content") or "").strip() and choice.get("finish_reason") == "length":
        raise UserError("The assistant ran out of room before answering. Try again, or ask about less.")
    return {"text": msg.get("content") or ""}
