"""couchboxd's methods. Each is registered with @method(name, write=...); write methods
need root or the couchbox group (checked by the server). Raise UserError with a message
fit for the TV screen; anything else is logged and reported as "<method> failed"."""

import json
import logging
import os
import platform
import re
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from couchbox import __version__, apps, home, paths, secrets, settings
from couchbox.system import CommandError, out, sh

from . import apply, events

log = logging.getLogger("couchboxd")


class UserError(Exception):
    pass


@dataclass
class Method:
    fn: Callable[..., Any]
    write: bool


METHODS: dict[str, Method] = {}


def method(name: str, write: bool = True):
    def deco(fn):
        METHODS[name] = Method(fn, write)
        return fn

    return deco


def _user_errors(fn):
    def wrapped(*a, **kw):
        try:
            return fn(*a, **kw)
        except (settings.SettingsError, CommandError) as e:
            raise UserError(str(e)) from None

    wrapped.__name__ = fn.__name__
    return wrapped


async def startup() -> None:
    """Make sure generated files exist (first start, after an update), then do the jobs the
    first boot left for when the network is up."""
    import asyncio

    try:
        settings.write_env()
    except OSError as e:
        log.warning("env file: %s", e)
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _safe(home.build))
    loop.run_in_executor(None, pending_jobs)


def _safe(fn):
    def run():
        try:
            fn()
        except Exception:  # noqa: BLE001
            log.exception("%s", fn.__name__)

    return run


def geocode(name: str) -> dict[str, Any] | None:
    """A place name -> {name, lat, lon, country, timezone} (Open-Meteo, no key)."""
    import urllib.parse
    import urllib.request

    q = urllib.parse.urlencode({"name": name.split(",")[0].strip(), "count": 8, "language": "en", "format": "json"})
    with urllib.request.urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{q}", timeout=15) as r:
        res = json.load(r).get("results") or []
    if not res:
        return None
    hint = name.split(",", 1)[1].strip().lower() if "," in name else ""
    best = next(
        (x for x in res if hint and hint in (x.get("admin1", "") + " " + x.get("country_code", "") + " " + x.get("country", "")).lower()),
        res[0],
    )
    label = ", ".join(v for v in (best.get("name"), best.get("admin1") if best.get("country_code") == "US" else best.get("country")) if v)
    return {
        "name": label,
        "lat": round(best["latitude"], 4),
        "lon": round(best["longitude"], 4),
        "country": best.get("country_code", ""),
        "timezone": best.get("timezone", ""),
    }


@method("location.search", write=False)
def location_search(name: str) -> list[dict[str, Any]]:
    import urllib.parse
    import urllib.request

    q = urllib.parse.urlencode({"name": name.strip(), "count": 10, "language": "en", "format": "json"})
    try:
        with urllib.request.urlopen(f"https://geocoding-api.open-meteo.com/v1/search?{q}", timeout=15) as r:
            res = json.load(r).get("results") or []
    except OSError as e:
        raise UserError(f"Couldn't look that up: {e}") from None
    return [
        {
            "name": ", ".join(v for v in (x.get("name"), x.get("admin1"), x.get("country")) if v),
            "lat": round(x["latitude"], 4),
            "lon": round(x["longitude"], 4),
            "timezone": x.get("timezone", ""),
            "country": x.get("country_code", ""),
        }
        for x in res
    ]


def pending_jobs() -> None:
    """Jobs couchbox-firstboot left (pending.json), retried until the network is up."""
    f = paths.state() / "state/pending.json"
    for _ in range(120):
        try:
            jobs = json.loads(f.read_text())
        except (OSError, ValueError):
            return
        left = []
        for j in jobs:
            try:
                if j["job"] == "geocode":
                    g = geocode(j["name"])
                    if g:
                        settings.update({"location.name": g["name"], "location.lat": g["lat"], "location.lon": g["lon"]})
                        home.build()
                elif j["job"] == "ssh_github":
                    ssh_import_github(j["user"])
                    apply.apply({"ssh.enabled": True}, settings.load())
                elif j["job"] == "tailscale_up":
                    tailscale_up()
            except Exception as e:  # noqa: BLE001 - offline yet: keep it for the next round
                log.info("pending %s: %s", j["job"], e)
                left.append(j)
        if not left:
            f.unlink(missing_ok=True)
            return
        f.write_text(json.dumps(left) + "\n")
        time.sleep(30)


# ------------------------------------------------------------------ settings and secrets
@method("ping", write=False)
def ping() -> dict[str, Any]:
    return {"version": __version__, "time": time.time()}


@method("settings.schema", write=False)
def settings_schema() -> dict[str, Any]:
    return settings.schema()


@method("settings.get", write=False)
def settings_get(keys: list[str] | None = None) -> dict[str, Any]:
    s = settings.load()
    if keys:
        unknown = [k for k in keys if k not in s]
        if unknown:
            raise UserError(f"Unknown setting: {unknown[0]}")
        return {k: s[k] for k in keys}
    return s


@method("settings.set")
@_user_errors
def settings_set(changes: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes:
        raise UserError("Nothing to change.")
    before = settings.load()
    clean = settings.update(changes)
    changed = {k: v for k, v in clean.items() if before.get(k) != v}
    notes = apply.apply(changed, settings.load())
    events.publish("settings.changed", changed)
    return {"changed": changed, "notes": notes}


@method("settings.reset")
@_user_errors
def settings_reset(key: str) -> dict[str, Any]:
    settings.reset(key)
    value = settings.get(key)
    apply.apply({key: value}, settings.load())
    events.publish("settings.changed", {key: value})
    return {key: value}


@method("settings.export", write=False)
def settings_export() -> dict[str, Any]:
    return {"couchbox": __version__, "settings": settings.changed()}


@method("settings.import")
@_user_errors
def settings_import(data: dict[str, Any]) -> dict[str, Any]:
    values = data.get("settings", data)
    known = {k: v for k, v in values.items() if k in settings.schema()["settings"]}
    return settings_set(known) if known else {"changed": {}, "notes": []}


@method("secrets.status", write=False)
def secrets_status() -> dict[str, bool]:
    return secrets.status()


@method("secrets.set")
@_user_errors
def secrets_set(name: str, value: str) -> dict[str, bool]:
    secrets.put(name, value)
    apply.secret_changed(name)
    events.publish("secrets.changed", {name: bool(value.strip())})
    return {name: secrets.is_set(name)}


@method("secrets.clear")
@_user_errors
def secrets_clear(name: str) -> dict[str, bool]:
    secrets.clear(name)
    apply.secret_changed(name)
    events.publish("secrets.changed", {name: False})
    return {name: False}


# ------------------------------------------------------------------ apps and home screen
@method("apps.list", write=False)
def apps_list() -> list[dict[str, Any]]:
    s = settings.load()
    row = [a.id for a in apps.home_row(s)]
    out_ = []
    for a in apps.all_apps(s):
        d = a.to_dict()
        d.update(
            available=a.available(s),
            missing=a.missing(s),
            on_home=a.id in row,
            position=row.index(a.id) if a.id in row else -1,
            hidden=a.id in s["home.hidden"],
            display_name=s["home.names"].get(a.id, a.name),
        )
        out_.append(d)
    return sorted(out_, key=lambda d: (d["position"] < 0, d["position"], d["default_order"]))


@method("home.row", write=False)
def home_row() -> dict[str, Any]:
    return home.row_json()


def _set(changes: dict[str, Any]) -> dict[str, Any]:
    return settings_set(changes)


@method("home.move")
@_user_errors
def home_move(app: str, index: int) -> dict[str, Any]:
    s = settings.load()
    return _set({"home.layout": apps.move(s["home.layout"], app, int(index), s)})


@method("home.hide")
@_user_errors
def home_hide(app: str, hidden: bool = True) -> dict[str, Any]:
    s = settings.load()
    a = apps.get(app, s)
    if not a:
        raise UserError(f"No app {app}")
    if not a.hideable:
        raise UserError(f"{a.name} always stays on the home screen.")
    h = [x for x in s["home.hidden"] if x != app] + ([app] if hidden else [])
    changes: dict[str, Any] = {"home.hidden": h}
    if not hidden and app not in s["home.layout"] and not a.default_visible:
        changes["home.layout"] = [x.id for x in apps.home_row(s) if x.hideable] + [app]
    return _set(changes)


@method("home.rename")
@_user_errors
def home_rename(app: str, name: str) -> dict[str, Any]:
    s = settings.load()
    if not apps.get(app, s):
        raise UserError(f"No app {app}")
    names = dict(s["home.names"])
    name = name.strip()[:40]
    if name:
        names[app] = name
    else:
        names.pop(app, None)
    return _set({"home.names": names})


@method("home.add_web")
@_user_errors
def home_add_web(name: str, url: str) -> dict[str, Any]:
    s = settings.load()
    web = list(s["home.web_apps"])
    entry = settings.validate("home.web_apps", [{"name": name, "url": url}])[0]
    if any(w["id"] == entry["id"] for w in web) or apps.get(entry["id"], s):
        entry["id"] = f"{entry['id'][:26]}-{len(web) + 2}"
    web.append(entry)
    layout = [x.id for x in apps.home_row(s) if x.hideable] + [entry["id"]]
    return _set({"home.web_apps": web, "home.layout": layout})


@method("home.remove_web")
@_user_errors
def home_remove_web(app: str) -> dict[str, Any]:
    s = settings.load()
    web = [w for w in s["home.web_apps"] if w["id"] != app]
    if len(web) == len(s["home.web_apps"]):
        raise UserError("Only websites you added can be removed.")
    return _set(
        {
            "home.web_apps": web,
            "home.layout": [x for x in s["home.layout"] if x != app],
            "home.hidden": [x for x in s["home.hidden"] if x != app],
        }
    )


@method("home.reset")
@_user_errors
def home_reset() -> dict[str, Any]:
    return _set({"home.layout": [], "home.hidden": [], "home.names": {}})


@method("home.rebuild")
def home_rebuild(restart_shell: bool = False) -> dict[str, Any]:
    return home.build(restart_shell=restart_shell)


# ------------------------------------------------------------------ network
def _nm_fields(line: str) -> list[str]:
    """Split nmcli -t output (':' separated, '\\:' escaped)."""
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


@method("network.status", write=False)
def network_status() -> dict[str, Any]:
    devs = []
    for line in out(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"], check=False).splitlines():
        f = _nm_fields(line)
        if len(f) >= 4 and f[1] in ("ethernet", "wifi"):
            devs.append({"device": f[0], "type": f[1], "state": f[2], "connection": f[3]})
    ips = {}
    for line in out(["ip", "-4", "-o", "addr", "show"], check=False).splitlines():
        m = re.match(r"\d+: (\S+)\s+inet (\S+)/", line)
        if m and m.group(1) != "lo":
            ips[m.group(1)] = m.group(2)
    online = sh(["nmcli", "-t", "networking", "connectivity"], check=False).stdout.strip()
    return {"devices": devs, "ips": ips, "connectivity": online or "unknown", "hostname": platform.node()}


@method("network.wifi_scan", write=False)
def wifi_scan(rescan: bool = True, bounce: bool = False) -> list[dict[str, Any]]:
    """bounce: while the setup hotspot is up, take it down for a real scan ("Look again")."""
    if api_setup.hotspot_active():
        return api_setup.rescan() if bounce else api_setup.cached_scan()
    r = out(
        ["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ", "device", "wifi", "list", "--rescan", "yes" if rescan else "no"],
        check=False,
        timeout=30,
    )
    nets: dict[str, dict[str, Any]] = {}
    for line in r.splitlines():
        f = _nm_fields(line)
        if len(f) < 5 or not f[1]:
            continue
        n = {
            "ssid": f[1],
            "signal": int(f[2] or 0),
            "secure": bool(f[3].strip() and f[3] != "--"),
            "connected": f[0] == "*",
            "band": "5 GHz" if f[4].startswith("5") else "2.4 GHz",
        }
        if f[1] not in nets or n["signal"] > nets[f[1]]["signal"] or n["connected"]:
            nets[f[1]] = n
    return sorted(nets.values(), key=lambda n: (not n["connected"], -n["signal"]))


@method("network.wifi_connect")
@_user_errors
def wifi_connect(ssid: str, password: str = "", hidden: bool = False) -> dict[str, Any]:
    if not ssid or len(ssid) > 32:
        raise UserError("Network names are 1 to 32 characters.")
    if password and not 8 <= len(password) <= 63:
        raise UserError("Wi-Fi passwords are 8 to 63 characters.")
    if any(ord(c) < 32 for c in ssid + password):
        raise UserError("Network names and passwords can't contain control characters.")
    con = f"couchbox-{re.sub(r'[^A-Za-z0-9_-]', '_', ssid)}"
    had_hotspot = api_setup.hotspot_active()
    api_setup.hotspot_stop()  # one radio: the setup hotspot makes way (and comes back on failure)
    sh(["nmcli", "connection", "delete", "id", con], check=False)
    # A keyfile written root-only: the password never appears on a command line.
    esc = ssid.replace("\\", "\\\\")
    lines = [
        "[connection]",
        f"id={con}",
        f"uuid={uuid.uuid4()}",
        "type=wifi",
        "autoconnect=true",
        "",
        "[wifi]",
        "mode=infrastructure",
        f"ssid={esc}",
        f"hidden={'true' if hidden else 'false'}",
        "",
    ]
    if password:
        lines += ["[wifi-security]", "key-mgmt=wpa-psk", f"psk={password}", ""]
    lines += ["[ipv4]", "method=auto", "", "[ipv6]", "method=auto", ""]
    kf = paths.root() / f"etc/NetworkManager/system-connections/{con}.nmconnection"
    kf.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(kf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines))
    sh(["nmcli", "connection", "load", str(kf)], check=False)
    r = sh(["nmcli", "--wait", "40", "connection", "up", "id", con], check=False, timeout=60)
    if r.returncode != 0:
        sh(["nmcli", "connection", "delete", "id", con], check=False)
        if had_hotspot:
            try:
                api_setup.hotspot_start()
            except UserError:
                pass
        msg = (r.stderr or r.stdout).lower()
        if "secrets" in msg or "password" in msg or "802-1x" in msg:
            raise UserError("Wrong password, or the network refused it.")
        raise UserError("Couldn't join that network. Move closer, or check its name.")
    apply.wifi_changed()
    events.publish("network.changed", {"ssid": ssid})
    return network_status()


@method("network.wifi_forget")
@_user_errors
def wifi_forget(ssid: str) -> dict[str, Any]:
    for line in out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], check=False).splitlines():
        f = _nm_fields(line)
        if len(f) >= 2 and f[1] == "802-11-wireless":
            got = out(["nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "id", f[0]], check=False)
            if got == ssid:
                sh(["nmcli", "connection", "delete", "id", f[0]], check=False)
    events.publish("network.changed", {"forgot": ssid})
    return network_status()


# ------------------------------------------------------------------ time
@method("time.zones", write=False)
def time_zones() -> list[str]:
    z = out(["timedatectl", "list-timezones"], check=False)
    return z.splitlines() if z else []


@method("time.status", write=False)
def time_status() -> dict[str, Any]:
    r = out(["timedatectl", "show"], check=False)
    kv = dict(line.split("=", 1) for line in r.splitlines() if "=" in line)
    return {"timezone": kv.get("Timezone", ""), "synced": kv.get("NTPSynchronized") == "yes", "now": time.time()}


# ------------------------------------------------------------------ tailscale
_ts_login: dict[str, Any] = {}


@method("tailscale.status", write=False)
def tailscale_status() -> dict[str, Any]:
    r = sh(["tailscale", "status", "--json"], check=False)
    if r.returncode == 127:
        return {"installed": False, "state": "not installed"}
    try:
        st = json.loads(r.stdout)
    except ValueError:
        return {"installed": True, "state": "stopped", "login_url": _ts_login.get("url", "")}
    me = st.get("Self") or {}
    return {
        "installed": True,
        "state": st.get("BackendState", "unknown"),
        "name": (me.get("DNSName") or "").rstrip("."),
        "ips": me.get("TailscaleIPs") or [],
        "tailnet": (st.get("CurrentTailnet") or {}).get("Name", ""),
        "login_url": st.get("AuthURL") or _ts_login.get("url", ""),
    }


@method("tailscale.up")
@_user_errors
def tailscale_up(auth_key: str = "") -> dict[str, Any]:
    """Start tailscaled and sign in. Without a key, returns the login URL for the QR code."""
    if auth_key:
        secrets.put("tailscale.auth_key", auth_key)
    s = settings.load()
    if not s["tailscale.enabled"]:
        settings.update({"tailscale.enabled": True})
    sh(["systemctl", "enable", "--now", "tailscaled"], check=False)
    cmd = ["tailscale", "up", f"--hostname={s['network.hostname']}"]
    if s["tailscale.tags"]:
        cmd.append(f"--advertise-tags={s['tailscale.tags']}")
    key = secrets.get("tailscale.auth_key")
    if key:
        sh([*cmd, f"--auth-key=file:{paths.secrets_dir() / 'tailscale.auth_key'}"], timeout=90)
        secrets.clear("tailscale.auth_key")  # one-off: the node key is what persists
        apply.tailscale_serve(settings.load())
        events.publish("tailscale.changed", {"state": "Running"})
        return tailscale_status()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    found = threading.Event()

    def reader():
        for line in proc.stdout:
            m = re.search(r"https://login\.tailscale\.com/\S+", line)
            if m:
                _ts_login["url"] = m.group(0)
                found.set()
                events.publish("tailscale.login", {"url": m.group(0)})
        proc.wait()
        _ts_login.clear()
        apply.tailscale_serve(settings.load())
        events.publish("tailscale.changed", tailscale_status())

    threading.Thread(target=reader, daemon=True).start()
    found.wait(20)
    return tailscale_status()


@method("tailscale.down")
@_user_errors
def tailscale_down(logout: bool = False) -> dict[str, Any]:
    sh(["tailscale", "logout" if logout else "down"], check=False)
    settings.update({"tailscale.enabled": False})
    if logout:
        sh(["systemctl", "disable", "--now", "tailscaled"], check=False)
    events.publish("tailscale.changed", {"state": "Stopped"})
    return tailscale_status()


# ------------------------------------------------------------------ ssh
ADMIN = "admin"


def _authorized_keys():
    import pwd

    try:
        home_ = pwd.getpwnam(ADMIN).pw_dir
    except KeyError:
        raise UserError("The admin account is missing (reinstall the couchbox package).") from None
    return paths.root() / home_.lstrip("/") / ".ssh/authorized_keys"


@method("ssh.status", write=False)
def ssh_status() -> dict[str, Any]:
    active = sh(["systemctl", "is-active", "ssh"], check=False).stdout.strip() == "active"
    try:
        keys = [k for k in _authorized_keys().read_text().splitlines() if k.strip() and not k.startswith("#")]
    except (OSError, UserError):
        keys = []
    return {
        "enabled": settings.get("ssh.enabled"),
        "active": active,
        "user": ADMIN,
        "keys": [{"type": k.split()[0], "comment": " ".join(k.split()[2:]) or k.split()[1][-12:]} for k in keys if len(k.split()) >= 2],
    }


def _add_keys(keys: list[str]) -> int:
    f = _authorized_keys()
    have = set(f.read_text().splitlines()) if f.exists() else set()
    new = [k for k in keys if k and k not in have and re.match(r"^(ssh-(ed25519|rsa)|ecdsa-sha2-\S+|sk-\S+) [A-Za-z0-9+/=]+( .*)?$", k)]
    if new:
        f.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with open(f, "a") as fh:
            fh.write("".join(k + "\n" for k in new))
        os.chmod(f, 0o600)
        sh(["chown", "-R", f"{ADMIN}:{ADMIN}", str(f.parent)], check=False)
    return len(new)


@method("ssh.import_github")
@_user_errors
def ssh_import_github(user: str) -> dict[str, Any]:
    settings.validate("ssh.github_user", user)
    import urllib.request

    try:
        with urllib.request.urlopen(f"https://github.com/{user}.keys", timeout=15) as r:
            keys = r.read().decode().splitlines()
    except OSError as e:
        raise UserError(f"Couldn't get keys from GitHub: {e}") from None
    if not keys:
        raise UserError(f"github.com/{user} has no SSH keys.")
    n = _add_keys(keys)
    settings.update({"ssh.github_user": user})
    return {"added": n, **ssh_status()}


@method("ssh.add_key")
@_user_errors
def ssh_add_key(key: str) -> dict[str, Any]:
    n = _add_keys([key.strip()])
    if not n:
        raise UserError("That doesn't look like a new SSH public key.")
    return {"added": n, **ssh_status()}


@method("ssh.remove_keys")
@_user_errors
def ssh_remove_keys() -> dict[str, Any]:
    f = _authorized_keys()
    if f.exists():
        f.write_text("")
    return ssh_status()


# ------------------------------------------------------------------ phone page
@method("phone.pairing", write=False)
def phone_pairing() -> dict[str, Any]:
    """URL for the QR code. Read-only callers get it only when they may write too (the
    server checks write access for this method below)."""
    token = secrets.ensure_token()
    s = settings.load()
    base = f"http://{s['network.hostname']}.local:8791"
    ts = tailscale_status() if s["tailscale.enabled"] else {}
    if ts.get("state") == "Running" and ts.get("name") and s["tailscale.serve_phone_page"]:
        base = f"https://{ts['name']}"
    return {"url": f"{base}/#t={token}", "base": base, "code": secrets.pair_code(token)}


METHODS["phone.pairing"].write = True  # the token is a credential


@method("phone.rotate")
def phone_rotate() -> dict[str, Any]:
    secrets.clear("phone.token")
    secrets.ensure_token()
    events.publish("phone.rotated")
    return phone_pairing()


# ------------------------------------------------------------------ system
@method("system.info", write=False)
def system_info() -> dict[str, Any]:
    def read(p, default=""):
        try:
            return (paths.root() / p.lstrip("/")).read_text().strip("\x00\n ")
        except OSError:
            return default

    osr = dict(line.split("=", 1) for line in read("/etc/os-release").splitlines() if "=" in line)
    temp = read("/sys/class/thermal/thermal_zone0/temp")
    mem = dict(line.split(":", 1) for line in read("/proc/meminfo").splitlines() if ":" in line)
    st = os.statvfs(str(paths.root()))
    return {
        "version": __version__,
        "os": osr.get("PRETTY_NAME", "").strip('"'),
        "model": read("/proc/device-tree/model"),
        "kernel": platform.release(),
        "temp_c": round(int(temp) / 1000, 1) if temp.isdigit() else None,
        "mem_total_mb": int(mem.get("MemTotal", "0 kB").split()[0]) // 1024,
        "mem_free_mb": int(mem.get("MemAvailable", "0 kB").split()[0]) // 1024,
        "disk_total_gb": round(st.f_blocks * st.f_frsize / 1e9, 1),
        "disk_free_gb": round(st.f_bavail * st.f_frsize / 1e9, 1),
        "throttled": out(["vcgencmd", "get_throttled"], check=False).split("=")[-1] or None,
        "uptime_s": float(read("/proc/uptime", "0 0").split()[0]),
    }


@method("system.doctor", write=False)
def system_doctor() -> dict[str, Any]:
    from couchbox import doctor

    return doctor.run()


@method("system.reboot")
def system_reboot() -> dict[str, Any]:
    threading.Timer(2, lambda: sh(["systemctl", "reboot"], check=False)).start()
    return {"rebooting": True}


@method("system.restart_ui")
def system_restart_ui() -> dict[str, Any]:
    home.restart_plasmashell()
    return {"restarted": True}


@method("system.factory_reset")
@_user_errors
def system_factory_reset(keep_wifi: bool = True, confirm: str = "") -> dict[str, Any]:
    if confirm != "RESET":
        raise UserError("Confirm with RESET.")
    for f in [paths.settings_file()]:
        f.unlink(missing_ok=True)
    for n in secrets.names():
        secrets.clear(n)
    (paths.state() / "state/setup.json").unlink(missing_ok=True)
    tvdata = home.tv_home() / ".local/share/couchbox"
    sh(["rm", "-rf", str(tvdata)], check=False)
    if not keep_wifi:
        for line in out(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], check=False).splitlines():
            f = _nm_fields(line)
            if len(f) >= 2 and f[1] == "802-11-wireless":
                sh(["nmcli", "connection", "delete", "id", f[0]], check=False)
    settings.write_env()
    threading.Timer(2, lambda: sh(["systemctl", "reboot"], check=False)).start()
    return {"reset": True}


# ------------------------------------------------------------------ first-boot setup
def _setup_file():
    return paths.state() / "state/setup.json"


@method("setup.state", write=False)
def setup_state() -> dict[str, Any]:
    try:
        return json.loads(_setup_file().read_text())
    except (OSError, ValueError):
        return {"done": False, "step": 0, "completed": []}


@method("setup.save")
def setup_save(step: int, completed: list[str] | None = None, done: bool = False) -> dict[str, Any]:
    st = {"done": bool(done), "step": int(step), "completed": completed or [], "time": time.time()}
    f = _setup_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(st) + "\n")
    if done:
        api_setup.hotspot_stop()
        events.publish("setup.done")
    return st


# ------------------------------------------------------------------ the rest lives in modules
from . import api_display, api_encryption, api_extra, api_remote, api_setup, api_updates, api_weather  # noqa: E402,F401
