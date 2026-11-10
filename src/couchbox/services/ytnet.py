"""Whether the TV can reach YouTube: asked when a call fails (no internet, or YouTube's own
trouble?), and then every few seconds until it can again. couchbox-yt tells the app on each
change, so it shows YouTube's "No internet connection" panel and takes it down by itself."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as Late

HOST = ("www.youtube.com", 443)
TIMEOUT = 4.0  # s: no answer by then counts as no connection (a lost network's lookups hang)
EVERY = 3.0  # s between checks while offline


def _connect(host: tuple[str, int], timeout: float) -> bool:
    try:
        socket.create_connection(host, timeout=timeout).close()
        return True
    except OSError:
        return False


class Net:
    """online: the last word. check() asks now; offline, a thread asks every EVERY seconds and
    changed(True) once YouTube answers again. reach: how to ask (the demo's is made up)."""

    def __init__(self, changed: Callable[[bool], None], reach: Callable[[], bool] | None = None):
        self.changed = changed
        self.online = True
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ytnet")
        self.reach = reach or self._reach
        self.stop = threading.Event()

    def _reach(self) -> bool:
        # (getaddrinfo has no timeout of its own: a lookup on a network that's gone can hang for
        # tens of seconds, so it runs on a thread of its own and late is "no")
        try:
            return self.pool.submit(_connect, HOST, TIMEOUT).result(timeout=TIMEOUT + 0.5)
        except Late:
            return False

    def check(self) -> bool:
        """Can the TV reach YouTube right now? Offline starts the checks that end it."""
        ok = self.reach()
        if not ok:
            self._set(False)
        return ok

    def _set(self, online: bool) -> None:
        with self.lock:
            if online == self.online:
                return
            self.online = online
        if not online:
            threading.Thread(target=self._watch, name="ytnet-watch", daemon=True).start()
        self.changed(online)

    def _watch(self) -> None:
        while not self.stop.wait(EVERY):
            if self.reach():
                self._set(True)
                return
