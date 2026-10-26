"""The remote's media keys (Play/Pause, Rewind, Fast-forward, Next, Previous) for whatever is
actually playing, wherever you are on the TV.

couchbox-input (root) sends each press here (`couchbox-mediakeys`, the TV user's service) over
the appctl socket "mediakeys"; this picks a player and calls it over MPRIS. Before, the keys went
to Plasma's media controller, which picks "the player that's playing" from what players claim,
and YouTube's TV page keeps claiming "Playing" after its video has been paused behind its back:
Play/Pause then went to a paused YouTube instead of the Spotify that was playing.

Which player:
  1. The app in front, if it has something loaded (playing or paused): it gets the key, as
     before. The window and a player belong together when they're in the same systemd scope
     (app-*.scope / *.service), or the player's DesktopEntry is the window's app id (the
     Spotify app's window and the Spotify player service, couchbox-spotify).
  2. Else what's playing (the most recently started, if several).
  3. Else the most recently paused.
Nothing loaded anywhere: the key goes on to the app in front as a key press.

A Chromium player that says "Playing" with a rate of 0 is paused (its page set the media
session to playing; Chromium's rate follows the media element). Play/Pause sends Play or Pause,
never PlayPause, so a player with a stale state still does what the remote asked.

    {"op": "key", "action": "playpause"}  -> {"player": ..., "did": "Pause", "why": ...}
          actions: playpause, play, pause, stop, next, previous, rewind, forward
    {"op": "state"}                       -> the players and the window in front
"""

import json
import logging
import os
import tempfile
import threading
import time

log = logging.getLogger("couchbox.mediakeys")

SITE = "mediakeys"  # appctl socket: $XDG_RUNTIME_DIR/couchbox/app-mediakeys.sock
ACTIONS = ("playpause", "play", "pause", "stop", "next", "previous", "rewind", "forward")
SEEK_SECONDS = 10  # Rewind / Fast-forward step (the remote's own apps use 10 s)
MPRIS = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"
IFACE = "org.couchbox.MediaKeys"
SCRIPT_NAME = "couchbox-mediakeys"
# A KWin script that tells us whenever the window in front changes (so a key press doesn't
# have to ask KWin, which takes a moment)
KWIN_JS = """
function report(w) {
  callDBus("%s", "/", "%s", "Active", JSON.stringify(w ? {
    class: w.resourceClass, app: w.desktopFileName, pid: w.pid,
    shell: !!(w.desktopWindow || w.dock || w.resourceClass === "plasmashell")} : {}));
}
workspace.windowActivated.connect(report);
report(workspace.activeWindow);
"""


# ------------------------------------------------------------------ choosing (no D-Bus here)
def effective(p):
    """("Playing" | "Paused" | "Stopped", stale): the player's state, believing a rate of 0
    over a "Playing" (Chromium, when a page's media session says playing over a paused video)."""
    status = p.get("status") or "Stopped"
    if status == "Playing" and p.get("rate") == 0:
        return "Paused", True
    return status, False


def unit_of(cgroup):
    """The systemd unit a process runs in (its app scope or service), from /proc/PID/cgroup's
    line; "" for a login session or the user manager itself (shared by unrelated things)."""
    last = (cgroup or "").strip().rsplit("/", 1)[-1]
    if last.endswith(".scope") and last.startswith("app-") or last.endswith(".service") and not last.startswith("user@"):
        return last
    return ""


def belongs(p, window):
    """Whether the player p is the window's (same app scope or service, or same app id)."""
    if not window or window.get("shell"):
        return False
    unit = window.get("unit") or ""
    if unit and unit == p.get("unit"):
        return True
    app = (window.get("app") or "").lower().removesuffix(".desktop")
    desk = (p.get("desktop") or "").lower().removesuffix(".desktop")
    return bool(app and desk and app == desk)


def choose(players, window):
    """(player or None, why) for a media key: the app in front's, else the one playing, else the
    one paused last. players: [{name, status, rate, unit, desktop, changed}], window: {app, unit,
    shell}."""
    live = []
    for p in players:
        st, stale = effective(p)
        if st in ("Playing", "Paused"):
            live.append((p, st, stale))
    if not live:
        return None, "nothing is playing or paused"

    def recent(item):
        p, st, stale = item
        return (st == "Playing", p.get("changed") or 0, not stale)

    mine = [x for x in live if belongs(x[0], window)]
    if mine:
        return max(mine, key=recent)[0], "the app in front"
    playing = [x for x in live if x[1] == "Playing"]
    if playing:
        return max(playing, key=recent)[0], "playing in the background"
    return max(live, key=recent)[0], "paused last"


def method_for(action, p):
    """(MPRIS method, args) for an action on player p."""
    st, _ = effective(p)
    if action == "playpause":
        return ("Pause", ()) if st == "Playing" else ("Play", ())
    if action in ("pause", "stop"):
        return "Pause", ()
    if action == "play":
        return "Play", ()
    if action == "next":
        return "Next", ()
    if action == "previous":
        return "Previous", ()
    if action in ("rewind", "forward"):
        return "Seek", ((-1 if action == "rewind" else 1) * SEEK_SECONDS * 1_000_000,)
    raise ValueError(f"unknown action {action!r}")


def label(p):
    return p.get("identity") or p.get("name", "").removeprefix(MPRIS + ".")


# ------------------------------------------------------------------ the service (TV user)
class Service:
    """Keeps track of the MPRIS players and the window in front; answers couchbox-input."""

    def __init__(self):
        import dbus
        import dbus.mainloop.glib
        import dbus.service

        self.dbus = dbus
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        self.lock = threading.Lock()
        self.players = {}  # well-known name -> {name, owner, status, rate, unit, desktop, identity, changed}
        self.window = {}
        self.window_at = 0.0
        svc = self

        class Reporter(dbus.service.Object):
            @dbus.service.method(IFACE, in_signature="s")
            def Active(self, js):
                svc.set_window(js)

        self._name = dbus.service.BusName(IFACE, self.bus)
        self._reporter = Reporter(self.bus, "/")
        self.bus.add_signal_receiver(
            self.owner_changed, "NameOwnerChanged", "org.freedesktop.DBus", "org.freedesktop.DBus", "/org/freedesktop/DBus"
        )
        self.bus.add_signal_receiver(
            self.props_changed, "PropertiesChanged", PROPS, None, "/org/mpris/MediaPlayer2", sender_keyword="sender"
        )
        dbus_obj = self.bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus")
        for name in dbus_obj.ListNames(dbus_interface="org.freedesktop.DBus"):
            if str(name).startswith(MPRIS + "."):
                self.add(str(name), changed=0.0)

    # -------------------------------------------------- players
    def add(self, name, changed=None):
        if "kdeconnect" in name.lower():  # phones' players: not the TV's
            return
        dbus = self.dbus
        try:
            owner = str(self.bus.get_name_owner(name))
            obj = self.bus.get_object(name, "/org/mpris/MediaPlayer2")
            props = obj.GetAll(PLAYER, dbus_interface=PROPS, timeout=2)
            root = obj.GetAll(MPRIS, dbus_interface=PROPS, timeout=2)
            pid = int(
                self.bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus").GetConnectionUnixProcessID(
                    name, dbus_interface="org.freedesktop.DBus"
                )
            )
        except (dbus.DBusException, ValueError) as err:
            log.info("can't read player %s: %s", name, err)
            return
        p = {
            "name": name,
            "owner": owner,
            "status": str(props.get("PlaybackStatus", "Stopped")),
            "rate": float(props.get("Rate", 1.0)),
            "identity": str(root.get("Identity", "")),
            "desktop": str(root.get("DesktopEntry", "")),
            "unit": unit_of(read_cgroup(pid)),
        }
        p["changed"] = time.time() if changed is None and effective(p)[0] == "Playing" else (changed or 0.0)
        with self.lock:
            self.players[name] = p
        log.info("player %s (%s, %s): %s", name, p["identity"], p["unit"] or p["desktop"], effective(p)[0])

    def owner_changed(self, name, old, new):
        name = str(name)
        if not name.startswith(MPRIS + "."):
            return
        with self.lock:
            self.players.pop(name, None)
        if new:
            self.add(name)

    def props_changed(self, iface, changed, _invalidated, sender=None):
        if str(iface) != PLAYER or not ({"PlaybackStatus", "Rate"} & {str(k) for k in changed}):
            return
        with self.lock:
            for p in self.players.values():
                if p["owner"] != sender:
                    continue
                before = effective(p)[0]
                if "PlaybackStatus" in changed:
                    p["status"] = str(changed["PlaybackStatus"])
                if "Rate" in changed:
                    p["rate"] = float(changed["Rate"])
                if effective(p)[0] != before:
                    p["changed"] = time.time()

    # -------------------------------------------------- the window in front
    def set_window(self, js):
        try:
            w = json.loads(str(js)) or {}
        except ValueError:
            return
        if w.get("pid"):
            w["unit"] = unit_of(read_cgroup(int(w["pid"])))
        with self.lock:
            self.window, self.window_at = w, time.time()

    def watch_windows(self, fresh=False):
        """Load the KWin script that reports the window in front (again if KWin lost it; with
        fresh, reload it so it reports the window in front now)."""
        dbus = self.dbus
        try:
            scripting = self.bus.get_object("org.kde.KWin", "/Scripting")
            if bool(scripting.isScriptLoaded(SCRIPT_NAME, dbus_interface="org.kde.kwin.Scripting")):
                if not fresh:
                    return True
                scripting.unloadScript(SCRIPT_NAME, dbus_interface="org.kde.kwin.Scripting")
            fd, path = tempfile.mkstemp(prefix="couchbox-mediakeys-", suffix=".js")
            os.write(fd, (KWIN_JS % (IFACE, IFACE)).encode())
            os.close(fd)
            try:
                # KWin overloads loadScript (s) and (ss); introspection alone picks the wrong one
                sid = scripting.loadScript(path, SCRIPT_NAME, signature="ss", dbus_interface="org.kde.kwin.Scripting")
                self.bus.get_object("org.kde.KWin", f"/Scripting/Script{int(sid)}").run(dbus_interface="org.kde.kwin.Script")
            finally:
                # KWin reads the file on load; it can go once the script runs
                threading.Timer(5, lambda: os.path.exists(path) and os.unlink(path)).start()
        except dbus.DBusException as err:
            log.warning("can't watch the window in front: %s", err)
        return True  # GLib timeout: keep checking

    def refresh(self):
        """Read each player's state again (a player may not signal every change, e.g. a rate)."""
        dbus = self.dbus
        for name in list(self.players):
            try:
                props = self.bus.get_object(name, "/org/mpris/MediaPlayer2").GetAll(PLAYER, dbus_interface=PROPS, timeout=0.25)
            except dbus.DBusException:
                continue
            with self.lock:
                p = self.players.get(name)
                if not p:
                    continue
                before = effective(p)[0]
                p["status"] = str(props.get("PlaybackStatus", p["status"]))
                p["rate"] = float(props.get("Rate", p["rate"]))
                if effective(p)[0] != before:
                    p["changed"] = time.time()

    # -------------------------------------------------- a key
    def key(self, action):
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        self.refresh()
        with self.lock:
            players = [dict(p) for p in self.players.values()]
            window = dict(self.window)
        p, why = choose(players, window)
        if not p:
            return {"player": None, "why": why}
        method, args = method_for(action, p)
        obj = self.bus.get_object(p["name"], "/org/mpris/MediaPlayer2")
        getattr(obj, method)(
            *args,
            dbus_interface=PLAYER,
            reply_handler=lambda *a: None,
            error_handler=lambda err: log.warning("%s %s: %s", p["name"], method, err),
        )
        return {"player": p["name"], "identity": label(p), "did": method, "why": why}

    def handle(self, req):
        op = req.get("op")
        if op == "ping":
            return {"ok": True, "site": SITE}
        if op == "key":
            return self.key(req.get("action", ""))
        if op == "state":
            with self.lock:
                return {"window": self.window, "players": [dict(p, effective=effective(p)[0]) for p in self.players.values()]}
        return {"error": f"unknown op {op!r}"}


def read_cgroup(pid):
    try:
        with open(f"/proc/{pid}/cgroup") as f:
            return f.read().strip().splitlines()[-1]
    except (OSError, IndexError):
        return ""


def serve():
    from gi.repository import GLib

    from couchbox import appctl

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    svc = Service()
    svc.watch_windows(fresh=True)
    GLib.timeout_add_seconds(60, svc.watch_windows)
    server = appctl.Server(SITE, lambda req: run_on_loop(svc.handle, req))
    server.start()
    log.info("ready: %d player(s)", len(svc.players))
    try:
        GLib.MainLoop().run()
    finally:
        server.close()


def run_on_loop(fn, req, timeout=5):
    """Run fn(req) on the GLib loop's thread (D-Bus calls stay on one thread) and return its result."""
    from gi.repository import GLib

    done = threading.Event()
    out = {}

    def call():
        try:
            out["r"] = fn(req)
        except Exception as err:  # noqa: BLE001 - the caller gets the reason
            out["r"] = {"error": str(err) or err.__class__.__name__}
        done.set()
        return False

    GLib.idle_add(call)
    if not done.wait(timeout):
        return {"error": "timed out"}
    return out["r"]
