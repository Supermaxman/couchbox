"""MpvVideo: libmpv drawn inside Qt Quick (as Jellyfin Desktop does), for our TV apps.

mpv decodes and renders into the item's OpenGL framebuffer (libmpv's render API); QML draws
its own controls on top. H.264 is decoded in software on all four cores (the Pi 5 has no
H.264 hardware); HEVC uses the Pi's hardware decoder (hwdec=drm-copy, which needs the Pi
build of ffmpeg in /opt/couchbox/ffmpeg-rpi: couchbox-streaming runs with it, like Jellyfin Desktop).

QML:
    MpvVideo { id: video; anchors.fill: parent }
    video.load(url, startSeconds)      video.togglePause()   video.seek(+10)
    video.position / duration / paused / buffering / ended / subtitles / subtitle
    video.setSubtitle(id)  (0: off)    video.stop()
Set COUCHBOX_MUTE=1 to play without sound (tests while the TV is in use).

Settings → Display and sound, followed live (couchbox.playback): Video drawing (below), Match
the TV's refresh rate (a Follower per player, polled once a second), Night mode (an audio
filter) and Surround sound passthrough (audio-spdif).
"""

import atexit
import ctypes
import os
import resource
import threading
import time
import weakref

import mpv
from PySide6.QtCore import Property, Qt, QTimer, Signal, Slot
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from PySide6.QtQuick import QQuickFramebufferObject

from couchbox import playback

try:
    from PySide6.QtQuick import QQuickOpenGLUtils
except ImportError:  # older PySide6
    QQuickOpenGLUtils = None

# Video can hold many files open (see the fence leak below): take the full allowance up front,
# rather than crashing at the usual 1024. couchbox-memory also raises it for any app past 256.
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (resource.getrlimit(resource.RLIMIT_NOFILE)[1],) * 2)
except (OSError, ValueError):
    pass

_egl = ctypes.CDLL("libEGL.so.1")
_egl.eglGetProcAddress.restype = ctypes.c_void_p
_egl.eglGetProcAddress.argtypes = [ctypes.c_char_p]


# libmpv 0.41's OpenGL render API makes a GL fence at the end of every frame and keeps it for
# a buffer swap that only its own windows do (fixed upstream after 0.41), so it never deletes it.
# On the Pi each fence holds a file descriptor: about 4 minutes of live video used up all 1024,
# after which Mesa failed every frame ("Export failed") and the app crashed. glFenceSync goes
# through _fence_sync, which notes the newest fence; after each frame _Renderer deletes the
# frame's last one, which is that end-of-frame fence (mpv makes it after everything else).
_FenceSyncFn = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)
_DeleteSyncFn = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
_gl = {"fence": None, "delete": None, "last": None}


def _fence_sync(condition, flags):
    fence = _gl["fence"](condition, flags)
    _gl["last"] = fence
    return fence


_fence_sync_fn = _FenceSyncFn(_fence_sync)


def _get_proc_address(_ctx, name):
    addr = _egl.eglGetProcAddress(name) or 0
    if name == b"glFenceSync" and addr:
        _gl["fence"] = _FenceSyncFn(addr)
        return ctypes.cast(_fence_sync_fn, ctypes.c_void_p).value
    if name == b"glDeleteSync" and addr:
        _gl["delete"] = _DeleteSyncFn(addr)
    return addr


def _drop_frame_fence():
    fence, _gl["last"] = _gl["last"], None
    if fence and _gl["delete"]:
        _gl["delete"](fence)


_proc_fn = mpv.MpvGlGetProcAddressFn(_get_proc_address)

# How mpv draws each frame (Settings → Display and sound → Video drawing). mpv's own defaults
# use scaling filters made for desktop graphics cards: on 1080p60 Twitch they kept the Pi 5's
# GPU ~86% busy, so frames missed their slot (stutter) and the chip ran hot (fan at full).
# "fast" is mpv's fast profile plus bilinear chroma; "quality" puts back mpv's defaults.
FAST = {
    "scale": "bilinear",
    "dscale": "bilinear",
    "cscale": "bilinear",
    "dither": "no",
    "correct-downscaling": "no",
    "linear-downscaling": "no",
    "sigmoid-upscaling": "no",
    "hdr-compute-peak": "no",
}
_DEBUG = bool(os.environ.get("COUCHBOX_MPV_LOG"))  # also: what draws after a seek (MpvVideo._debug)
_players = weakref.WeakSet()
TIMING = None  # an app's timing hook (couchbox-yt: yttiming.note): how long a file takes to show
_live = {}  # the playback settings (playback.LIVE), followed while the app runs


def _settings_changed(changed):
    """Follow the settings while the app runs, so a change shows on the playing video."""
    _live.update(changed)
    for p in list(_players):
        p.apply_settings(changed)


def _follow_rate(ref):
    """Once a second, show the player's state to its refresh-rate Follower (it may switch the
    TV: kscreen-doctor, here rather than on Qt's thread). Ends with the player."""
    while True:
        time.sleep(1)
        p = ref()
        if p is None or p._closed:
            return
        try:
            p._rate.step(playback.snapshot(p._get), passive=p._live_cam, shown=p._shown)
        except Exception:  # noqa: BLE001
            pass
        del p


@atexit.register
def _put_rate_back():
    """The app is quitting: Settings' mode again, if a player here switched (a guard process
    does it should the app be killed instead)."""
    for p in list(_players):
        p._rate.close()


class _Renderer(QQuickFramebufferObject.Renderer):
    def __init__(self, item):
        super().__init__()
        self.item = item
        self.ctx = None

    def createFramebufferObject(self, size):
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
        # keep a Python reference: Qt Quick uses it after this returns
        self.fbo = QOpenGLFramebufferObject(size, fmt)
        return self.fbo

    def render(self):
        if self.ctx is None:
            self.ctx = mpv.MpvRenderContext(self.item.mpv, "opengl", opengl_init_params={"get_proc_address": _proc_fn})
            self.ctx.update_cb = self.item._on_update
        fbo = self.framebufferObject()
        _gl["last"] = None
        # render.h: mpv_render_context_update() after each update callback, before rendering
        new = self.ctx.update()
        self.item._debug(f"render {fbo.width()}x{fbo.height()} new-frame={new}")
        it = self.item
        if TIMING and new and it._t_loaded:  # the file's first picture
            t = time.monotonic()
            TIMING("frame", open=round((it._t_loaded - it._t_load) * 1000), frame=round((t - it._t_loaded) * 1000), start=it._t_start)
            it._t_load = it._t_loaded = 0.0
        self.ctx.render(flip_y=False, opengl_fbo={"w": fbo.width(), "h": fbo.height(), "fbo": fbo.handle()})
        _drop_frame_fence()
        if QQuickOpenGLUtils:
            QQuickOpenGLUtils.resetOpenGLState()

    def __del__(self):
        if self.ctx is not None:
            self.ctx.free()


class MpvVideo(QQuickFramebufferObject):
    frameReady = Signal()
    positionChanged = Signal()
    durationChanged = Signal()
    pausedChanged = Signal()
    bufferingChanged = Signal()
    endedChanged = Signal()
    tracksChanged = Signal()
    subtitleChanged = Signal()
    errorChanged = Signal()
    _prop = Signal(str, object)  # from mpv's thread to Qt's

    def __init__(self, parent=None):
        super().__init__(parent)
        mute = os.environ.get("COUCHBOX_MUTE") == "1"
        # hardware decoding only for HEVC (the Pi 5's decoder); H.264 in software on 4 threads
        self.mpv = mpv.MPV(
            vo="libmpv",
            hwdec="drm-copy",
            hwdec_codecs="hevc",
            vd_lavc_threads=4,
            vd_lavc_dr="yes",
            # local playlists (nebula.py writes one with the streams it picked) may
            # point at https segments
            demuxer_lavf_o="protocol_whitelist=[file,http,https,tcp,tls,crypto,data]",
            keep_open="yes",
            idle="yes",
            osc="no",
            osd_bar="no",  # the apps draw their own progress bars (mpv's showed on seeks, mid-screen)
            input_default_bindings="no",
            ytdl="no",
            cache="yes",
            demuxer_max_bytes=(os.environ.get("COUCHBOX_MPV_CACHE") or "120MiB,30MiB").split(",")[0],
            demuxer_max_back_bytes=(os.environ.get("COUCHBOX_MPV_CACHE") or "120MiB,30MiB").split(",")[-1],
            hls_bitrate="max",
            sub_auto="no",
            slang="en,eng",
            sid="no",
            sub_font_size=44,
            sub_border_size=3,
            sub_margin_y=60,
            sub_create_cc_track="yes",  # live captions (CEA-608) when a stream has them
            audio_display="no",
            ao="null" if mute else "pipewire,pulse,alsa",
            msg_level="all=warn",
            log_handler=(lambda lvl, comp, msg: print(f"mpv {lvl} {comp}: {msg.strip()}", flush=True))
            if os.environ.get("COUCHBOX_MPV_LOG")
            else None,
        )
        self._dbg_until = 0.0  # COUCHBOX_MPV_LOG: log renders and updates until then (after a seek)
        self._t_load = 0.0  # loadfile (TIMING): until the file is loaded, then its first picture
        self._t_loaded = 0.0
        self._t_start = 0
        self._pos = 0.0
        self._dur = 0.0
        self._paused = False
        self._buffering = False
        self._ended = False
        self._tracks = []
        self._sid = 0
        self._error = ""
        self._closed = False
        self._live_cam = False  # loadLive(): a camera (never takes the TV's mode from another player)
        self._shown = True  # the item is visible (apps hide it when the player page isn't on top)
        self.visibleChanged.connect(self._on_visible)
        self._rate = playback.Follower(who=f"player-{id(self)}", on_claim=playback.start_guard)
        self._quality = {}  # mpv's defaults, as text for "set" (cscale's default "" reads back as 0)
        for k in FAST:
            try:
                v = self.mpv[k]
                self._quality[k] = "yes" if v is True else "no" if v is False else str(v or "")
            except Exception:  # noqa: BLE001  (an mpv without the option)
                pass
        if not _live:
            _live.update(playback.live_settings())
            threading.Thread(target=playback.watch_settings, args=(_settings_changed,), daemon=True).start()
        _players.add(self)
        self.apply_settings(_live)
        threading.Thread(target=_follow_rate, args=(weakref.ref(self),), daemon=True).start()
        self.frameReady.connect(self.update, Qt.QueuedConnection)
        self._prop.connect(self._on_prop, Qt.QueuedConnection)
        for name in ("time-pos", "duration", "pause", "paused-for-cache", "eof-reached", "track-list", "sid"):
            self.mpv.observe_property(name, lambda n, v: self._prop.emit(n, v))

        @self.mpv.event_callback("file-loaded")
        def _loaded(ev):
            if self._t_load and not self._t_loaded:
                self._t_loaded = time.monotonic()

        @self.mpv.event_callback("end-file")
        def _end(ev):
            # reason 4 is an error (0 EOF, 2 stop, 3 quit, 5 redirect)
            reason = getattr(getattr(ev, "data", None), "reason", None)
            if reason == 4 or str(reason).lower().endswith("error"):
                self._prop.emit("error", "This video couldn't be played.")

    def createRenderer(self):
        self._renderer = _Renderer(self)  # kept alive for Qt Quick (it owns it in C++)
        return self._renderer

    @Slot(str, object)
    def _on_prop(self, name, value):
        if name == "time-pos":
            self._pos = float(value or 0)
            self.positionChanged.emit()
            self._debug("time-pos")
        elif name == "duration":
            self._dur = float(value or 0)
            self.durationChanged.emit()
        elif name == "pause":
            self._paused = bool(value)
            self.pausedChanged.emit()
        elif name == "paused-for-cache":
            self._buffering = bool(value)
            self.bufferingChanged.emit()
        elif name == "eof-reached":
            self._ended = bool(value)
            self.endedChanged.emit()
        elif name == "track-list":
            self._tracks = [
                {"id": t.get("id"), "title": t.get("title") or t.get("lang") or f"Track {t.get('id')}", "lang": t.get("lang") or ""}
                for t in (value or [])
                if t.get("type") == "sub"
            ]
            self.tracksChanged.emit()
        elif name == "sid":
            self._sid = int(value) if isinstance(value, int) else 0
            self.subtitleChanged.emit()
        elif name == "error":
            self._error = value
            self.errorChanged.emit()

    @Slot()
    def _on_visible(self):
        self._shown = self.isVisible()  # (Qt's thread; the Follower's thread reads it)

    def _get(self, name):
        # a property, as attribute access reads it (mpv[name] would read the option of that name:
        # options/path and options/estimated-vf-fps don't exist, so the Follower saw nothing)
        return getattr(self.mpv, name.replace("-", "_"))

    def apply_settings(self, changed):
        """Playback settings (all of them at start, then each change) on this player."""
        if "video.drawing" in changed:
            self.set_drawing(_live["video.drawing"])
        test = os.environ.get("COUCHBOX_MUTE") == "1"  # someone's watching the TV: leave its mode and sound be
        if "video.match_rate" in changed:
            self._rate.set_enabled(bool(_live["video.match_rate"]) and not test)
        if "audio.night_mode" in changed:
            self._set("af", playback.night_filter(bool(_live["audio.night_mode"])))
        if ("audio.passthrough" in changed or "audio.night_mode" in changed) and not test:
            # mpv starts the audio decoder again, so a playing video changes at once
            codecs = playback.tv_codecs() if _live["audio.passthrough"] == "on" else []
            self._set("audio-spdif", playback.spdif(_live["audio.passthrough"], bool(_live["audio.night_mode"]), codecs))

    def _set(self, k, v):
        try:
            self.mpv.command("set", k, v)
        except Exception:  # noqa: BLE001
            pass

    def set_drawing(self, mode):
        for k, v in (FAST if mode == "fast" else self._quality).items():
            if k in self._quality:
                try:
                    self.mpv.command("set", k, v)
                except Exception:  # noqa: BLE001
                    pass
        self.frameReady.emit()  # redraw (from any thread)

    # ------------------------------------------------------------------ QML API
    @Slot(str, float)
    def load(self, url, start):
        self.loadWith(url, start, "")

    @Slot(str, float, str)
    def loadWith(self, url, start, options):
        """load() with mpv options for this file only, in mpv's syntax ("a=1,b=%5%x,y,z"): the
        YouTube app gives a live stream's sound as audio-file=%LEN%URL."""
        self._live_cam = False
        self._ended = False
        self._error = ""
        self.endedChanged.emit()
        opts = [f"start={int(start)}"] if start > 0 else []
        if options:
            opts.append(options)  # as given: its %LEN% quoting may hold commas
        self._t_load, self._t_loaded, self._t_start = time.monotonic(), 0.0, int(start)
        self.mpv.command("loadfile", url, "replace", -1, ",".join(opts))
        self.mpv.pause = False

    @Slot(str)
    def loadLive(self, url):
        """A live camera (an endless fMP4 stream): small buffers, start as soon as there's a frame.
        The options are per file, so later load()s play as before."""
        self._live_cam = True
        self._ended = False
        self._error = ""
        self.endedChanged.emit()
        opts = "cache=no,demuxer-readahead-secs=0,demuxer-lavf-analyzeduration=0.5,demuxer-lavf-probesize=65536,video-latency-hacks=yes"
        self.mpv.command("loadfile", url, "replace", -1, opts)
        self.mpv.pause = False

    @Slot(str)
    def addSubtitle(self, url):
        try:
            self.mpv.command("sub-add", url, "auto")
        except Exception:
            pass

    @Slot(str, str)
    def addSubtitleTrack(self, url, title):
        """A subtitle file (the YouTube app's captions), shown at once."""
        try:
            self.mpv.command("sub-add", url, "select", title or "Captions")
        except Exception:
            pass

    @Slot(float)
    def setSpeed(self, speed):
        try:
            self.mpv.speed = max(0.25, min(4.0, speed))
        except Exception:
            pass

    @Slot()
    def togglePause(self):
        self.mpv.pause = not self.mpv.pause

    @Slot(bool)
    def setPaused(self, p):
        self.mpv.pause = p

    @Slot(result=bool)
    def toggleMute(self):
        """Sound off or on again (a keyboard's M); returns whether it's off now."""
        try:
            self.mpv.mute = not self.mpv.mute
            return bool(self.mpv.mute)
        except Exception:  # noqa: BLE001
            return False

    @Slot(float)
    def seek(self, delta):
        # back past the start: to 0 exactly (a relative seek before the start of a stream made of
        # a video and a sound track, the YouTube app's EDL, can leave no picture while paused)
        try:
            if self._pos + delta < 0.5:
                self.mpv.command("seek", 0, "absolute+exact")
            else:
                self.mpv.command("seek", delta, "relative+exact" if abs(delta) < 15 else "relative")
        except Exception:
            pass
        self._after_seek(f"seek {delta:+g} from {self._pos:.1f}")

    @Slot(float)
    def seekTo(self, pos):
        try:
            self.mpv.command("seek", pos, "absolute")
        except Exception:
            pass
        self._after_seek(f"seek to {pos:.1f} from {self._pos:.1f}")

    def _after_seek(self, what):
        """Paused, nothing plays on to draw the new picture: ask Qt to draw it again a few times
        while mpv decodes it (the TV showed black after a paused seek). COUCHBOX_MPV_LOG=1: log
        what happens for the next 4 s (mpv's update calls, our renders, the position)."""
        self._dbg_until = time.monotonic() + 4
        self._debug(f"{what} paused={self._paused}")
        if self._paused:
            for ms in (60, 200, 450, 900, 1600, 2500):
                QTimer.singleShot(ms, self.update)

    def _on_update(self):
        """mpv's render update callback (from mpv's thread): Qt draws the next frame."""
        self._debug("update-cb")
        self.frameReady.emit()

    def _debug(self, msg):
        if _DEBUG and time.monotonic() < self._dbg_until:
            print(f"mpv-debug {time.monotonic():.3f} pos={self._pos:.2f} {msg}", flush=True)

    @Slot(int)
    def setSubtitle(self, sid):
        self.mpv.sid = sid if sid > 0 else "no"

    @Slot(int)
    def setSubtitlePosition(self, percent):
        """Where subtitles sit (100: the bottom); raised while the controls are showing."""
        self.mpv.sub_pos = max(0, min(150, percent))

    @Slot()
    def stop(self):
        self.mpv.command("stop")

    @Slot()
    def shutdown(self):
        self._closed = True
        self._rate.close()
        self.mpv.terminate()

    position = Property(float, lambda s: s._pos, notify=positionChanged)
    duration = Property(float, lambda s: s._dur, notify=durationChanged)
    paused = Property(bool, lambda s: s._paused, notify=pausedChanged)
    buffering = Property(bool, lambda s: s._buffering, notify=bufferingChanged)
    ended = Property(bool, lambda s: s._ended, notify=endedChanged)
    subtitles = Property("QVariantList", lambda s: s._tracks, notify=tracksChanged)
    subtitle = Property(int, lambda s: s._sid, notify=subtitleChanged)
    error = Property(str, lambda s: s._error, notify=errorChanged)
