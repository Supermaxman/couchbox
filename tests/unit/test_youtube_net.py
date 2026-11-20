"""The TV's connection (ytnet): a failed check says offline once, checks go on until YouTube
answers, then online once; a lookup that hangs counts as no connection."""

import threading
import time

from couchbox.services import ytnet


def wait_for(cond, secs=3.0):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_offline_once_then_online_once(monkeypatch):
    monkeypatch.setattr(ytnet, "EVERY", 0.05)
    up = {"v": False}
    said = []
    net = ytnet.Net(said.append, reach=lambda: up["v"])
    assert net.check() is False
    assert net.check() is False  # (still offline: said once)
    assert said == [False] and net.online is False
    up["v"] = True
    assert wait_for(lambda: said == [False, True])
    assert net.online is True
    time.sleep(0.2)
    assert said == [False, True]  # (the checks stopped)


def test_online_check_says_nothing():
    said = []
    net = ytnet.Net(said.append, reach=lambda: True)
    assert net.check() is True
    assert said == [] and net.online is True


def test_a_hanging_lookup_is_no_connection(monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(ytnet, "TIMEOUT", 0.1)
    monkeypatch.setattr(ytnet, "_connect", lambda host, timeout: gate.wait(5))
    net = ytnet.Net(lambda on: None)
    t = time.time()
    assert net._reach() is False
    assert time.time() - t < 1.5
    net.stop.set()
    gate.set()
