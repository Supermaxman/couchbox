"""Signing in to YouTube for the TV app (couchbox-yt), the way YouTube's own TV apps do: a code shown
on the TV, entered at youtube.com/activate (Google's device flow), then OAuth tokens for InnerTube.

    POST https://www.youtube.com/o/oauth2/device/code  {client_id, scope, device_id, device_model}
         -> {device_code, user_code, verification_url, expires_in (30 min), interval}
    POST https://www.youtube.com/o/oauth2/token        {client_id, client_secret, code: device_code,
         grant_type: http://oauth.net/grant_type/device/1.0}  -> "authorization_pending" until the code is
         entered, then {access_token (1 h), refresh_token}; later refresh_token -> a new access_token

The household enters codes on their phones whenever they get to it, so a code waits in pending.json
and a thread (Waiter) keeps checking it until it's used or expires: leaving the sign-in page, or
the app quitting and starting again, doesn't lose it.

One file per Google account in ~/.local/share/couchbox-yt/accounts/<id>.json (mode 600): its refresh
and access tokens and the channels it can watch as (the personal one and any brand accounts, from
InnerTube's account/accounts_list). A profile in "Who's watching" is one account and one channel;
InnerTube calls for a brand account carry its page id (context.user.onBehalfOfUser). Tokens never
reach the log or the QML.
"""

import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

import requests

# The OAuth client of YouTube's TV app (Leanback), as published in its player JavaScript and used by
# SmartTube and, until 2024, yt-dlp: public knowledge, not a secret of this project.
CLIENT_ID = "861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com"
CLIENT_SECRET = "SboVhoG9s0rNafixCSGGKXAT"
SCOPE = "http://gdata.youtube.com https://www.googleapis.com/auth/youtube-paid-content"
DEVICE_URL = "https://www.youtube.com/o/oauth2/device/code"
TOKEN_URL = "https://www.youtube.com/o/oauth2/token"
ACTIVATE = "youtube.com/activate"
TIMEOUT = (8, 20)


class SignedOut(RuntimeError):
    """The account's sign-in is gone (revoked, or the password changed): sign in again."""


def _write(path: str, data: dict[str, Any]) -> None:
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(data, f)
    os.replace(path + ".tmp", path)


def _read(path: str) -> dict[str, Any]:
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def account_id(refresh_token: str, email: str = "") -> str:
    """A stable file name for an account (never the token itself)."""
    return hashlib.sha256((email or refresh_token).encode()).hexdigest()[:16]


class Auth:
    """The box's YouTube accounts and the sign-in code being waited for."""

    def __init__(self, data_dir: str, session: requests.Session | None = None, on_event: Callable[[str, dict], None] | None = None):
        self.dir = data_dir
        self.adir = os.path.join(data_dir, "accounts")
        os.makedirs(self.adir, mode=0o700, exist_ok=True)
        os.chmod(self.adir, 0o700)
        self.s = session or requests.Session()
        self.on_event = on_event or (lambda name, data: None)
        self.lock = threading.Lock()
        self.waiter: threading.Thread | None = None
        self.last = {"state": "idle"}  # the code's latest state, for the sign-in page
        self.channels_for: Callable[[str], list[dict[str, Any]]] = lambda token: []  # youtube.py: accounts_list

    # ---------------------------------------------------------------- the device's id (YouTube's TV apps send one)
    def device_id(self) -> str:
        path = os.path.join(self.dir, "device.json")
        d = _read(path)
        if not d.get("id"):
            d = {"id": str(uuid.uuid4())}
            _write(path, d)
        return d["id"]

    # ---------------------------------------------------------------- signing in with a code
    @property
    def pending_file(self) -> str:
        return os.path.join(self.dir, "pending.json")

    def start(self) -> dict[str, Any]:
        """A new code for youtube.com/activate (replacing one still waiting)."""
        r = self.s.post(
            DEVICE_URL,
            json={"client_id": CLIENT_ID, "scope": SCOPE, "device_id": self.device_id(), "device_model": "ytlr::"},
            timeout=TIMEOUT,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"YouTube didn't give a sign-in code ({r.status_code}).")
        j = r.json()
        pending = {
            "device_code": j["device_code"],
            "user_code": j["user_code"],
            "expires_at": time.time() + int(j.get("expires_in") or 1800),
            "interval": max(2, int(j.get("interval") or 5)),
        }
        _write(self.pending_file, pending)
        self.last = {"state": "waiting"}
        self.resume()
        return self.code()

    def code(self) -> dict[str, Any]:
        """The code waiting to be entered (for the sign-in page), or {"state": ...} without one."""
        p = _read(self.pending_file)
        if p and p.get("expires_at", 0) <= time.time():
            return {"state": "expired"}
        if not p:
            return dict(self.last) if self.last.get("state") != "waiting" else {"state": "expired"}
        code = p["user_code"]
        return {
            "state": "waiting",
            "code": code,
            "url": ACTIVATE,
            # the QR code opens Google's device page with the code filled in
            "full": f"https://www.google.com/device?user_code={code}",
            "expires": int(p["expires_at"] - time.time()),
        }

    def resume(self) -> None:
        """Keep checking a waiting code (at start too: the app may have quit since it was shown)."""
        with self.lock:
            if self.waiter and self.waiter.is_alive():
                return
            p = _read(self.pending_file)
            if not p or p.get("expires_at", 0) <= time.time():
                return
            self.waiter = threading.Thread(target=self._wait, name="yt-signin", daemon=True)
            self.waiter.start()

    def cancel(self) -> None:
        try:
            os.remove(self.pending_file)
        except OSError:
            pass
        self.last = {"state": "idle"}

    def _wait(self) -> None:
        while True:
            p = _read(self.pending_file)
            if not p:
                return  # cancelled, or used
            if p.get("expires_at", 0) <= time.time():
                self.cancel()
                self.last = {"state": "expired"}
                self.on_event("signInExpired", {})
                return
            time.sleep(p.get("interval", 5))
            try:
                st = self.exchange(p)
            except (requests.RequestException, ValueError):
                continue  # offline for a moment: keep trying until the code expires
            if st["state"] == "slow":
                p["interval"] = p.get("interval", 5) + 5
                _write(self.pending_file, p)
            elif st["state"] != "waiting":
                if _read(self.pending_file).get("device_code") == p["device_code"]:
                    self.cancel()
                self.last = st
                if st["state"] == "ok":
                    self.on_event("signedIn", {"account": st["account"], "name": st.get("name", "")})
                return

    def exchange(self, p: dict[str, Any]) -> dict[str, Any]:
        """One check of a code: {"state": "waiting" | "slow" | "ok" (saved) | "denied" | "expired"}."""
        r = self.s.post(
            TOKEN_URL,
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": p["device_code"],
                "grant_type": "http://oauth.net/grant_type/device/1.0",
            },
            timeout=TIMEOUT,
        )
        j = r.json()
        err = j.get("error", "")
        if err == "authorization_pending":
            return {"state": "waiting"}
        if err == "slow_down":
            return {"state": "slow"}
        if err:
            return {"state": "denied" if err == "access_denied" else "expired"}
        acct = self.add(j)
        return {"state": "ok", "account": acct["id"], "name": acct.get("name", "")}

    # ---------------------------------------------------------------- accounts
    def add(self, tokens: dict[str, Any]) -> dict[str, Any]:
        """Save a new sign-in (a token response) with the account's channels."""
        access = tokens["access_token"]
        channels = []
        try:
            channels = self.channels_for(access)
        except Exception:
            pass  # saved anyway; the channels are fetched again on the next start
        main = next((c for c in channels if c.get("main")), channels[0] if channels else {})
        acct = {
            "id": account_id(tokens.get("refresh_token", access), main.get("email", "")),
            "refresh_token": tokens.get("refresh_token", ""),
            "access_token": access,
            "expires_at": time.time() + int(tokens.get("expires_in") or 3600) - 60,
            "name": main.get("name", ""),
            "email": main.get("email", ""),
            "channels": channels,
            "added": time.time(),
        }
        old = self.account(acct["id"])
        if old and not acct["refresh_token"]:
            acct["refresh_token"] = old.get("refresh_token", "")
        _write(self._path(acct["id"]), acct)
        return acct

    def _path(self, aid: str) -> str:
        return os.path.join(self.adir, f"{aid}.json")

    def account(self, aid: str) -> dict[str, Any]:
        return _read(self._path(aid)) if aid and "/" not in aid else {}

    def accounts(self) -> list[dict[str, Any]]:
        out = []
        for f in sorted(os.listdir(self.adir)):
            if f.endswith(".json"):
                a = _read(os.path.join(self.adir, f))
                if a.get("refresh_token") or a.get("access_token"):
                    out.append(a)
        return sorted(out, key=lambda a: a.get("added", 0))

    def remove(self, aid: str) -> None:
        try:
            os.remove(self._path(aid))
        except OSError:
            pass

    def save_channels(self, aid: str, channels: list[dict[str, Any]]) -> None:
        a = self.account(aid)
        if a and channels:
            a["channels"] = channels
            main = next((c for c in channels if c.get("main")), channels[0])
            a["name"], a["email"] = main.get("name", a.get("name", "")), main.get("email", a.get("email", ""))
            _write(self._path(aid), a)

    def expire(self, aid: str) -> None:
        """YouTube refused the access token: the next token() renews it."""
        a = self.account(aid)
        if a:
            a["expires_at"] = 0
            _write(self._path(aid), a)

    def token(self, aid: str) -> str:
        """The account's access token, refreshed when it's (nearly) out of date."""
        with self.lock:
            a = self.account(aid)
            if not a:
                raise SignedOut("That account isn't signed in on this TV.")
            if a.get("access_token") and a.get("expires_at", 0) > time.time():
                return a["access_token"]
            r = self.s.post(
                TOKEN_URL,
                json={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "refresh_token": a.get("refresh_token", ""),
                    "grant_type": "refresh_token",
                },
                timeout=TIMEOUT,
            )
            j = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if j.get("error") in ("invalid_grant", "unauthorized_client"):
                raise SignedOut(f"{a.get('name') or 'This account'} was signed out of YouTube: sign in again.")
            if not j.get("access_token"):
                raise RuntimeError(f"Couldn't renew the YouTube sign-in ({r.status_code}).")
            a["access_token"] = j["access_token"]
            a["expires_at"] = time.time() + int(j.get("expires_in") or 3600) - 60
            _write(self._path(aid), a)
            return a["access_token"]

    # ---------------------------------------------------------------- profiles (who's watching)
    def profiles(self) -> list[dict[str, Any]]:
        """Every channel of every account: {id: "<account>:<page id>", name, handle, photo, premium}."""
        out = []
        for a in self.accounts():
            chans = a.get("channels") or [{"name": a.get("name") or "YouTube account", "main": True}]
            for c in chans:
                out.append(
                    {
                        "id": f"{a['id']}:{c.get('pageId', '') if not c.get('main') else ''}",
                        "account": a["id"],
                        "pageId": "" if c.get("main") else c.get("pageId", ""),
                        "name": c.get("name", ""),
                        "handle": c.get("handle", ""),
                        "photo": c.get("photo", ""),
                        "premium": bool(c.get("premium", a.get("premium", False))),
                    }
                )
        return out

    def last_profile(self) -> str:
        return _read(os.path.join(self.dir, "profile.json")).get("id", "")

    def set_last_profile(self, pid: str) -> None:
        _write(os.path.join(self.dir, "profile.json"), {"id": pid})

    def set_premium(self, aid: str, premium: bool) -> None:
        a = self.account(aid)
        if a and a.get("premium") != premium:
            a["premium"] = premium
            _write(self._path(aid), a)
