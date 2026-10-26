"""MPRIS for our TV apps' players, so the remote's media keys reach them.

Plasma's media controller owns the Play/Pause, Rewind and Fast-forward keys (global shortcuts)
and sends them over D-Bus (MPRIS) to the player that's playing: browsers and mpv do this, so
our libmpv player has to too. This serves org.mpris.MediaPlayer2.<name> on the session bus
(dbus-python on a GLib loop in its own thread) and hands the commands to Qt.

    bridge = Mpris("couchbox_dropout", "Dropout", "couchbox-streaming")    # a QObject
    bridge.command -> ("playpause" | "play" | "pause" | "stop" | "next" | "previous" | "seek", seconds)
    bridge.update(playing, paused, title, artist, length_s, position_s)   from QML
"""

import threading

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib
from PySide6.QtCore import QObject, Signal, Slot

ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
PROPS = "org.freedesktop.DBus.Properties"


class _Service(dbus.service.Object):
    def __init__(self, bus, bridge, identity, desktop):
        super().__init__(bus, "/org/mpris/MediaPlayer2")
        self.bridge = bridge
        self.identity = identity
        self.desktop = desktop
        self.status = "Stopped"
        self.meta = {}
        self.position = 0

    # ------------------------------------------------------------------ org.mpris.MediaPlayer2.Player
    @dbus.service.method(PLAYER)
    def PlayPause(self):
        self.bridge.command.emit("playpause", 0.0)

    @dbus.service.method(PLAYER)
    def Play(self):
        self.bridge.command.emit("play", 0.0)

    @dbus.service.method(PLAYER)
    def Pause(self):
        self.bridge.command.emit("pause", 0.0)

    @dbus.service.method(PLAYER)
    def Stop(self):
        self.bridge.command.emit("stop", 0.0)

    @dbus.service.method(PLAYER)
    def Next(self):
        self.bridge.command.emit("next", 0.0)

    @dbus.service.method(PLAYER)
    def Previous(self):
        # the previous song (Spotify); the video apps go back 30 s (they have no previous)
        self.bridge.command.emit("previous", -30.0)

    @dbus.service.method(PLAYER, in_signature="x")
    def Seek(self, offset_us):
        # Plasma's Rewind / Fast-forward keys ask for 5 s; the remote's are 10 s steps
        s = offset_us / 1e6
        self.bridge.command.emit("seek", s * 2 if abs(s) <= 5 else s)

    @dbus.service.method(PLAYER, in_signature="ox")
    def SetPosition(self, _track, pos_us):
        self.bridge.command.emit("seekto", pos_us / 1e6)

    @dbus.service.method(PLAYER, in_signature="s")
    def OpenUri(self, _uri):
        pass

    @dbus.service.signal(PLAYER, signature="x")
    def Seeked(self, pos):
        pass

    # ------------------------------------------------------------------ org.mpris.MediaPlayer2
    @dbus.service.method(ROOT)
    def Raise(self):
        pass

    @dbus.service.method(ROOT)
    def Quit(self):
        self.bridge.command.emit("stop", 0.0)

    # ------------------------------------------------------------------ properties
    def _all(self, iface):
        if iface == ROOT:
            return {
                "CanQuit": True,
                "CanRaise": False,
                "HasTrackList": False,
                "Identity": self.identity,
                "DesktopEntry": self.desktop,
                "SupportedUriSchemes": dbus.Array([], "s"),
                "SupportedMimeTypes": dbus.Array([], "s"),
            }
        if iface == PLAYER:
            active = self.status != "Stopped"
            return {
                "PlaybackStatus": self.status,
                "Rate": 1.0,
                "MinimumRate": 1.0,
                "MaximumRate": 1.0,
                "Volume": 1.0,
                "Position": dbus.Int64(int(self.position * 1e6)),
                "Metadata": dbus.Dictionary(self.meta, signature="sv"),
                "CanGoNext": active,
                "CanGoPrevious": active,
                "CanPlay": active,
                "CanPause": active,
                "CanSeek": active,
                "CanControl": True,
            }
        return {}

    @dbus.service.method(PROPS, in_signature="ss", out_signature="v")
    def Get(self, iface, prop):
        return self._all(iface)[prop]

    @dbus.service.method(PROPS, in_signature="s", out_signature="a{sv}")
    def GetAll(self, iface):
        return self._all(iface)

    @dbus.service.method(PROPS, in_signature="ssv")
    def Set(self, iface, prop, value):
        pass

    @dbus.service.signal(PROPS, signature="sa{sv}as")
    def PropertiesChanged(self, iface, changed, invalidated):
        pass

    def set_state(self, status, meta, position):
        changed = {}
        if status != self.status:
            self.status = status
            changed["PlaybackStatus"] = status
            for k in ("CanPlay", "CanPause", "CanSeek", "CanGoNext", "CanGoPrevious"):
                changed[k] = status != "Stopped"
        if meta != self.meta:
            self.meta = meta
            changed["Metadata"] = dbus.Dictionary(meta, signature="sv")
        jumped = abs(position - self.position) > 3
        self.position = position
        if changed:
            self.PropertiesChanged(PLAYER, changed, dbus.Array([], "s"))
        if jumped:
            self.Seeked(dbus.Int64(int(position * 1e6)))


class Mpris(QObject):
    command = Signal(str, float)

    def __init__(self, name, identity, desktop):
        super().__init__()
        self.svc = None
        self._last = None
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        ready = threading.Event()

        def loop():
            try:
                bus = dbus.SessionBus()
                self._name = dbus.service.BusName(f"{ROOT}.{name}", bus)
                self.svc = _Service(bus, self, identity, desktop)
            finally:
                ready.set()
            self.loop = GLib.MainLoop()
            self.loop.run()

        threading.Thread(target=loop, daemon=True).start()
        ready.wait(5)

    @Slot(bool, bool, str, str, float, float)
    def update(self, active, paused, title, artist, length, position):
        """From QML: what's playing (active false: nothing)."""
        if not self.svc:
            return
        status = "Stopped" if not active else "Paused" if paused else "Playing"
        meta = {}
        if active:
            meta = {
                "mpris:trackid": dbus.ObjectPath("/org/couchbox/track/1"),
                "xesam:title": title,
                "xesam:artist": dbus.Array([artist] if artist else [], "s"),
                "mpris:length": dbus.Int64(int(length * 1e6)),
            }
        GLib.idle_add(lambda: (self.svc.set_state(status, meta, position), False)[1])
