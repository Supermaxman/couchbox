"""The YouTube app's streams, worked out in a process of their own: yt-dlp (ytstream) runs here,
not in couchbox-yt, so its seconds of Python per video (the JS challenge, the parsing) never hold
the app's interpreter while Qt draws, and its memory stays out of the app's.

  python3 -m couchbox.services.ytworker      (couchbox-yt starts it; one JSON request a line on
                                              stdin, one JSON answer a line on stdout)

Requests: {"n": 1, "op": OP, "args": {...}}; answers: {"n": 1, "result": ...} or {"n": 1,
"error": "...", "unavailable": true}. OPs:
  resolve   a video's stream now (ytstream.resolve's answer): first in line
  prefetch  the same, kept for when it's asked for (a focused card, Up next): after any resolve,
            newest first; one asked for more than PREFETCH_STALE seconds ago is dropped
  about     yt-dlp's version and the JavaScript runtime (Settings → About)
  client    the TV client's context as yt-dlp knows it (InnerTube's clientVersion...)
yt-dlp's information is kept per video until its addresses are about to expire, so a video
prefetched, or played before, starts without asking YouTube again; which format plays is chosen
when it's asked for (some only open a few seconds after extraction). The worker leaves once it
holds more than MAX_RSS_MB, between requests; the app starts another when it next needs one.
"""

import heapq
import itertools
import json
import os
import re
import subprocess
import sys
import threading
import time
from typing import Any

CACHE_SECONDS = 4 * 3600  # at most; less when the addresses expire sooner
EXPIRY_MARGIN = 900  # an address this close to its expiry is asked for again
PREFETCH_STALE = 8.0
MAX_RSS_MB = 400
MAX_CACHED = 24
# what's kept of yt-dlp's information per video (the rest is thumbnails, heat maps, every
# language's caption formats...: megabytes once parsed)
INFO_KEYS = (
    "id",
    "title",
    "channel",
    "uploader",
    "channel_id",
    "duration",
    "chapters",
    "view_count",
    "like_count",
    "timestamp",
    "release_timestamp",
    "live_status",
    "is_live",
)
FORMAT_KEYS = (
    "format_id",
    "url",
    "vcodec",
    "acodec",
    "width",
    "height",
    "fps",
    "tbr",
    "abr",
    "audio_channels",
    "format_note",
    "language_preference",
    "available_at",
    "protocol",
    "fragments",
    "columns",
    "rows",
)


def slim(info: dict[str, Any]) -> dict[str, Any]:
    out = {k: info.get(k) for k in INFO_KEYS if k in info}
    out["formats"] = [{k: f[k] for k in FORMAT_KEYS if k in f} for f in info.get("formats") or []]
    want = ("en",)
    out["subtitles"] = {lang: [t for t in tracks if t.get("ext") == "vtt"] for lang, tracks in (info.get("subtitles") or {}).items()}
    out["automatic_captions"] = {
        lang: [t for t in tracks if t.get("ext") == "vtt"]
        for lang, tracks in (info.get("automatic_captions") or {}).items()
        if lang.split("-")[0] in want
    }
    return out


DASH_LEAD = 1.0  # seconds: DASH that opens within this is waited for (trying it meanwhile), else HLS now


def touch(url: str) -> None:
    """The stream's servers, looked up and each address asked for its first bytes, in the
    background: mpv's own first requests then find the name known and the file at hand (opening a
    signed-in DASH stream took 0.25 s on the box, or 1.3 s: 0.73 s for the video's first answer,
    0.57 s for the sound's)."""
    import re

    urls = [u for u in re.findall(r"%\d+%(https://[^;]+)", url)] if url.startswith("edl://") else [url] if url.startswith("http") else []

    def get(u: str) -> None:
        import requests

        try:
            requests.get(u, headers={"Range": "bytes=0-1023"}, timeout=5).close()
        except requests.RequestException:
            pass

    for u in urls[:2]:
        threading.Thread(target=get, args=(u,), daemon=True).start()


def wait_until_open(url: str, until: float) -> None:
    """Until YouTube serves url (a one-byte range), or the time it gave (and a little more)."""
    import requests

    s = requests.Session()
    while time.time() < until + 1:
        try:
            if s.get(url, headers={"Range": "bytes=0-0"}, timeout=3).status_code in (200, 206):
                return
        except requests.RequestException:
            pass
        time.sleep(0.2)


# ------------------------------------------------------------------ in the worker
def expires(info: dict[str, Any]) -> float:
    """When the stream addresses in yt-dlp's information stop working (their expire=)."""
    for f in info.get("formats") or []:
        m = re.search(r"[?&/]expire[=/](\d{9,})", f.get("url") or "")
        if m:
            return float(m.group(1))
    return time.time() + 3600


class Cache:
    def __init__(self) -> None:
        self.items: dict[str, tuple[float, dict[str, Any]]] = {}

    def get(self, vid: str) -> dict[str, Any] | None:
        hit = self.items.get(vid)
        if hit and hit[0] > time.time():
            return hit[1]
        self.items.pop(vid, None)
        return None

    def put(self, vid: str, info: dict[str, Any]) -> None:
        until = min(time.time() + CACHE_SECONDS, expires(info) - EXPIRY_MARGIN)
        if until <= time.time():
            return
        if len(self.items) >= MAX_CACHED:  # the one that expires first goes
            del self.items[min(self.items, key=lambda k: self.items[k][0])]
        self.items[vid] = (until, info)


def _libc():
    import ctypes

    try:
        return ctypes.CDLL("libc.so.6")
    except OSError:
        return None


LIBC = _libc()
if LIBC is not None:
    try:
        LIBC.mallopt(-8, 1)  # M_ARENA_MAX: one (the worker does one thing at a time)
    except AttributeError:
        LIBC = None


def rss_mb() -> float:
    try:
        with open("/proc/self/status") as fh:
            return next((int(ln.split()[1]) for ln in fh if ln.startswith("VmRSS:")), 0) / 1024
    except OSError:
        return 0.0


class Worker:
    def __init__(self, out) -> None:
        self.out = out
        self.cache = Cache()
        self.queue: list[tuple[int, float, int, dict[str, Any]]] = []
        self.seq = itertools.count()
        self.cv = threading.Condition()
        self.out_lock = threading.Lock()

    def answer(self, n: int, **body: Any) -> None:
        with self.out_lock:
            self.out.write(json.dumps({"n": n, **body}) + "\n")
            self.out.flush()

    def take(self, req: dict[str, Any]) -> None:
        args = req.get("args") or {}
        if req.get("op") == "resolve" and self.cache.get(args.get("key") or args.get("id", "")) is not None:
            # kept from before: answered now, not behind an extraction in progress (a prefetch)
            threading.Thread(target=self.run_one, args=(req, time.monotonic()), daemon=True).start()
            return
        prefetch = req.get("op") == "prefetch"
        # resolve and the rest in the order asked; prefetches after them, newest first
        key = (1, -time.monotonic(), next(self.seq)) if prefetch else (0, 0.0, next(self.seq))
        with self.cv:
            heapq.heappush(self.queue, (*key, req))
            self.cv.notify()

    def info_touched(self, a: dict[str, Any]) -> None:
        """prefetch: the information, and its stream's addresses looked up and asked for once."""
        from couchbox.services import ytstream

        info, cached = self.info(a)
        if not cached:
            try:
                touch(
                    ytstream.playable(info, a.get("h264", True), int(a.get("max_height") or ytstream.MAX_HEIGHT), a.get("superres", True))[
                        "url"
                    ]
                )
            except ytstream.Unavailable:
                pass

    def info(self, a: dict[str, Any], phases: Any = None) -> tuple[dict[str, Any], bool]:
        """yt-dlp's information for a video: kept, from the app's own /player call (signed in: "player"
        and the cache "key", one per profile), else yt-dlp's."""
        from couchbox.services import ytjs, ytstream

        key = a.get("key") or a["id"]
        info = self.cache.get(key)
        if info is not None:
            return info, True
        if a.get("player"):
            t = time.monotonic()
            info = ytstream.from_player(a["player"], ytjs.solve)
            del t
            if phases is not None:
                phases.marks.append((0, "decipher"))
        else:
            info = ytstream.extract(a["id"], phases, a.get("visitor") or "")
        info = slim(info)
        self.cache.put(key, info)
        return info, False

    def resolve(self, a: dict[str, Any]) -> dict[str, Any]:
        """The stream to play now. DASH (opens in ~0.1 s; HLS takes over a second) opens a few
        seconds after it's worked out (YouTube's gap for the ads we don't show): when that's
        within DASH_LEAD it's waited for, trying its address meanwhile (it often opens before the
        time it's given), else HLS plays now."""
        from couchbox.services import ytstream, yttiming

        t = time.monotonic()
        phases = yttiming.Phases()
        info, cached = self.info(a, phases)
        took = yttiming.ms(t)
        out = ytstream.resolve(
            a["id"],
            h264=a.get("h264", True),
            max_height=int(a.get("max_height") or ytstream.MAX_HEIGHT),
            superres=a.get("superres", True),
            info=info,
            lead=DASH_LEAD,
        )
        waited = 0
        if out.get("probe"):
            w = time.monotonic()
            wait_until_open(out.pop("probe"), out.pop("until"))
            waited, out["wait"] = yttiming.ms(w), 0
        out["timing"].update(phases.spans(took), extract=took, cached=cached, dash_wait=waited)
        if not cached:
            touch(out.get("url") or "")
        return out

    def run_one(self, req: dict[str, Any], asked: float) -> None:
        from couchbox.services import ytstream

        n, op, a = req.get("n", 0), req.get("op"), req.get("args") or {}
        try:
            if op == "prefetch":
                if time.monotonic() - asked > PREFETCH_STALE or self.cache.get(a.get("key") or a["id"]) is not None:
                    return self.answer(n, result={"ok": True, "skipped": True})
                self.info_touched(a)
                return self.answer(n, result={"ok": True})
            if op == "resolve":
                return self.answer(n, result=self.resolve(a))
            if op == "warm":  # the app's start: yt-dlp imported, node up with the player read
                from couchbox.services import ytjs

                ytstream.module()
                ytjs.prepare()
                return self.answer(n, result={"ok": True, "rss": round(rss_mb())})
            if op == "player":  # the player JS's version and signatureTimestamp (the app's /player calls)
                from couchbox.services import ytjs

                p = ytjs.current_player()
                return self.answer(n, result={"ver": p["ver"], "sts": p["sts"]})
            if op == "about":
                return self.answer(n, result=ytstream.about())
            if op == "client":
                from couchbox.services import youtube

                return self.answer(n, result=youtube.tv_client())
            if op == "clients":  # yt-dlp's TV clients' contexts (measuring: playerProbe)
                ytstream.module()
                from yt_dlp.extractor.youtube._base import INNERTUBE_CLIENTS

                keep = ("clientName", "clientVersion", "userAgent", "deviceMake", "deviceModel", "osName", "osVersion")
                return self.answer(
                    n,
                    result={
                        k: {x: v for x, v in INNERTUBE_CLIENTS[k]["INNERTUBE_CONTEXT"]["client"].items() if x in keep}
                        for k in ("tv", "tv_samsung", "tv_downgraded")
                        if k in INNERTUBE_CLIENTS
                    },
                )
            if op == "ping":
                return self.answer(n, result={"ok": True, "rss": round(rss_mb())})
            return self.answer(n, error=f"unknown op {op}")
        except ytstream.Unavailable as err:
            return self.answer(n, error=str(err), unavailable=True)
        except Exception as err:  # noqa: BLE001 - the app shows it
            return self.answer(n, error=str(err) or err.__class__.__name__)

    def loop(self) -> None:
        while True:
            with self.cv:
                while not self.queue:
                    if rss_mb() > MAX_RSS_MB:  # grown: leave now, between requests (a fresh one starts)
                        print(f"ytworker: {rss_mb():.0f} MB: leaving for a fresh worker", file=sys.stderr, flush=True)
                        os._exit(0)
                    self.cv.wait()
                prio, stamp, _, req = heapq.heappop(self.queue)
            self.run_one(req, -stamp if prio else time.monotonic())
            if LIBC is not None:
                LIBC.malloc_trim(0)  # what an extraction freed, back to the system (it grew 68 -> 102 MB)


def serve() -> None:
    # stdout is the answers' line; anything printed (yt-dlp, our logs) goes to stderr instead
    out = os.fdopen(os.dup(1), "w")
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    from couchbox.services import ytstream, yttiming

    yttiming.ON = False  # the app prints what this measures
    w = Worker(out)
    threading.Thread(target=w.loop, daemon=True).start()
    threading.Thread(target=ytstream.module, daemon=True).start()  # yt-dlp imported now: the first video starts sooner
    for line in sys.stdin:
        try:
            w.take(json.loads(line))
        except ValueError:
            continue
    os._exit(0)  # the app went away


# ------------------------------------------------------------------ in the app
class Client:
    """couchbox-yt's side: the worker started when first needed (and again if it left)."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.pending: dict[int, dict[str, Any]] = {}
        self.n = itertools.count(1)

    def _start(self) -> subprocess.Popen:
        if self.proc and self.proc.poll() is None:
            return self.proc
        self.proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "couchbox.services.ytworker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        return self.proc

    def _read(self, proc: subprocess.Popen) -> None:
        for line in proc.stdout:
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                p = self.pending.pop(msg.get("n"), None)
            if p:
                p["answer"] = msg
                p["done"].set()
        with self.lock:  # it left: whatever it was asked fails (and is asked again once)
            mine = [k for k, p in self.pending.items() if p["proc"] is proc]
            for k in mine:
                p = self.pending.pop(k)
                p["answer"] = {"error": "the stream worker stopped", "gone": True}
                p["done"].set()

    def _send(self, op: str, args: dict[str, Any], wait: bool, timeout: float) -> Any:
        with self.lock:
            proc = self._start()
            n = next(self.n)
            p = {"done": threading.Event(), "answer": None, "proc": proc}
            if wait:
                self.pending[n] = p
            try:
                proc.stdin.write(json.dumps({"n": n, "op": op, "args": args}) + "\n")
                proc.stdin.flush()
            except OSError:
                self.pending.pop(n, None)
                return {"error": "the stream worker stopped", "gone": True}
        if not wait:
            return None
        if not p["done"].wait(timeout):
            with self.lock:
                self.pending.pop(n, None)
            return {"error": "YouTube took too long to answer."}
        return p["answer"]

    def call(self, op: str, timeout: float = 90, **args: Any) -> Any:
        from couchbox.services import ytstream

        msg = self._send(op, args, True, timeout)
        if msg.get("gone"):  # it left (grown, or crashed): once more, with a fresh one
            msg = self._send(op, args, True, timeout)
        if "error" in msg:
            raise ytstream.Unavailable(msg["error"]) if msg.get("unavailable") else RuntimeError(msg["error"])
        return msg["result"]

    def prefetch(self, vid: str, **args: Any) -> None:
        self._send("prefetch", dict(args, id=vid), False, 0)

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()


if __name__ == "__main__":
    serve()
