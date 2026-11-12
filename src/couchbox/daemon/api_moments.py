"""Moments (couchbox.moments): Settings → Moments changes them, the home screen's tiles start them
(`couchbox moment start ID`, as the TV user). Starting, stopping and "what plays now" happen in
the voice service (couchbox.voice.moments), which drives the apps; these hand it on."""

import json
import urllib.request
from typing import Any

from couchbox import moments

from .api import UserError, _set, _user_errors, method

VOICE = "http://127.0.0.1:8790"


def _voice(path: str, body: dict[str, Any] | None = None, timeout: float = 60) -> dict[str, Any]:
    req = urllib.request.Request(
        VOICE + path, json.dumps(body or {}).encode(), {"Content-Type": "application/json", "X-Couchbox": "1"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = json.load(r)
    except (OSError, ValueError):
        raise UserError("The voice service isn't running, and it plays Moments.") from None
    if not out.get("ok"):
        raise UserError(out.get("result") or "That didn't work.")
    return out


def _one(mid: str) -> dict[str, Any]:
    m = moments.get(mid)
    if not m:
        raise UserError("There's no such Moment any more.")
    return m


@method("moments.list", write=False)
def moments_list() -> dict[str, Any]:
    return {"moments": moments.all(), "active": moments.active_id(), "describe": {m["id"]: moments.describe(m) for m in moments.all()}}


@method("moments.update")
@_user_errors
def moments_update(id: str, changes: dict[str, Any]) -> dict[str, Any]:  # noqa: A002 - the API's name
    """Rename it, or change its volume, repeat, dark picture or "when leaving"."""
    m = _one(id)
    allowed = {k: v for k, v in (changes or {}).items() if k in ("name", "volume", "repeat", "dark", "leaving")}
    if "name" in allowed:
        name = str(allowed["name"]).strip()
        if any(moments.words(x["name"]) == moments.words(name) and x["id"] != id for x in moments.all()):
            raise UserError(f"There's already a Moment called {name}.")
    new = dict(m, **allowed)
    return _set({moments.KEY: [new if x["id"] == id else x for x in moments.all()]})


@method("moments.delete")
@_user_errors
def moments_delete(id: str) -> dict[str, Any]:  # noqa: A002
    _one(id)
    if moments.active_id() == id:
        try:
            _voice("/moments/stop")
        except UserError:
            pass
    return _set({moments.KEY: [x for x in moments.all() if x["id"] != id]})


@method("moments.capture")
@_user_errors
def moments_capture(id: str) -> dict[str, Any]:  # noqa: A002
    """It plays what's playing now instead (its name and options stay)."""
    m = _one(id)
    got = _voice("/moments/capture", timeout=20)["moment"]
    new = dict(m, **{k: got[k] for k in ("app", "target", "title", "art")})
    return _set({moments.KEY: [new if x["id"] == id else x for x in moments.all()]})


@method("moments.start")
def moments_start(id: str) -> dict[str, Any]:  # noqa: A002
    _one(id)
    return {"result": _voice("/moments/start", {"id": id})["result"]}


@method("moments.stop")
def moments_stop() -> dict[str, Any]:
    return {"result": _voice("/moments/stop")["result"]}
