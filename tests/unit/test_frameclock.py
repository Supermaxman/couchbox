"""frameclock: only on the basic render loop, never off screen; a Qt without the driver leaves Qt's timer."""

import pytest

pytest.importorskip("PySide6.QtCore")

from couchbox import frameclock  # noqa: E402


class Window:
    def afterAnimating(self):
        pass


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    monkeypatch.setattr(frameclock, "_clock", None)
    for k in ("COUCHBOX_FRAME_CLOCK", "QSG_RENDER_LOOP", "QT_QPA_PLATFORM"):
        monkeypatch.delenv(k, raising=False)


def test_not_on_the_threaded_loop():
    assert frameclock.attach(Window()) is False  # Qt's own render thread drives animations there


def test_not_off_screen(monkeypatch):
    monkeypatch.setenv("QSG_RENDER_LOOP", "basic")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    assert frameclock.attach(Window()) is False


def test_switched_off(monkeypatch):
    monkeypatch.setenv("QSG_RENDER_LOOP", "basic")
    monkeypatch.setenv("COUCHBOX_FRAME_CLOCK", "0")
    assert frameclock.attach(Window()) is False


def test_a_qt_without_the_driver_keeps_its_timer(monkeypatch):
    monkeypatch.setenv("QSG_RENDER_LOOP", "basic")

    def missing(window):
        raise AttributeError("no such symbol")

    monkeypatch.setattr(frameclock, "_FrameClock", missing)
    assert frameclock.attach(Window()) is False
