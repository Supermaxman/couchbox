"""The remote's one-shot keys, once per press, for the TV apps (YouTube, the streaming apps,
Frigate, the morning show and Reels, Spotify).

OK, Back, Menu and Play/Pause act once per press, on whatever had the focus when they went
down. Their repeats (the key held, or the compositor's) are dropped: a held OK flipped pause
over and over, a held Back left the player, then page after page, then the app. A release
that arrives after the press moved the focus is dropped too (the press that opened Search
typed nothing, the press that opened a panel picked nothing in it). The arrows and every
other key pass as they are: held arrows keep moving.

    guard = keyguard.install(window)        # kept by the caller for as long as the window lives
    guard.pressed                           # a signal: any key went down (not its repeats)
    keyguard.KeyGuard(on_key=fn)            # fn(name) with it, name as Qt's ("Key_Return");
        .attach(window)                     # made before the window is (a QML context property)
"""

from PySide6.QtCore import QEvent, QObject, Qt, Signal

ONCE = (
    "Key_Return",
    "Key_Enter",
    "Key_Select",
    "Key_Escape",
    "Key_Back",
    "Key_Menu",
    "Key_MediaTogglePlayPause",
    "Key_MediaPlay",
    "Key_MediaPause",
)


class KeyGuard(QObject):
    pressed = Signal()  # any key (someone's there)

    def __init__(self, window=None, on_key=None):
        super().__init__()
        self.window = window
        self.on_key = on_key
        self.keys = {int(getattr(Qt, k)) for k in ONCE}
        self.down = {}  # a one-shot key that's down: what had the focus when it went down

    def attach(self, window):
        self.window = window
        window.installEventFilter(self)
        return self

    def eventFilter(self, obj, ev):
        kind = ev.type()
        if kind not in (QEvent.KeyPress, QEvent.KeyRelease):
            return False
        key = int(ev.key())
        if kind == QEvent.KeyPress and not ev.isAutoRepeat():
            self.pressed.emit()
            if self.on_key:
                try:
                    name = Qt.Key(key).name
                except ValueError:  # (a key Qt has no name for)
                    name = str(key)
                self.on_key(name)
        if key not in self.keys:
            return False
        if ev.isAutoRepeat():
            return True
        focus = self.window.activeFocusItem()
        if kind == QEvent.KeyPress:
            self.down[key] = focus
            return False
        return self.down.pop(key, None) is not focus


def install(window, on_key=None):
    """The guard on a window (keep what this returns: Qt doesn't)."""
    return KeyGuard(on_key=on_key).attach(window)
