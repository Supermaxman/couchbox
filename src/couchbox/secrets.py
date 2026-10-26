"""Secrets (API keys, auth keys, the phone pairing token): one root-only file each in
/var/lib/couchbox/secrets. Written through couchboxd, read only by the services that need
them, never shown back in the UI or included in settings exports."""

import hashlib
import hmac
import os
import re
import secrets as _random

from couchbox import paths, settings

_NAME = re.compile(r"^[a-z0-9_.]+$")


def names() -> list[str]:
    return list(settings.schema()["secrets"])


def _file(name: str):
    if name not in settings.schema()["secrets"] or not _NAME.match(name):
        raise settings.SettingsError(f"Unknown secret: {name}")
    return paths.secrets_dir() / name


def get(name: str) -> str:
    """The value, or "" when unset. Callers must be root (or the file's owner)."""
    try:
        return _file(name).read_text().strip()
    except FileNotFoundError:
        return ""


def is_set(name: str) -> bool:
    return _file(name).exists()


def status() -> dict[str, bool]:
    return {n: is_set(n) for n in names()}


def put(name: str, value: str) -> None:
    value = value.strip()
    if not value:
        return clear(name)
    if len(value) > 4096 or "\n" in value or "\x00" in value:
        raise settings.SettingsError("That key doesn't look right (one line, under 4 KB).")
    d = paths.secrets_dir()
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    f = _file(name)
    tmp = f.with_name(f".{f.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(value + "\n")
    os.replace(tmp, f)


def clear(name: str) -> None:
    try:
        _file(name).unlink()
    except FileNotFoundError:
        pass


def ensure_token(name: str = "phone.token") -> str:
    """The phone pairing token, made on first use."""
    t = get(name)
    if not t:
        t = _random.token_urlsafe(18)
        put(name, t)
    return t


PAIR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to mix up


def pair_code(token: str) -> str:
    """The pairing code to type on the phone page, where a QR code can't be scanned (an
    iPhone home-screen web app keeps its own storage). It comes from the token, so New pairing
    code changes it too: 8 characters, about 10^12 choices, shown as ABCD-EFGH."""
    if not token:
        return ""
    d = hmac.new(token.encode(), b"couchbox-pair-code", hashlib.sha256).digest()
    c = "".join(PAIR_ALPHABET[b % 32] for b in d[:8])
    return f"{c[:4]}-{c[4:]}"


def check_pair_code(given: str, name: str = "phone.token") -> str:
    """The token when `given` is this box's pairing code (any case, dashes and spaces ignored), else ""."""
    token = get(name)
    want = pair_code(token).replace("-", "")
    given = re.sub(r"[^A-Za-z0-9]", "", given or "").upper()
    return token if want and hmac.compare_digest(want, given) else ""


def mask(text: str) -> str:
    """Hide every known secret value in text (for logs)."""
    for n in names():
        v = get(n) if os.access(paths.secrets_dir(), os.R_OK) else ""
        if len(v) >= 6:
            text = text.replace(v, v[:3] + "…")
    return text
