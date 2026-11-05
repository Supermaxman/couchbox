"""What the box is doing right now, for Settings → System: processor and graphics load, the fan,
the processor's clock, and the apps using the processor most.

Loads are measured between two calls (couchboxd keeps the last sample), so the first call after
a start has none. Processes are grouped by the systemd unit they run in, as couchbox-memory does:
each app the home screen starts has its own (app-couchbox\\x2dtwitch@<id>.service).
"""

import os
import re
import time
from pathlib import Path
from typing import Any

from couchbox import paths

# units that aren't one app, shown by what they do
UNIT_NAMES = {
    "plasma-kwin_wayland.service": "Screen (KWin)",
    "plasma-plasmashell.service": "Home screen",
    "couchbox-frigate-popup.service": "Camera pop-up",
    "couchbox-spotify-connect.service": "Spotify",
    "pipewire.service": "Sound",
    "couchbox-voice-overlay.service": "Voice indicator",
}
HZ = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100

_last: dict[str, Any] = {}


def _p(path: str) -> Path:
    return paths.root() / path.lstrip("/")


def _read(path: str, default: str = "") -> str:
    try:
        return _p(path).read_text().strip()
    except OSError:
        return default


def unit_name(unit: str) -> str:
    """app-couchbox\\x2dtwitch@ab12.service -> Twitch; app-flatpak-rocks.shy.VacuumTube-12.scope ->
    VacuumTube; known services by what they do; others by their name."""
    if unit in UNIT_NAMES:
        return UNIT_NAMES[unit]
    if unit.startswith("session-") and unit.endswith(".scope"):
        return "Logins"  # someone signed in over SSH, or the TV's own session leader
    name = unit
    if unit.startswith("app-"):
        name = unit[4:].split("@", 1)[0]
        if name.endswith(".scope"):
            name = name.removesuffix(".scope").removeprefix("flatpak-").rsplit("-", 1)[0]
        name = re.sub(r"\\x([0-9a-f]{2})", lambda m: chr(int(m.group(1), 16)), name)
    name = name.removesuffix(".service").removeprefix("couchbox-").rsplit(".", 1)[-1]
    return {"VacuumTube": "YouTube", "JellyfinDesktop": "Jellyfin"}.get(name, name[:1].upper() + name[1:])


def _cpu_total() -> tuple[int, int]:
    """(busy, total) jiffies of all processors."""
    f = [int(x) for x in _read("/proc/stat").splitlines()[0].split()[1:]]
    idle = f[3] + (f[4] if len(f) > 4 else 0)
    return sum(f) - idle, sum(f)


def _gpu_ns() -> int:
    """Nanoseconds the graphics chip has spent rendering (the Pi 5's V3D: gpu_stats' render queue)."""
    for card in sorted(_p("/sys/class/drm").glob("card*/device/gpu_stats")):
        for line in card.read_text().splitlines():
            parts = line.split()
            if parts and parts[0] == "render":
                return int(parts[3])
    return -1


def _per_unit() -> dict[str, int]:
    """{unit: jiffies used} over every process."""
    out: dict[str, int] = {}
    for d in _p("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            st = (d / "stat").read_text()
            cg = (d / "cgroup").read_text().strip().rsplit("/", 1)[-1]
        except OSError:
            continue
        f = st[st.rindex(")") + 2 :].split()
        out[cg] = out.get(cg, 0) + int(f[11]) + int(f[12])
    return out


def _fan() -> dict[str, Any]:
    """The Pi's fan: its step (0 off .. 4 full) and speed."""
    for d in sorted(_p("/sys/class/thermal").glob("cooling_device*")):
        try:
            if (d / "type").read_text().strip() != "pwm-fan":
                continue
            rpm = next((int(x.read_text()) for x in _p("/sys/devices/platform/cooling_fan").glob("hwmon/*/fan1_input")), None)
            return {"step": int((d / "cur_state").read_text()), "steps": int((d / "max_state").read_text()), "rpm": rpm}
        except (OSError, ValueError):
            continue
    return {}


def sample() -> dict[str, Any]:
    """Load since the previous sample (none on the first), and the fan and clock now."""
    now = time.monotonic()
    cur = {"t": now, "cpu": _cpu_total(), "gpu": _gpu_ns(), "units": _per_unit()}
    out: dict[str, Any] = {"fan": _fan()}
    mhz = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
    out["cpu_mhz"] = int(mhz) // 1000 if mhz.isdigit() else None
    prev = _last.get("s")
    if prev and now - prev["t"] > 0.2:
        busy, total = cur["cpu"][0] - prev["cpu"][0], cur["cpu"][1] - prev["cpu"][1]
        out["cpu_pct"] = round(100 * busy / total) if total > 0 else None
        if cur["gpu"] >= 0 and prev["gpu"] >= 0:
            out["gpu_pct"] = min(100, round((cur["gpu"] - prev["gpu"]) / ((now - prev["t"]) * 1e9) * 100))
        cores = os.cpu_count() or 1
        used = {u: j - prev["units"].get(u, 0) for u, j in cur["units"].items()}
        top = sorted(((j, u) for u, j in used.items() if j > 0), reverse=True)[:4]
        # % of the whole processor (all cores), as in the Processor row
        out["apps"] = [{"name": unit_name(u), "pct": round(100 * j / HZ / (now - prev["t"]) / cores)} for j, u in top]
    _last["s"] = cur
    return out
