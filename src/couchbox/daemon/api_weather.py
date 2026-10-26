"""The Weather app's "today at a glance" line: the assistant's model (Settings → Voice) turns
the day's numbers into one friendly sentence. Here because only couchboxd may read the model's
API key; the answer is kept for a few hours per set of facts, so reopening the app costs nothing."""

import re
import threading
import time
from typing import Any

from couchbox import secrets, settings

from .api import method

KEEP = 3 * 3600
_cache: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()

PROMPT = (
    "You write the one-line weather summary at the top of a TV weather app. From the facts below, write ONE short, "
    "friendly sentence (at most 22 words) about today and anything worth planning for (an umbrella, a jacket, wind, "
    "sun cream, an alert). Plain text: no emoji, no quotes, no lists, don't start with 'Today'.\n\n"
)


def enabled(s: dict[str, Any] | None = None) -> bool:
    s = s or settings.load()
    return bool(s["voice.mode"] == "assistant" and s["voice.llm.url"] and s["voice.llm.model"])


def clean(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    text = text.strip().strip('"“”').splitlines()[0].strip() if text.strip() else ""
    return text[:200]


@method("weather.glance")
def weather_glance(facts: str) -> dict[str, Any]:
    """{"text": sentence} ("" when the assistant isn't set up or doesn't answer)."""
    import requests

    s = settings.load()
    if not enabled(s) or not facts.strip():
        return {"text": "", "enabled": False}
    key = facts.strip()[:2000]
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < KEEP:
            return {"text": hit[1], "enabled": True}
    body = {
        "model": s["voice.llm.model"],
        "max_tokens": 700,
        "messages": [{"role": "user", "content": PROMPT + key}],
        "chat_template_kwargs": {"enable_thinking": False},
    }
    k = secrets.get("voice.llm.api_key")
    try:
        r = requests.post(
            f"{s['voice.llm.url'].rstrip('/')}/chat/completions",
            json=body,
            timeout=60,
            headers={"Authorization": f"Bearer {k}"} if k else {},
        )
        r.raise_for_status()
        text = clean(r.json()["choices"][0]["message"].get("content") or "")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return {"text": "", "enabled": True}
    if text:
        with _lock:
            for old in [x for x, (t, _) in _cache.items() if time.time() - t > KEEP]:
                del _cache[old]
            _cache[key] = (time.time(), text)
    return {"text": text, "enabled": True}
