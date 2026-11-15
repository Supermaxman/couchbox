"""The apps' event subscription covers every topic their QML listens for: couchboxd sends a
client only the topics it asked for. "install" was missing, so setup's Install to the SSD
never saw its progress, nor its end (no Restart now)."""

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtCore")

REPO = Path(__file__).resolve().parents[2]


def test_every_topic_the_screens_listen_for_is_subscribed():
    from couchbox import qtapp

    heard = set()
    for f in (REPO / "ui").rglob("*.qml"):
        heard |= set(re.findall(r'topic\s*[!=]==\s*"([a-z_]+)\.', f.read_text()))
    assert "install" in heard and "remote" in heard
    assert heard <= set(qtapp.TOPICS), heard - set(qtapp.TOPICS)


def test_install_progress_reaches_a_subscriber():
    import asyncio

    from couchbox import qtapp
    from couchbox.daemon import events

    async def run():
        events.bind_loop(asyncio.get_running_loop())
        q = events.listen(qtapp.TOPICS)
        try:
            events.publish("install.progress", {"state": "done", "next": "restart"})
            return await asyncio.wait_for(q.get(), 1)
        finally:
            events.unlisten(q)

    assert asyncio.run(run()) == ("install.progress", {"state": "done", "next": "restart"})
