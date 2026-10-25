"""Smaller helpers for Settings: Jellyfin discovery, voice server tests, Fire remote IR."""

import io
import json
import socket
import struct
import time
import wave
from typing import Any

from couchbox import secrets, settings
from couchbox.system import sh

from .api import UserError, method


@method("media.jellyfin_discover", write=False)
def jellyfin_discover(seconds: float = 2.5) -> list[dict[str, str]]:
    """Jellyfin servers on the LAN: they answer "who is JellyfinServer?" on UDP 7359."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.settimeout(0.3)
    found: dict[str, dict[str, str]] = {}
    try:
        s.sendto(b"who is JellyfinServer?", ("255.255.255.255", 7359))
        end = time.time() + seconds
        while time.time() < end:
            try:
                data, _ = s.recvfrom(4096)
            except TimeoutError:
                continue
            try:
                d = json.loads(data)
            except ValueError:
                continue
            if d.get("Address"):
                found[d["Address"]] = {"name": d.get("Name", "Jellyfin"), "url": d["Address"].rstrip("/")}
    finally:
        s.close()
    return list(found.values())


def _auth(name: str) -> dict[str, str]:
    k = secrets.get(name)
    return {"Authorization": f"Bearer {k}"} if k else {}


def _silence_wav(seconds: float = 1.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(struct.pack("<h", 0) * int(16000 * seconds))
    return buf.getvalue()


@method("voice.test_stt")
def test_stt() -> dict[str, Any]:
    import requests

    s = settings.load()
    if not s["voice.stt.url"]:
        raise UserError("Set the speech-to-text server first.")
    t = time.time()
    try:
        r = requests.post(f"{s['voice.stt.url']}/audio/transcriptions", timeout=30, headers=_auth("voice.stt.api_key"),
                          files={"file": ("test.wav", _silence_wav(), "audio/wav")}, data={"model": s["voice.stt.model"]})
    except requests.RequestException as e:
        raise UserError(f"No answer: {e.__class__.__name__}") from None
    if r.status_code in (401, 403):
        raise UserError("The server wants an API key (or a different one).")
    if r.status_code == 404:
        raise UserError("No /audio/transcriptions there. The address usually ends in /v1.")
    if r.status_code >= 400:
        raise UserError(f"The server said {r.status_code}: {r.text[:120]}")
    return {"message": f"Works ({time.time() - t:.1f} s)"}


@method("voice.models", write=False)
def voice_models() -> list[str]:
    import requests

    s = settings.load()
    if not s["voice.llm.url"]:
        return []
    try:
        r = requests.get(f"{s['voice.llm.url']}/models", timeout=10, headers=_auth("voice.llm.api_key"))
        return sorted(m["id"] for m in r.json().get("data", []))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return []


@method("voice.test_llm")
def test_llm() -> dict[str, Any]:
    import requests

    s = settings.load()
    if not (s["voice.llm.url"] and s["voice.llm.model"]):
        raise UserError("Set the assistant server and model first.")
    t = time.time()
    body = {"model": s["voice.llm.model"], "max_tokens": 400,
            "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
            "tools": [{"type": "function", "function": {"name": "noop", "description": "Does nothing.", "parameters": {"type": "object", "properties": {}}}}]}
    try:
        r = requests.post(f"{s['voice.llm.url']}/chat/completions", json=body, timeout=90, headers=_auth("voice.llm.api_key"))
    except requests.RequestException as e:
        raise UserError(f"No answer: {e.__class__.__name__}") from None
    if r.status_code in (401, 403):
        raise UserError("The server wants an API key (or a different one).")
    if r.status_code >= 400:
        raise UserError(f"The server said {r.status_code}: {r.text[:160]}")
    return {"message": f"Works ({time.time() - t:.1f} s)"}


BRANDS = [{"id": "samsung", "name": "Samsung", "tested": True}]


@method("remote.ir_brands", write=False)
def ir_brands() -> list[dict[str, Any]]:
    return BRANDS


@method("remote.ir_program")
def ir_program(brand: str) -> dict[str, Any]:
    if brand not in {b["id"] for b in BRANDS}:
        raise UserError("That TV brand isn't supported yet.")
    r = sh(["/usr/lib/couchbox/bin/couchbox-remote-ir", "program"], check=False, timeout=90)
    if r.returncode != 0:
        raise UserError("Couldn't reach the remote. Press a button on it to wake it, then try again.")
    return {"message": "Power, Volume and Mute on the Fire TV remote now control the TV by infrared. Try them."}
