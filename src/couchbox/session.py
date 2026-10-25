"""The TV session, seen from root services: its user, D-Bus, and what's playing (MPRIS)."""

import os
import pwd
import re
import subprocess
import time

from couchbox import paths

TV_USER = "tv"
LAST_KEY = "last-key"  # /run/couchbox/last-key: touched by couchbox-input on every press


def tv_env() -> tuple[pwd.struct_passwd, dict[str, str]]:
    pw = pwd.getpwnam(TV_USER)
    run = f"/run/user/{pw.pw_uid}"
    env = {
        "HOME": pw.pw_dir,
        "XDG_RUNTIME_DIR": run,
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={run}/bus",
        "WAYLAND_DISPLAY": "wayland-0",
        "USER": pw.pw_name,
    }
    return pw, env


def _gdbus(*args: str, timeout: int = 2) -> subprocess.CompletedProcess:
    pw, env = tv_env()
    cmd = ["gdbus", "call", "--session", "--timeout", str(timeout), *args]
    if os.geteuid() == 0:
        cmd = ["runuser", "-u", pw.pw_name, "--", "env", f"DBUS_SESSION_BUS_ADDRESS={env['DBUS_SESSION_BUS_ADDRESS']}", *cmd]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 3)


def players() -> list[str]:
    try:
        r = _gdbus("--dest", "org.freedesktop.DBus", "--object-path", "/org/freedesktop/DBus", "--method", "org.freedesktop.DBus.ListNames")
    except (KeyError, OSError, subprocess.TimeoutExpired):
        return []
    return [n for n in re.findall(r"'(org\.mpris\.MediaPlayer2\.[^']+)'", r.stdout) if "kdeconnect" not in n.lower()]


def playback_status(name: str) -> str:
    try:
        r = _gdbus(
            "--dest",
            name,
            "--object-path",
            "/org/mpris/MediaPlayer2",
            "--method",
            "org.freedesktop.DBus.Properties.Get",
            "org.mpris.MediaPlayer2.Player",
            "PlaybackStatus",
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    m = re.search(r"'(Playing|Paused|Stopped)'", r.stdout)
    return m.group(1) if m else ""


def anything_playing() -> bool:
    if any(playback_status(p) == "Playing" for p in players()):
        return True
    # apps without MPRIS (web pages): couchbox-memory's last look
    try:
        import json

        st = json.loads((paths.run() / "memory/state.json").read_text())
        if time.time() - st.get("t", 0) < 120 and any(a.get("playing") for a in st.get("apps", {}).values()):
            return True
    except (OSError, ValueError):
        pass
    return False


def pause_all() -> list[str]:
    paused = []
    for name in players():
        r = _gdbus("--dest", name, "--object-path", "/org/mpris/MediaPlayer2", "--method", "org.mpris.MediaPlayer2.Player.Pause")
        if r.returncode == 0:
            paused.append(name.split(".", 3)[-1])
    return paused


def seconds_since_input() -> float:
    try:
        return time.time() - (paths.run() / LAST_KEY).stat().st_mtime
    except OSError:
        try:
            with open("/proc/uptime") as f:
                return float(f.read().split()[0])
        except OSError:
            return 1e9
