"""couchbox doctor: is everything working? Used by Settings → System, the updater's
post-update health check (--post-update) and CI (--container).

Each check returns ok / warn / fail with a short detail. Only "fail" fails a health check.
"""

import json
import os
import time
from collections.abc import Callable
from typing import Any

from couchbox import __version__, paths, settings
from couchbox.system import sh

CORE_UNITS = ["couchboxd.service", "couchbox-input.service", "couchbox-phone.service", "couchbox-memory.service"]


def _unit(name: str) -> tuple[str, str]:
    r = sh(["systemctl", "is-active", name], check=False).stdout.strip()
    if r == "active":
        return "ok", "running"
    enabled = sh(["systemctl", "is-enabled", name], check=False).stdout.strip()
    if enabled in ("disabled", "masked", "static") and name != "couchboxd.service":
        return "ok", f"{enabled}"
    return "fail", r or "not running"


def check_settings() -> tuple[str, str]:
    f = paths.settings_file()
    if f.exists():
        try:
            data = json.loads(f.read_text())
        except ValueError:
            return "fail", f"{f} isn't valid JSON (running on defaults)"
        bad = []
        for k, v in data.get("values", {}).items():
            try:
                settings.validate(k, v)
            except settings.SettingsError as e:
                bad.append(str(e))
        if bad:
            return "warn", "; ".join(bad[:3])
    return "ok", f"{len(settings.changed())} changed from defaults"


def check_daemon() -> tuple[str, str]:
    from couchbox import ipc

    try:
        v = ipc.call("ping", timeout=5)["version"]
    except ipc.IpcError as e:
        return "fail", str(e)
    return ("ok", v) if v == __version__ else ("fail", f"daemon runs {v}, installed {__version__} (restart pending)")


def check_session() -> tuple[str, str]:
    r = sh(["pgrep", "-u", "tv", "-x", "plasmashell"], check=False)
    if r.returncode != 0:
        # right after an update the shell may be restarting
        time.sleep(15)
        r = sh(["pgrep", "-u", "tv", "-x", "plasmashell"], check=False)
    return ("ok", "TV interface running") if r.returncode == 0 else ("fail", "the TV interface isn't running")


def check_home() -> tuple[str, str]:
    f = paths.state() / "home/home.json"
    try:
        n = len(json.loads(f.read_text())["apps"])
    except (OSError, ValueError, KeyError):
        return "fail", "home screen data missing (couchbox home rebuild)"
    return "ok", f"{n} apps on the home row"


def check_disk() -> tuple[str, str]:
    st = os.statvfs(str(paths.root()))
    free = st.f_bavail * st.f_frsize / 1e9
    return ("ok" if free > 2 else "warn" if free > 0.5 else "fail"), f"{free:.1f} GB free"


def check_network() -> tuple[str, str]:
    r = sh(["nmcli", "-t", "networking", "connectivity"], check=False).stdout.strip()
    return ("ok" if r == "full" else "warn"), r or "unknown"


def check_thermal() -> tuple[str, str]:
    r = sh(["vcgencmd", "get_throttled"], check=False)
    if r.returncode != 0:
        return "ok", "not a Pi"
    v = r.stdout.strip().split("=")[-1]
    return ("ok" if v == "0x0" else "warn"), f"throttled={v}"


def run(post_update: bool = False, container: bool = False) -> dict[str, Any]:
    checks: list[tuple[str, Callable[[], tuple[str, str]]]] = [("settings", check_settings)]
    if not container:
        checks += [(u, (lambda u=u: _unit(u))) for u in CORE_UNITS]
        checks += [("couchboxd", check_daemon), ("home", check_home), ("session", check_session)]
        if not post_update:
            checks += [("disk", check_disk), ("network", check_network), ("thermal", check_thermal)]
    results = []
    for name, fn in checks:
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001
            status, detail = "fail", f"check crashed: {e}"
        results.append({"name": name, "status": status, "detail": detail})
    worst = "fail" if any(r["status"] == "fail" for r in results) else "warn" if any(r["status"] == "warn" for r in results) else "ok"
    return {"version": __version__, "status": worst, "checks": results}
