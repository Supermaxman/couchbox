"""Where the YouTube app's time goes, for finding what's slow on the box.

Every measurement is kept (the last 120, in memory) and goes into the control socket's focus
report ("timing": the box check's perf mode reads it); with COUCHBOX_YT_TIMING=1 each is also
printed, as one line:  yt-timing KIND key=value ...

Kinds:
  call     one back-end call (an InnerTube browse, next, search...; the stream): op, ms
  stream   a video's stream, in parts: yt-dlp's phases (webpage, the clients' player API calls,
           the player JS, the JS challenge, the HLS playlist), as ms from the start of each
  play     OK on a video until its first frame: stream (reply), open (mpv loadfile until the file
           is loaded), frame (until the first picture), total
  key      a key until the focus moved (a page or panel shown): key, ms, to (where the focus went)
  stall    a frame that came late while the screen was moving (an image decoded on the GUI
           thread, a busy binding): ms
  rate     the TV's refresh-rate switch for a video (the screen is blank meanwhile): ms, mode
"""

import collections
import os
import threading
import time
from typing import Any

ON = os.environ.get("COUCHBOX_YT_TIMING") == "1"
_events: collections.deque = collections.deque(maxlen=120)
_lock = threading.Lock()
_t0 = time.monotonic()


def now() -> float:
    return time.monotonic()


def ms(since: float) -> int:
    return round((time.monotonic() - since) * 1000)


def note(kind: str, **data: Any) -> None:
    e = {"at": round(time.monotonic() - _t0, 3), "kind": kind, **data}
    with _lock:
        _events.append(e)
    if ON:
        print("yt-timing " + kind + " " + " ".join(f"{k}={v}" for k, v in data.items()), flush=True)


def recent(n: int = 120) -> list[dict[str, Any]]:
    with _lock:
        return list(_events)[-n:]


class Phases:
    """yt-dlp's messages as they come (its logger): when each phase of an extraction began."""

    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.marks: list[tuple[int, str]] = []

    def _mark(self, msg: str) -> None:
        m = str(msg)
        for needle, name in (
            ("Downloading webpage", "webpage"),
            ("player API JSON", "api"),
            ("Downloading player ", "player-js"),
            ("Solving JS challenges", "js-challenge"),
            ("m3u8 information", "hls-playlist"),
            ("Downloading MPD", "dash-manifest"),
        ):
            if needle in m:
                if name == "api":  # which client: "Downloading tv samsung player API JSON"
                    name = "api:" + m.split(": Downloading ", 1)[-1].split(" player API")[0].replace(" ", "-")
                self.marks.append((ms(self.t0), name))
                return

    debug = info = _mark

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass

    def spans(self, total: int) -> dict[str, int]:
        """{phase: ms it took} (each until the next began; the last until total)."""
        out: dict[str, int] = {}
        for i, (at, name) in enumerate(self.marks):
            end = self.marks[i + 1][0] if i + 1 < len(self.marks) else total
            out[name] = out.get(name, 0) + max(0, end - at)
        return out
