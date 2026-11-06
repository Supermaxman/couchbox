"""A live stream from its adaptive formats, for mpv: a small HTTP server on 127.0.0.1.

Signed in on the TV's own clients, YouTube answers a live stream's /player with its adaptive
formats only (no HLS, no DASH manifest; the clients that give HLS want a guest, which YouTube
bot-checks on a TV's address). Each such format is a live "manifestless" stream: its address
with &sq=N is the N-th segment (about 5 s), every segment a whole fragmented MP4 (ftyp, moov,
then moof and mdat), and each answer's X-Head-Seqnum header says the newest one. yt-dlp plays
these the same way (its live DASH fragments, counted from the head).

mpv gets one endless MP4 per format: http://127.0.0.1:PORT/live/GROUP/ITAG. The first segment
whole, then each next one's moof and mdat only (one ftyp and moov, as a fragmented MP4 stream
is). A group (one video) starts all its formats at the same segment, a little behind the head,
so the video and the sound line up; one asked for later (another quality) starts where the
stream is by then (the first one's start, one segment on for each segment's length since).
"""

from __future__ import annotations

import http.server
import itertools
import socketserver
import threading
import time
from typing import Any

BEHIND = 2  # segments behind the newest one to start at (~10 s: YouTube's own latency is like it)
GROUPS = 24  # live streams kept (their addresses expire in hours anyway)
WAIT_NEXT = 30.0  # how long to keep asking for a segment that isn't there yet before giving up


def boxes(data: bytes) -> list[tuple[str, bytes]]:
    """An MP4's top-level boxes: [(type, the box's bytes)]."""
    out, i = [], 0
    while i + 8 <= len(data):
        size = int.from_bytes(data[i : i + 4], "big")
        kind = data[i + 4 : i + 8].decode("latin-1")
        if size == 1 and i + 16 <= len(data):
            size = int.from_bytes(data[i + 8 : i + 16], "big")
        elif size == 0:
            size = len(data) - i
        if size < 8:
            break
        out.append((kind, data[i : i + size]))
        i += size
    return out


def fragments(data: bytes, first: bool) -> bytes:
    """A segment as the stream goes on: the first one whole, the rest their moof and mdat."""
    if first:
        return data
    return b"".join(b for kind, b in boxes(data) if kind in ("moof", "mdat"))


class Proxy:
    def __init__(self, session: Any = None) -> None:
        self.lock = threading.Lock()
        self.groups: dict[str, dict[str, Any]] = {}  # group: {urls: {itag: url}, start: sq or None, at: time}
        self.ids = itertools.count(1)
        self.server: socketserver.ThreadingTCPServer | None = None
        self.port = 0
        self._session = session

    # ------------------------------------------------------------------ the formats
    def group(self, urls: dict[str, str], seconds: float = 5.0, behind: float = 0.0, window: float = 0.0) -> dict[str, str]:
        """Register one live stream's formats ({itag: its YouTube address}; seconds: a segment's
        length; behind: how far behind the newest segment to start, for going back into the
        stream's DVR window of window seconds): {itag: the address for mpv}. Starts the server
        the first time."""
        self.start()
        gid = f"g{next(self.ids)}"
        with self.lock:
            self.groups[gid] = {
                "urls": dict(urls),
                "start": None,
                "t0": 0.0,
                "seconds": max(1.0, seconds or 5.0),
                "at": time.time(),
                "behind": max(0.0, behind),
                "window": window,
            }
            for old in sorted(self.groups, key=lambda g: self.groups[g]["at"])[:-GROUPS]:
                del self.groups[old]
        return {itag: f"http://127.0.0.1:{self.port}/live/{gid}/{itag}" for itag in urls}

    def session(self) -> Any:
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def head(self, url: str) -> int:
        """The newest segment's number (X-Head-Seqnum, from a segment 0 request's headers)."""
        r = self.session().get(url + "&sq=0", timeout=(8, 20), stream=True)
        try:
            return int(r.headers.get("X-Head-Seqnum") or 0)
        finally:
            r.close()

    def start_of(self, gid: str, url: str) -> int:
        with self.lock:
            g = self.groups.get(gid)
            if g is None:
                raise KeyError(gid)
            if g["start"] is not None:  # (as far on as the stream has gone since)
                return g["start"] + int((time.monotonic() - g["t0"]) / g["seconds"])
        back = int(g["behind"] / g["seconds"])
        if g["window"]:
            back = min(back, int(g["window"] / g["seconds"]) - BEHIND - 1)
        sq = max(0, self.head(url) - BEHIND - max(0, back))
        with self.lock:
            if g["start"] is None:
                g["start"], g["t0"] = sq, time.monotonic()
            return g["start"] + int((time.monotonic() - g["t0"]) / g["seconds"])

    def segments(self, gid: str, itag: str):
        """The stream's bytes, segment after segment, for as long as it's live and wanted."""
        with self.lock:
            g = self.groups.get(gid)
            url = (g or {}).get("urls", {}).get(itag)
        if not url:
            return
        sq = self.start_of(gid, url)
        first = True
        waited = 0.0
        while True:
            try:
                r = self.session().get(f"{url}&sq={sq}", timeout=(8, 30))
                ok = r.status_code == 200 and len(r.content) > 8
            except Exception as err:  # noqa: BLE001 - a dropped request: asked again
                print(f"yt live {gid}/{itag}: segment {sq}: {err}", flush=True)
                ok = False
                r = None
            if not ok:
                if r is not None and r.status_code in (403, 410):
                    print(f"yt live {gid}/{itag}: segment {sq}: {r.status_code} (the address expired?)", flush=True)
                    return
                if waited >= WAIT_NEXT:
                    print(f"yt live {gid}/{itag}: no segment {sq} after {WAIT_NEXT:.0f} s: the stream ended", flush=True)
                    return
                time.sleep(1.0)
                waited += 1.0
                continue
            waited = 0.0
            yield fragments(r.content, first)
            first = False
            sq += 1

    # ------------------------------------------------------------------ the server
    def start(self) -> None:
        with self.lock:
            if self.server is not None:
                return
            proxy = self

            class Handler(http.server.BaseHTTPRequestHandler):
                protocol_version = "HTTP/1.0"  # (no length: the body ends when the stream does)

                def log_message(self, *args: Any) -> None:
                    pass

                def do_GET(self) -> None:  # noqa: N802 - http.server's name
                    parts = self.path.strip("/").split("/")
                    if len(parts) != 3 or parts[0] != "live" or parts[1] not in proxy.groups:
                        self.send_error(404)
                        return
                    _, gid, itag = parts
                    try:
                        chunks = proxy.segments(gid, itag)
                        first = next(chunks, None)
                    except Exception as err:  # noqa: BLE001
                        print(f"yt live {gid}/{itag}: {err}", flush=True)
                        first = None
                    if first is None:
                        self.send_error(502)
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.end_headers()
                    try:
                        self.wfile.write(first)
                        for chunk in chunks:
                            self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        pass  # mpv stopped (or moved to another quality)

            class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
                daemon_threads = True
                allow_reuse_address = True

            self.server = Server(("127.0.0.1", 0), Handler)
            self.port = self.server.server_address[1]
            threading.Thread(target=self.server.serve_forever, name="yt-live", daemon=True).start()


PROXY = Proxy()
