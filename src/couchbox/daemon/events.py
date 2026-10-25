"""In-process event bus for couchboxd: handlers publish, subscribed clients receive.

publish() is safe from executor threads (handlers run there)."""

import asyncio
from typing import Any

_listeners: list[tuple[asyncio.Queue, set[str]]] = []
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def listen(topics: list[str]) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    _listeners.append((q, set(topics)))
    return q


def unlisten(q: asyncio.Queue) -> None:
    _listeners[:] = [(x, t) for x, t in _listeners if x is not q]


def _deliver(topic: str, data: Any) -> None:
    for q, topics in list(_listeners):
        if not topics or topic in topics or topic.split(".")[0] in topics:
            try:
                q.put_nowait((topic, data))
            except asyncio.QueueFull:
                pass  # a stuck client misses events rather than stalling everyone


def publish(topic: str, data: Any = None) -> None:
    if _loop is None:
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _loop:
        _deliver(topic, data)
    else:
        _loop.call_soon_threadsafe(_deliver, topic, data)
