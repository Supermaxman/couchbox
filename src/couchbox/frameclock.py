"""Animations in step with the screen, for the apps that draw video.

Those apps run Qt Quick's basic render loop (libmpv draws on Qt's thread: couchbox.player), and on
that loop Qt moves animations from a 16 ms timer of its own, not from the screen's frames. The
TV shows a frame every 16.7 ms, so the two drift: about once in 25 frames a frame showed two
timer steps' worth of movement (measured on the Pi 5, the YouTube app's rows: 31-32 ms steps
among the 16s, in most moves). A focus glide or a scrolling row hitched a little each time.

attach(window) takes the timer's place: animations move once per frame, right after each frame
goes to the screen (frameSwapped), by the time that passed since the frame before. With no
frames (only timers running, or the window hidden) they go by the clock, as before.

Qt has a class for this, QAnimationDriver, but PySide6 leaves it out, so it's made and called
through libQt6Core's exported functions (part of Qt 6's public interface: they stay). If any
of that isn't there, attach() does nothing and Qt's own timer stays.

COUCHBOX_FRAME_CLOCK=0 turns it off (to compare).
"""

import ctypes
import os
import time

from PySide6.QtCore import SIGNAL, QObject, Qt, QTimer

_NEW = "_ZN16QAnimationDriverC1EP7QObject"  # QAnimationDriver::QAnimationDriver(QObject *)
_INSTALL = "_ZN16QAnimationDriver7installEv"  # void QAnimationDriver::install()
_ADVANCE = "_ZN16QAnimationDriver7advanceEv"  # void QAnimationDriver::advance()

_clock = None  # the one clock of this process (kept: Qt holds on to it)


class _FrameClock(QObject):
    def __init__(self, window):
        super().__init__()
        import shiboken6

        qt = ctypes.CDLL("libQt6Core.so.6")
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc.restype = ctypes.c_void_p
        libc.malloc.argtypes = [ctypes.c_size_t]
        new, install, self._advance = getattr(qt, _NEW), getattr(qt, _INSTALL), getattr(qt, _ADVANCE)
        for fn in (new, install, self._advance):
            fn.restype = None
        new.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        install.argtypes = [ctypes.c_void_p]
        self._advance.argtypes = [ctypes.c_void_p]
        # the driver: two pointers' worth of object in memory that's never freed (Qt uses it
        # until the process ends)
        self._this = libc.malloc(256)
        if not self._this:
            raise MemoryError
        ctypes.memset(self._this, 0, 256)
        new(self._this, None)
        self._driver = shiboken6.wrapInstance(self._this, QObject)
        self._window = window
        self._running = False
        self._last = 0  # the last frame (monotonic ns)
        # with no frames coming, by the clock: a timer of Qt's own interval, only while something runs
        self._idle = QTimer(self)
        self._idle.setTimerType(Qt.PreciseTimer)
        self._idle.setInterval(16)
        self._idle.timeout.connect(self._tick)
        QObject.connect(self._driver, SIGNAL("started()"), self._started)
        QObject.connect(self._driver, SIGNAL("stopped()"), self._stopped)
        window.afterAnimating.connect(self._frame)
        window.frameSwapped.connect(self._swapped)
        install(self._this)

    def _started(self):
        self._running = True
        self._idle.start()
        if self._window.isVisible():  # a frame now: the animation's first step comes with it
            self._window.update()

    def _stopped(self):
        self._running = False
        self._idle.stop()

    def _late(self):
        """No frame for a frame and a half."""
        screen = self._window.screen()
        hz = screen.refreshRate() if screen is not None else 60.0
        return time.monotonic_ns() - self._last > 1.5e9 / max(hz, 20.0)

    def _step(self):
        self._last = time.monotonic_ns()
        self._advance(self._this)

    def _swapped(self):
        """A frame has just gone to the screen: move the animations on, for the next one. Done
        now, the work (bindings, layout) fits in the wait for the screen's next refresh; done as
        that frame starts, it pushed busy frames past the compositor's deadline, and they showed
        a refresh late: 30 a second (measured: the streaming apps' page scrolling)."""
        if self._running:
            self._step()

    def _frame(self):
        """The window is about to draw the first frame after a pause: up to now, so it already moves."""
        if self._running and self._late():
            self._step()

    def _tick(self):
        """No frame lately (nothing on screen changes, the window is hidden): by the clock."""
        if self._running and self._late():
            self._step()


def attach(window) -> bool:
    """Move this process's animations with `window`'s frames. True when it took (once per process;
    only on the basic render loop, and never for off-screen screenshots)."""
    global _clock
    if _clock is not None:
        return True
    if os.environ.get("COUCHBOX_FRAME_CLOCK") == "0" or os.environ.get("QSG_RENDER_LOOP") != "basic":
        return False
    if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or not hasattr(window, "afterAnimating"):
        return False
    try:
        _clock = _FrameClock(window)
    except (OSError, AttributeError, ImportError, MemoryError, RuntimeError, TypeError):
        return False  # a Qt without these: its own timer, as before
    return True
