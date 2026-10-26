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
"""

import ctypes
import os

import mpv
from PySide6.QtCore import Property, Qt, Signal, Slot
from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat
from PySide6.QtQuick import QQuickFramebufferObject

try:
    from PySide6.QtQuick import QQuickOpenGLUtils
except ImportError:  # older PySide6
    QQuickOpenGLUtils = None

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
            self.ctx.update_cb = self.item.frameReady.emit
        fbo = self.framebufferObject()
        _gl["last"] = None
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
            input_default_bindings="no",
            ytdl="no",
            cache="yes",
            demuxer_max_bytes="120MiB",
            demuxer_max_back_bytes="30MiB",
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
        self._pos = 0.0
        self._dur = 0.0
        self._paused = False
        self._buffering = False
        self._ended = False
        self._tracks = []
        self._sid = 0
        self._error = ""
        self.frameReady.connect(self.update, Qt.QueuedConnection)
        self._prop.connect(self._on_prop, Qt.QueuedConnection)
        for name in ("time-pos", "duration", "pause", "paused-for-cache", "eof-reached", "track-list", "sid"):
            self.mpv.observe_property(name, lambda n, v: self._prop.emit(n, v))

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

    # ------------------------------------------------------------------ QML API
    @Slot(str, float)
    def load(self, url, start):
        self._ended = False
        self._error = ""
        self.endedChanged.emit()
        opts = {"start": str(int(start))} if start > 0 else {}
        self.mpv.command("loadfile", url, "replace", -1, ",".join(f"{k}={v}" for k, v in opts.items()))
        self.mpv.pause = False

    @Slot(str)
    def loadLive(self, url):
        """A live camera (an endless fMP4 stream): small buffers, start as soon as there's a frame.
        The options are per file, so later load()s play as before."""
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

    @Slot()
    def togglePause(self):
        self.mpv.pause = not self.mpv.pause

    @Slot(bool)
    def setPaused(self, p):
        self.mpv.pause = p

    @Slot(float)
    def seek(self, delta):
        try:
            self.mpv.command("seek", delta, "relative+exact" if abs(delta) < 15 else "relative")
        except Exception:
            pass

    @Slot(float)
    def seekTo(self, pos):
        try:
            self.mpv.command("seek", pos, "absolute")
        except Exception:
            pass

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
        self.mpv.terminate()

    position = Property(float, lambda s: s._pos, notify=positionChanged)
    duration = Property(float, lambda s: s._dur, notify=durationChanged)
    paused = Property(bool, lambda s: s._paused, notify=pausedChanged)
    buffering = Property(bool, lambda s: s._buffering, notify=bufferingChanged)
    ended = Property(bool, lambda s: s._ended, notify=endedChanged)
    subtitles = Property("QVariantList", lambda s: s._tracks, notify=tracksChanged)
    subtitle = Property(int, lambda s: s._sid, notify=subtitleChanged)
    error = Property(str, lambda s: s._error, notify=errorChanged)
