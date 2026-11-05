"""Playback settings for every player on the box (Settings → Display and sound): our own
(player.py: libmpv in the Twitch, Nebula, Dropout and Frigate apps) and Jellyfin Desktop's mpv,
which couchbox-jellyfin configures at start and couchbox-playback follows while it runs.

- video.match_rate: while a film plays, the TV's refresh rate matches its frame rate (23.976 fps
  at 23.98 Hz, 25 at 50, 29.97 at 59.94), so every frame is on screen for the same time instead of
  the 3:2 judder of 24 fps on 60 Hz. Follower decides from mpv's properties; set_rate switches with
  kscreen-doctor, and puts back Settings → Resolution (display.mode) once playback has stopped.
- audio.night_mode: night_filter(), an mpv audio filter that evens out loud and quiet.
- audio.passthrough: Dolby Digital (Plus) and DTS sent to the TV undecoded (mpv's audio-spdif),
  for the codecs the TV lists in its ELD (tv_codecs); couchbox-audio lets the HDMI sink take them.

    from couchbox import playback
    playback.night_filter(True)                 -> "@couchbox-night:lavfi=[acompressor=...]"
    playback.pick_mode(23.976, output)          -> Mode("3", 1920, 1080, 23.98)
    playback.set_rate(23.976) / set_rate(None)  switch the TV / put Settings' mode back

  couchbox-playback status | match FPS | restore | codecs | watch PID [--mpv SOCKET]
"""

import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from couchbox import paths, system

# The settings players follow while they run (player.py, couchbox-playback watch), with their
# defaults should the settings not be readable.
LIVE = {"video.drawing": "fast", "video.match_rate": True, "audio.night_mode": False, "audio.passthrough": "off"}


def live_settings() -> dict[str, Any]:
    try:
        from couchbox import settings

        s = settings.load()
        return {k: s.get(k, v) for k, v in LIVE.items()}
    except Exception:  # noqa: BLE001
        return dict(LIVE)


def watch_settings(changed: Callable[[dict[str, Any]], None]) -> None:
    """Call changed({key: value}) whenever a LIVE setting changes, for as long as the process runs
    (in a thread of its own; while couchboxd restarts, it tries again)."""
    from couchbox import ipc

    while True:
        try:
            for ev in ipc.subscribe(["settings"]):
                data = {k: v for k, v in (ev.get("data") or {}).items() if k in LIVE}
                if data:
                    changed(data)
        except Exception:  # noqa: BLE001  (daemon restarting): try again
            pass
        time.sleep(10)


def _log(msg: str) -> None:
    print(f"couchbox-playback: {msg}", file=sys.stderr, flush=True)


# ------------------------------------------------------------------ night mode

# Night mode: a compressor and a limiter, so explosions and music don't wake the house while
# speech stays easy to follow. Measured on a sine with ffmpeg 9 (RMS in -> out):
# -3 dB -> -16, -13 -> -18, -23 -> -21, -33 -> -25, -43 -> -35: 40 dB of range becomes ~19.
# - acompressor: above -28 dBFS (RMS; film dialogue sits around -30 to -20) the level rises a
#   quarter as fast (ratio 4). 5 ms attack catches gunshots, 300 ms release doesn't "pump"
#   between words. 8 dB make-up gain brings quiet speech up.
# - alimiter at -1 dBFS: the make-up gain must never clip on a transient the compressor's attack
#   let through. level=0: no auto-levelling (ffmpeg's default would boost everything to the limit).
# Cheap: 5.1 at 48 kHz runs ~570x real time on one desktop core (estimated ~1 % of a Pi 5 core),
# so it fits beside software H.264.
NIGHT_LABEL = "couchbox-night"
NIGHT_GRAPH = "acompressor=threshold=-28dB:ratio=4:attack=5:release=300:makeup=8dB,alimiter=limit=-1dB:level=0"


def night_filter(on: bool) -> str:
    """mpv's af value: the night filter (labelled, in lavfi's brackets), or none."""
    return f"@{NIGHT_LABEL}:lavfi=[{NIGHT_GRAPH}]" if on else ""


# ------------------------------------------------------------------ passthrough

# Codecs sent to the TV as IEC 61937 bitstreams, in mpv's names. All three fit in 2-channel
# HDMI audio (E-AC-3 at 192 kHz). TrueHD and DTS-HD MA need 8-channel "HBR" audio, which the
# 2-channel HDMI sink can't carry: their DTS core / AC-3 compatibility track still plays.
PASSTHROUGH = ("ac3", "eac3", "dts")
PIPEWIRE_CODECS = {"ac3": "AC3", "eac3": "EAC3", "dts": "DTS"}
# CEA-861 audio coding types in the ELD's short audio descriptors (DTS-HD sinks decode DTS too)
_ELD_TYPES = {2: "ac3", 10: "eac3", 7: "dts", 11: "dts"}


def eld_codecs(text: str) -> list[str]:
    """The passthrough codecs an ELD (/proc/asound/cardN/eld#M) lists, in PASSTHROUGH order."""
    found = {_ELD_TYPES.get(int(m, 16)) for m in re.findall(r"^sad\d+_coding_type\s+\[0x([0-9a-fA-F]+)\]", text, re.M)}
    return [c for c in PASSTHROUGH if c in found]


def tv_codecs(card: str | None = None) -> list[str]:
    """The codecs the TV on HDMI says it decodes (none when no screen is on). card: only that
    ALSA card index (couchbox-audio's)."""
    for f in sorted((paths.root() / "proc/asound").glob(f"card{card if card is not None else '*'}/eld#*")):
        try:
            text = f.read_text()
        except OSError:
            continue
        if re.search(r"^monitor_name\s+\S", text, re.M):
            return eld_codecs(text)
    return []


def spdif(passthrough: str, night: bool, codecs: list[str]) -> str:
    """mpv's audio-spdif value. Night mode decodes everything: its filter can't work on a bitstream."""
    return ",".join(codecs) if passthrough == "on" and not night else ""


def jellyfin_conf(s: dict[str, Any] | None = None, codecs: list[str] | None = None) -> dict[str, Any]:
    """What couchbox-jellyfin puts in Jellyfin Desktop's settings at start: the night filter
    (an "af=" line of its mpv options) and the passthrough codecs (its HDMI device type)."""
    s = s or live_settings()
    on = s["audio.passthrough"] == "on" and not s["audio.night_mode"]
    codecs = (tv_codecs() if codecs is None else codecs) if on else []
    return {"af": night_filter(bool(s["audio.night_mode"])), "passthrough": [c for c in codecs if c in PASSTHROUGH]}


# ------------------------------------------------------------------ the TV's modes


@dataclass(frozen=True)
class Mode:
    id: str
    width: int
    height: int
    rate: float

    def __str__(self) -> str:
        return f"{self.width}x{self.height}@{self.rate:g}"


@dataclass
class Output:
    name: str
    enabled: bool = False
    connected: bool = False
    modes: list[Mode] = field(default_factory=list)
    current: str | None = None

    def mode(self, mode_id: str | None) -> Mode | None:
        return next((m for m in self.modes if m.id == mode_id), None)


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def parse_outputs(text: str) -> list[Output]:
    """kscreen-doctor -o: each output, its modes ("3:1920x1080@23.98", "*" the current one)."""
    outs = []
    for block in re.split(r"^Output:", _ANSI.sub("", text), flags=re.M)[1:]:
        words = block.split()
        if len(words) < 2:
            continue
        o = Output(words[1], enabled=bool(re.search(r"\benabled\b", block)), connected=bool(re.search(r"\bconnected\b", block)))
        for mid, w, h, rate, star in re.findall(r"(?<!\S)([\w-]+):(\d+)x(\d+)@(\d+(?:\.\d+)?)(\*?)", block):
            o.modes.append(Mode(mid, int(w), int(h), float(rate)))
            if star:
                o.current = mid
        outs.append(o)
    return outs


# How close a refresh rate must be to the frame rate (or twice it). kscreen-doctor shows two
# decimals: 23.98 for 23.976 and 59.94 for 59.94006 are "exact"; 24.00 for 23.976 is "close"
# (a frame repeated every 42 s), used only when the TV has no 23.98.
EXACT = 0.0005
CLOSE = 0.002


def pick_mode(fps: float, output: Output) -> Mode | None:
    """The mode, at the current resolution, whose refresh rate is the video's frame rate or twice
    it (25 fps at 50 Hz, 29.97 at 59.94): exact before close, then the higher rate (smoother menus
    and subtitles, and TVs flicker less). None: no rate fits (48 fps, ...), or under 23 fps
    (12 or 15 fps already divide 60 Hz evenly)."""
    cur = output.mode(output.current)
    if not cur or fps < 23:
        return None
    best = None
    for m in output.modes:
        if (m.width, m.height) != (cur.width, cur.height) or m.rate < 23:
            continue
        for k in (1, 2):
            err = abs(m.rate - k * fps) / (k * fps)
            if err <= CLOSE:
                key = (err > EXACT, round(err, 4) if err > EXACT else 0, -m.rate)
                if best is None or key < best[0]:
                    best = (key, m)
    return best[1] if best else None


def spec_mode(output: Output, spec: str) -> Mode | None:
    """Settings → Resolution ("1920x1080@60") among the output's modes: that size at the nearest
    rate (60.00 rather than 59.94)."""
    m = re.fullmatch(r"(\d+)x(\d+)@(\d+(?:\.\d+)?)", spec or "")
    if not m:
        return None
    w, h, rate = int(m[1]), int(m[2]), float(m[3])
    same = [x for x in output.modes if (x.width, x.height) == (w, h)]
    return min(same, key=lambda x: abs(x.rate - rate)) if same else None


def _display_settings() -> tuple[str, list[str]]:
    try:
        from couchbox import settings

        s = settings.load()
        return s["display.mode"], list(s["display.outputs"])
    except Exception:  # noqa: BLE001
        return "1920x1080@60", ["HDMI-A-1", "HDMI-A-2"]


def outputs() -> list[Output]:
    return parse_outputs(system.sh(["kscreen-doctor", "-o"], check=False, timeout=15).stdout or "")


def set_rate(fps: float | None) -> list[str]:
    """Put each TV output in the mode for a fps video (None: Settings → Resolution), with
    kscreen-doctor, in the TV session. An output already there isn't touched (a switch blanks
    the TV for a second or two). Returns the outputs left away from Settings' mode."""
    spec, names = _display_settings()
    away = []
    for o in outputs():
        if not (o.enabled and o.connected and o.name in names):
            continue
        home = spec_mode(o, spec)
        target = (pick_mode(fps, o) if fps else None) or home
        if not target:
            continue
        if target.id != o.current:
            r = system.sh(["kscreen-doctor", f"output.{o.name}.mode.{target.id}"], check=False, timeout=15)
            why = f"for {fps:.3f} fps" if fps else "Settings' mode"
            _log(f"{o.name}: {o.mode(o.current)} -> {target} {why}" + ("" if r.returncode == 0 else " (failed)"))
        if home is None or target.id != home.id:
            away.append(o.name)
    return away


# Who switched the TV away from Settings' mode: {"pid": the app, "who": its player}. Only the
# owner puts it back, so a player that never switched (a camera pop-up over a film) leaves it.
def _owner_file() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "couchbox-rate.json"


def owner() -> dict[str, Any] | None:
    try:
        return json.loads(_owner_file().read_text())
    except (OSError, ValueError):
        return None


def claim(pid: int, who: str, fps: float) -> None:
    f = _owner_file()
    tmp = f.with_name(f".{f.name}.{os.getpid()}")
    with contextlib.suppress(OSError):
        tmp.write_text(json.dumps({"pid": pid, "who": who, "fps": fps}))
        os.replace(tmp, f)


def release() -> None:
    _owner_file().unlink(missing_ok=True)


def restore() -> None:
    """Back to Settings' mode, whoever switched."""
    set_rate(None)
    release()


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


_guarded: set[int] = set()


def start_guard(pid: int) -> None:
    """A small process that puts Settings' mode back when the app quits without doing it itself
    (closed for memory with SIGTERM, crashed). Once per app."""
    if pid in _guarded:
        return
    _guarded.add(pid)
    try:
        subprocess.Popen(
            [sys.executable, "-m", "couchbox.playback", "watch", str(pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as e:
        _log(f"no guard: {e}")


# ------------------------------------------------------------------ following a player

# mpv's properties a Follower looks at, by its names for them
PROPS = {
    "path": "path",
    "idle": "idle-active",
    "eof": "eof-reached",
    "paused": "pause",
    "duration": "duration",
    "container_fps": "container-fps",
    "est_fps": "estimated-vf-fps",
}


def snapshot(get: Callable[[str], Any]) -> dict[str, Any]:
    """The PROPS from a player, through get(mpv property) (None when unavailable)."""
    out = {}
    for k, prop in PROPS.items():
        try:
            out[k] = get(prop)
        except Exception:  # noqa: BLE001
            out[k] = None
    return out


STABLE_SAMPLES = 3  # this many readings of the measured frame rate, a second apart, that agree
STABLE_SPREAD = 0.005  # ... to within 0.5 %
GIVE_UP = 30.0  # no steady frame rate by then (variable frame rate, audio only): leave the TV be
MIN_DURATION = 300.0  # shorter (trailers, clips, recordings of an event): not worth two blank screens
RESTORE_AFTER = 10.0  # stopped this long: Settings' mode again (the next episode starts sooner)


class Follower:
    """Decides, from a player's properties sampled about once a second (step), which refresh rate
    its video wants, and switches the TV when that changes.

    A new file is watched until the measured frame rate (estimated-vf-fps) holds steady for a few
    seconds; then, for a video (not live, not a short clip), the TV switches once to the matching
    mode and stays there until playback has stopped for RESTORE_AFTER, so going to the next
    episode doesn't switch twice. Live streams and clips put Settings' mode back only if this
    player switched, or, when they aren't passive (a camera pop-up is), if another player left the
    TV switched (its film paused, then Twitch opened). The switching itself (switch: set_rate) is
    done here, on the caller's thread."""

    def __init__(self, pid: int | None = None, who: str = "", switch=None, clock=time.monotonic, on_claim=None):
        self.pid = pid or os.getpid()
        self.who = who
        self.switch = switch or (lambda fps: set_rate(fps))
        self.clock = clock
        self.on_claim = on_claim
        self.enabled = True
        self.switched: float | None = None  # the frame rate this player switched the TV for
        self.path = None
        self.samples: list[float] = []
        self.started = 0.0
        self.decided = False
        self.paused = False
        self.stopped_at: float | None = None
        self.lock = threading.Lock()

    def _mine(self) -> bool:
        o = owner()
        return bool(o) and o.get("pid") == self.pid and o.get("who") == self.who

    def _switch(self, fps: float) -> None:
        if self.switch(fps):
            claim(self.pid, self.who, fps)
            self.switched = fps
            if self.on_claim:
                self.on_claim(self.pid)
        else:  # Settings' mode suits it (30 or 60 fps)
            self._home(passive=False)

    def _home(self, passive: bool) -> None:
        if self.switched is not None:
            if self._mine() or owner() is None:
                self.switch(None)
                release()
            self.switched = None
        elif not passive and owner():
            self.switch(None)
            release()

    def close(self) -> None:
        """The player is going away: Settings' mode again if it switched."""
        with self.lock:
            if self.switched is not None and self._mine():
                self.switch(None)
                release()
            self.switched = None

    def set_enabled(self, on: bool) -> None:
        with self.lock:
            self.enabled = on
            if not on:
                self._home(passive=True)
            self.path = None  # the video playing now is looked at afresh

    def step(self, p: dict[str, Any], passive: bool = False) -> None:
        with self.lock:
            self._step(p, passive)

    def _step(self, p: dict[str, Any], passive: bool) -> None:
        now = self.clock()
        if not self.enabled:
            return
        if p.get("idle") or not p.get("path") or p.get("eof"):
            if self.stopped_at is None:
                self.stopped_at = now
            if now - self.stopped_at >= RESTORE_AFTER:
                self._home(passive=True)
            self.path = None  # whatever plays next is looked at afresh (even the same file)
            return
        self.stopped_at = None
        if p["path"] != self.path:
            self.path, self.samples, self.started, self.decided = p["path"], [], now, False
        paused = bool(p.get("paused"))
        resumed, self.paused = self.paused and not paused, paused
        if self.decided:
            # resumed after another video took the TV over (a paused film, then Twitch): take it back
            if resumed and self.switched is not None and not self._mine():
                self._switch(self.switched)
            return
        fps = self._decide(p, now)
        if fps is False:
            return
        self.decided = True
        if fps:
            _log(f"{self.who or 'player'}: {fps:.3f} fps video")
            self._switch(fps)
        else:
            self._home(passive)

    def _decide(self, p: dict[str, Any], now: float) -> float | None | bool:
        """The frame rate to match, None (Settings' mode), or False: not sure yet."""
        est = p.get("est_fps")
        if isinstance(est, int | float) and est > 0:
            self.samples = (self.samples + [float(est)])[-STABLE_SAMPLES:]
        if now - self.started > GIVE_UP:
            return None
        if len(self.samples) < STABLE_SAMPLES or (max(self.samples) - min(self.samples)) > STABLE_SPREAD * max(self.samples):
            return False
        dur = p.get("duration")
        if not isinstance(dur, int | float) or dur <= 0 or dur < MIN_DURATION:
            return None  # live (no duration) or a clip
        measured = sorted(self.samples)[len(self.samples) // 2]
        cont = p.get("container_fps")
        # the container's rate is exact (23.976...) when it agrees with what's measured; some
        # streams carry a wrong one (90000, 0)
        if isinstance(cont, int | float) and cont > 0 and abs(cont - measured) <= 0.01 * measured:
            return float(cont)
        return measured


# ------------------------------------------------------------------ players that aren't ours


class MpvSocket:
    """mpv's JSON IPC (input-ipc-server): Jellyfin Desktop's player, from outside."""

    def __init__(self, path: str, timeout: float = 5):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect(path)
        except OSError:
            self.sock.close()
            raise
        self.f = self.sock.makefile("rwb")
        self.n = 0
        self.broken = False

    def command(self, *args: Any) -> Any:
        try:
            self.n += 1
            self.f.write((json.dumps({"command": list(args), "request_id": self.n}) + "\n").encode())
            self.f.flush()
            while True:
                line = self.f.readline()
                if not line:
                    raise OSError("mpv went away")
                r = json.loads(line)
                if r.get("request_id") == self.n:
                    return r.get("data") if r.get("error") == "success" else None
        except (OSError, ValueError):
            self.broken = True  # (snapshot() reads a failed property as None)
            raise

    def get(self, prop: str) -> Any:
        return self.command("get_property", prop)

    def close(self) -> None:
        with contextlib.suppress(OSError, ValueError):
            self.f.close()
            self.sock.close()


def watch(pid: int, mpv_socket: str | None = None, who: str = "jellyfin") -> None:
    """Until process pid exits: with mpv_socket, follow that player like ours (refresh rate, live
    night mode); then put Settings' mode back if it was the one that switched."""
    live = live_settings()
    fol = Follower(pid=pid, who=who)
    fol.enabled = bool(live["video.match_rate"])
    conn: list[MpvSocket | None] = [None]
    launch_af = night_filter(bool(live["audio.night_mode"]))  # what couchbox-jellyfin gave it at start
    lock = threading.Lock()

    def send_af() -> None:
        with lock:
            if conn[0]:
                with contextlib.suppress(OSError, ValueError):
                    conn[0].command("set_property", "af", night_filter(bool(live["audio.night_mode"])))

    def changed(data: dict[str, Any]) -> None:
        live.update(data)
        if "video.match_rate" in data:
            fol.set_enabled(bool(data["video.match_rate"]))
        if "audio.night_mode" in data:
            send_af()

    if mpv_socket:
        threading.Thread(target=watch_settings, args=(changed,), daemon=True).start()
    path = None
    while alive(pid):
        time.sleep(1)
        if not mpv_socket:
            continue
        try:
            with lock:
                if conn[0] is None:
                    conn[0] = MpvSocket(mpv_socket)
                snap = snapshot(conn[0].get)
                if conn[0].broken:
                    raise OSError("mpv went away")
        except (OSError, ValueError):
            with lock:
                if conn[0]:
                    conn[0].close()
                conn[0] = None
            continue
        if snap.get("path") and snap["path"] != path and night_filter(bool(live["audio.night_mode"])) != launch_af:
            # Jellyfin puts its start-up options (af= included) back whenever its own settings
            # change: a night mode changed since then is sent again with each new video
            send_af()
        path = snap.get("path")
        fol.step(snap)
    o = owner()
    if o and o.get("pid") == pid:
        _log(f"{who or pid} quit: back to Settings' mode")
        restore()


# ------------------------------------------------------------------ couchbox-playback


def _as_tv_user(argv: list[str]) -> None:
    """kscreen-doctor needs the TV session: as root, run again as the TV user (like couchbox-display)."""
    if os.geteuid() != 0:
        return
    import pwd

    user = os.environ.get("COUCHBOX_TV_USER", "tv")
    uid = pwd.getpwnam(user).pw_uid
    env = [f"XDG_RUNTIME_DIR=/run/user/{uid}", "WAYLAND_DISPLAY=wayland-0", f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus"]
    os.execvp("runuser", ["runuser", "-u", user, "--", "env", *env, sys.executable, "-m", "couchbox.playback", *argv])  # noqa: S606


def _status() -> None:
    spec, names = _display_settings()
    print(f"Settings: {spec} on {' '.join(names)}; owner: {owner() or 'none (Settings mode)'}")
    for o in outputs():
        state = ("enabled" if o.enabled else "disabled") + (", connected" if o.connected else ", disconnected")
        print(f"{o.name}: {state}, now {o.mode(o.current)}")
        if o.enabled and o.connected:
            print("  modes here: " + " ".join(str(m) for m in o.modes if o.mode(o.current) and m.width == o.mode(o.current).width))
            for fps in (23.976, 24, 25, 29.97, 30, 50, 59.94, 60):
                print(f"  {fps:>6} fps -> {pick_mode(fps, o) or spec_mode(o, spec)}")
    print("passthrough codecs the TV lists: " + (" ".join(tv_codecs()) or "none"))


USAGE = """usage: couchbox-playback [status]        the TV's modes, and the one each frame rate gets
       couchbox-playback match FPS       switch the TV as a FPS video would (e.g. 23.976)
       couchbox-playback restore         back to Settings -> Resolution
       couchbox-playback codecs [--pipewire] [--card N]   passthrough codecs the TV lists
       couchbox-playback jellyfin-conf   (couchbox-jellyfin) night filter and passthrough, as JSON
       couchbox-playback watch PID [--mpv SOCKET]   follow a player until PID exits"""


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "status"
    if cmd in ("status", "match", "restore"):
        _as_tv_user(argv or ["status"])
    if cmd == "status":
        _status()
    elif cmd == "match" and len(argv) == 2:
        fps = float(argv[1])
        if set_rate(fps):
            claim(os.getpid(), "couchbox-playback", fps)
        else:
            release()
    elif cmd == "restore":
        restore()
    elif cmd == "codecs":
        card = argv[argv.index("--card") + 1] if "--card" in argv else None
        codecs = tv_codecs(card)
        print(" ".join(PIPEWIRE_CODECS[c] for c in codecs) if "--pipewire" in argv else " ".join(codecs))
    elif cmd == "jellyfin-conf":
        print(json.dumps(jellyfin_conf()))
    elif cmd == "watch" and len(argv) >= 2:
        watch(int(argv[1]), argv[argv.index("--mpv") + 1] if "--mpv" in argv else None)
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
