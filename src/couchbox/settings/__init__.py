"""Settings: package defaults (schema.json) overlaid with the user's changes (settings.json).

    from couchbox import settings
    s = settings.load()
    s["voice.mode"]                 -> "off"
    settings.update({"voice.mode": "dictation"})   validated, written atomically

Only changed keys are stored, so better defaults reach everyone in updates. Secrets never
live here: see couchbox.secrets.
"""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from couchbox import paths

from .migrations import MIGRATIONS


class SettingsError(ValueError):
    """A value the schema doesn't allow (message is shown to the user)."""


_schema_cache: dict[str, Any] = {}


def schema() -> dict[str, Any]:
    f = paths.schema_file()
    key = str(f)
    if key not in _schema_cache:
        _schema_cache[key] = json.loads(f.read_text())
    return _schema_cache[key]


def spec(key: str) -> dict[str, Any]:
    try:
        return schema()["settings"][key]
    except KeyError:
        raise SettingsError(f"Unknown setting: {key}") from None


def defaults() -> dict[str, Any]:
    return {k: v["default"] for k, v in schema()["settings"].items()}


def _read_overrides() -> dict[str, Any]:
    f = paths.settings_file()
    try:
        data = json.loads(f.read_text())
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        # A broken file must never take the TV down: run on defaults, keep the file for repair.
        return {}
    data = migrate(data)
    return {k: v for k, v in data.get("values", {}).items() if k in schema()["settings"]}


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    version = data.get("version", 1)
    values = dict(data.get("values", {}))
    while version in MIGRATIONS:
        values = MIGRATIONS[version](values)
        version += 1
    return {"version": version, "values": values}


def load() -> dict[str, Any]:
    """Every setting's current value."""
    values = defaults()
    for k, v in _read_overrides().items():
        try:
            values[k] = validate(k, v)
        except SettingsError:
            pass  # an old or hand-edited bad value: keep the default
    return values


def get(key: str) -> Any:
    spec(key)
    return load()[key]


def changed() -> dict[str, Any]:
    """Only the keys that differ from their defaults."""
    return _read_overrides()


def validate(key: str, value: Any) -> Any:
    """The value, normalized, or SettingsError."""
    s = spec(key)
    t = s["type"]
    label = s.get("label", key)
    if t == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false", "1", "0", "on", "off", "yes", "no"):
            return value.lower() in ("true", "1", "on", "yes")
        raise SettingsError(f"{label}: expected on or off")
    if t in ("int", "number"):
        try:
            n = int(value) if t == "int" else float(value)
        except (TypeError, ValueError):
            raise SettingsError(f"{label}: expected a number") from None
        if isinstance(value, bool) or (t == "int" and isinstance(value, float) and value != int(value)):
            raise SettingsError(f"{label}: expected a whole number")
        if "min" in s and n < s["min"] or "max" in s and n > s["max"]:
            raise SettingsError(f"{label}: must be between {s.get('min')} and {s.get('max')}")
        return n
    if t == "enum":
        if value not in s["values"]:
            raise SettingsError(f"{label}: must be one of {', '.join(s['values'])}")
        return value
    if t in ("string", "text", "url"):
        if not isinstance(value, str):
            raise SettingsError(f"{label}: expected text")
        value = value.strip() if t != "text" else value
        if "\x00" in value or (t != "text" and ("\n" in value or "\r" in value)):
            raise SettingsError(f"{label}: no line breaks allowed")
        if len(value) > s.get("max_len", 2048):
            raise SettingsError(f"{label}: too long (max {s.get('max_len', 2048)})")
        if "pattern" in s and not re.fullmatch(s["pattern"], value):
            raise SettingsError(f"{label}: not a valid value")
        if t == "url" and value:
            u = urlparse(value)
            if u.scheme not in ("http", "https") or not u.netloc:
                raise SettingsError(f"{label}: expected an http(s):// address")
            value = value.rstrip("/")
        return value
    if t == "list":
        if not isinstance(value, list):
            raise SettingsError(f"{label}: expected a list")
        item = s.get("items", "string")
        for v in value:
            if item == "string" and not (isinstance(v, str) and v and len(v) < 256 and "\n" not in v):
                raise SettingsError(f"{label}: bad entry {v!r}")
            if item == "object" and not isinstance(v, dict):
                raise SettingsError(f"{label}: bad entry {v!r}")
        if key == "home.web_apps":
            return [_web_app(v) for v in value]
        return value
    if t == "object":
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise SettingsError(f"{label}: expected names")
        return value
    raise SettingsError(f"{label}: unsupported type {t}")


def _web_app(v: dict[str, Any]) -> dict[str, str]:
    name, url = str(v.get("name", "")).strip(), str(v.get("url", "")).strip()
    u = urlparse(url)
    if not name or len(name) > 40 or u.scheme not in ("http", "https") or not u.netloc:
        raise SettingsError("Website: needs a name and an http(s):// address")
    wid = v.get("id") or "web-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30]
    if not re.fullmatch(r"web-[a-z0-9-]{1,30}", wid):
        raise SettingsError("Website: bad id")
    return {"id": wid, "name": name, "url": url}


def update(changes: dict[str, Any]) -> dict[str, Any]:
    """Validate and store changes (all or nothing). A value equal to the default is dropped
    from the file. Returns the changed keys with their new values."""
    clean = {k: validate(k, v) for k, v in changes.items()}
    current = _read_overrides()
    d = defaults()
    for k, v in clean.items():
        if v == d[k]:
            current.pop(k, None)
        else:
            current[k] = v
    write_overrides(current)
    write_env()
    return clean


def reset(key: str) -> None:
    spec(key)
    current = _read_overrides()
    current.pop(key, None)
    write_overrides(current)
    write_env()


def write_overrides(values: dict[str, Any]) -> None:
    data = {"version": max(MIGRATIONS, default=0) + 1 if MIGRATIONS else 1, "values": dict(sorted(values.items()))}
    _atomic_write(paths.settings_file(), json.dumps(data, indent=2) + "\n", 0o644)


def env_name(key: str) -> str:
    return "COUCHBOX_" + re.sub(r"[^A-Z0-9]", "_", key.upper())


def _env_value(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, list):
        return " ".join(x if isinstance(x, str) else json.dumps(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v)
    return str(v)


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def env() -> dict[str, str]:
    """Settings as environment variables (COUCHBOX_VOICE_MODE=off ...), plus derived values."""
    s = load()
    out = {env_name(k): _env_value(v) for k, v in s.items() if schema()["settings"][k]["type"] != "text"}
    out.update({env_name(k): _env_value(v) for k, v in derived(s).items()})
    return out


def derived(s: dict[str, Any] | None = None) -> dict[str, Any]:
    """Values worked out from other settings (names default to the device name, ...)."""
    s = s or load()
    name = s["network.hostname"]
    units = s["location.units"]
    if units == "auto":
        units = "imperial" if s["time.timezone"].startswith(("America/", "US/", "Pacific/Honolulu")) else "metric"
    return {
        "tv.user": "tv",
        "airplay.name": s["apps.airplay.name"] or name,
        "cec.name": (s["tv.cec.name"] or name)[:14],
        "units": units,
        "clock24": s["home.clock"] == "24h" or (s["home.clock"] == "auto" and units == "metric"),
        "weather": (f"{s['location.lat']},{s['location.lon']},{s['location.name']}" if s["home.weather"] and s["location.name"] else ""),
    }


def write_env() -> None:
    lines = ["# Generated from /etc/couchbox/settings.json by couchbox. Don't edit: use Settings or 'couchbox config set'."]
    lines += [f"{k}={_shell_quote(v)}" for k, v in sorted(env().items())]
    try:
        _atomic_write(paths.env_file(), "\n".join(lines) + "\n", 0o644)
    except PermissionError:
        pass  # not root (tests, the TV session): the daemon writes it


def _atomic_write(path: Path, text: str, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
