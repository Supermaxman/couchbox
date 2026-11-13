"""keyguard: OK, Back, Menu and Play/Pause act once per press; the arrows repeat as they are."""

import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402

from couchbox import keyguard  # noqa: E402


class Window:
    focus = "list"

    def activeFocusItem(self):
        return self.focus


def key(kind, k, repeat=False):
    return QKeyEvent(kind, k, Qt.NoModifier, "", repeat)


def guard():
    seen = []
    return keyguard.KeyGuard(Window(), on_key=seen.append), seen


def test_a_held_ok_acts_once():
    g, seen = guard()
    assert g.eventFilter(None, key(QEvent.KeyPress, Qt.Key_Return)) is False
    assert g.eventFilter(None, key(QEvent.KeyPress, Qt.Key_Return, True)) is True
    assert g.eventFilter(None, key(QEvent.KeyRelease, Qt.Key_Return, True)) is True
    assert g.eventFilter(None, key(QEvent.KeyRelease, Qt.Key_Return)) is False
    assert seen == ["Key_Return"]


def test_a_release_after_the_focus_moved_is_dropped():
    g, _ = guard()
    for k in (Qt.Key_Escape, Qt.Key_Back, Qt.Key_Menu, Qt.Key_MediaTogglePlayPause):
        g.window.focus = "list"
        assert g.eventFilter(None, key(QEvent.KeyPress, k)) is False
        g.window.focus = "player"  # what the press opened
        assert g.eventFilter(None, key(QEvent.KeyRelease, k)) is True
    assert g.eventFilter(None, key(QEvent.KeyRelease, Qt.Key_Return)) is True  # (its press was never seen)


def test_arrows_repeat():
    g, seen = guard()
    assert g.eventFilter(None, key(QEvent.KeyPress, Qt.Key_Right)) is False
    assert g.eventFilter(None, key(QEvent.KeyPress, Qt.Key_Right, True)) is False
    assert g.eventFilter(None, key(QEvent.KeyRelease, Qt.Key_Right)) is False
    assert seen == ["Key_Right"]
