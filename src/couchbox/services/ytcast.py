"""Casting from the YouTube phone app to the TV, as a TV's YouTube app takes it: DIAL to be found
and launched on the network, and YouTube's Lounge protocol to be told what to play.

DIAL (the phone finds TVs on the Wi-Fi):
  * SSDP: an M-SEARCH for urn:dial-multiscreen-org:service:dial:1 on 239.255.255.250:1900 gets
    an answer pointing at our device description (/dd.xml, with an Application-URL header);
  * GET /apps/YouTube says whether the app runs (and our screen id); POST /apps/YouTube
    launches it, with a pairing code the TV then registers with YouTube, so the phone and the
    screen meet in a "lounge".

The Lounge (the phone and the TV talk through YouTube's servers):
  * a screen id (generate_screen_id, kept), a lounge token for it (get_lounge_token_batch);
  * bind: a session (SID, gsessionid), then a long poll that streams the phone's commands
    (setPlaylist, setVideo, play, pause, seekTo, setVolume, next, previous, stopVideo...);
  * the TV answers on the same channel: nowPlaying, onStateChange, onVolumeChanged;
  * "Link with TV code": get_pairing_code gives 12 digits to type into the phone app.

What plays is the app's (couchbox-yt): Lounge commands go to it through its control socket
(couchbox.appctl), and its state comes back the same way. No tokens or codes are logged.
"""

import json
import logging
import random
import re
import socket
import string
import struct
import threading
import time
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs

import requests

log = logging.getLogger("couchbox.ytcast")

LOUNGE = "https://www.youtube.com/api/lounge"
APP = "lb-v4"  # the TV ("leanback") app, as the phone knows it
TIMEOUT = (8, 20)
POLL_TIMEOUT = (8, 330)  # the long poll: YouTube holds it open for minutes
SSDP_ADDR, SSDP_PORT = "239.255.255.250", 1900
DIAL_ST = "urn:dial-multiscreen-org:service:dial:1"
HTTP_PORT = 56789

# the phone's view of the player (YouTube's player states)
STATE = {"unstarted": -1, "ended": 0, "playing": 1, "paused": 2, "buffering": 3}


# ------------------------------------------------------------------ the Lounge's answers
def parse_chunks(text: str) -> list[list[Any]]:
    """The bind channel's stream ("<length>\\n<json array>" repeated) -> its [id, [command, args?]]
    entries, in order. A partial chunk at the end is left for the next read."""
    out, i = [], 0
    while i < len(text):
        m = re.match(r"\s*(\d+)\n", text[i:])
        if not m:
            break
        start = i + m.end()
        n = int(m.group(1))
        body = text[start : start + n]
        if len(body) < n:
            break
        try:
            arr = json.loads(body)
        except ValueError:
            break
        out.extend(arr if isinstance(arr, list) else [])
        i = start + n
    return out


def split_chunks(text: str) -> tuple[list[list[Any]], str]:
    """parse_chunks, and what's left over (an incomplete chunk)."""
    entries, i = [], 0
    while True:
        m = re.match(r"\s*(\d+)\n", text[i:])
        if not m:
            break
        start = i + m.end()
        n = int(m.group(1))
        if len(text) - start < n:
            break
        try:
            arr = json.loads(text[start : start + n])
            entries.extend(arr if isinstance(arr, list) else [])
        except ValueError:
            pass
        i = start + n
    return entries, text[i:]


def command(entry: list[Any]) -> tuple[int, str, dict[str, Any]]:
    """[id, ["setVideo", {"videoId": ...}]] -> (id, "setVideo", {...})."""
    aid = int(entry[0]) if entry and isinstance(entry[0], int) else -1
    body = entry[1] if len(entry) > 1 and isinstance(entry[1], list) else []
    name = body[0] if body and isinstance(body[0], str) else ""
    args = body[1] if len(body) > 1 and isinstance(body[1], dict) else {}
    return aid, name, args


def playlist(args: dict[str, Any]) -> dict[str, Any]:
    """setPlaylist / setVideo's arguments -> {videoId, start, videoIds, index, listId}."""
    ids = [v for v in (args.get("videoIds") or "").split(",") if v]
    vid = args.get("videoId") or ""
    try:
        index = int(args.get("currentIndex", -1))
    except (TypeError, ValueError):
        index = -1
    if not vid and ids and 0 <= index < len(ids):
        vid = ids[index]
    if vid and vid not in ids:
        ids = [vid]
    if index < 0 and vid in ids:
        index = ids.index(vid)
    try:
        start = float(args.get("currentTime") or 0)
    except (TypeError, ValueError):
        start = 0.0
    return {"videoId": vid, "start": start, "videoIds": ids, "index": max(0, index), "listId": args.get("listId") or ""}


def outgoing(cmds: list[tuple[str, dict[str, Any]]], ofs: int) -> dict[str, str]:
    """What the TV says (nowPlaying, onStateChange...) as the bind channel's form: count, ofs,
    req0__sc, req0_<key>..."""
    form = {"count": str(len(cmds)), "ofs": str(ofs)}
    for i, (name, args) in enumerate(cmds):
        form[f"req{i}__sc"] = name
        for k, v in args.items():
            form[f"req{i}_{k}"] = str(v)
    return form


def zx() -> str:
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(12))


# ------------------------------------------------------------------ the screen's side
class Lounge:
    """The TV's end of the Lounge: its screen id and token, a session, the long poll, replies.
    on_command(name, args) is called (on the poll's thread) for each command from a phone."""

    def __init__(self, name: str, screen_id: str = "", device_id: str = "", session: requests.Session | None = None):
        self.name = name
        self.screen_id = screen_id
        self.device_id = device_id or str(uuid.uuid4())
        self.s = session or requests.Session()
        self.s.headers.setdefault("User-Agent", "Mozilla/5.0 (Linux; couchbox) Cobalt/25 YouTube TV")
        self.token = ""
        self.token_expires = 0.0
        self.sid = self.gsession = ""
        self.aid = -1
        self.rid = random.randint(10000, 90000)
        self.ofs = 0
        self.lock = threading.Lock()
        self.on_command: Callable[[str, dict[str, Any]], None] = lambda name, args: None
        self.stopping = False

    # pairing
    def ensure_screen(self) -> str:
        if not self.screen_id:
            r = self.s.get(f"{LOUNGE}/pairing/generate_screen_id", timeout=TIMEOUT)
            r.raise_for_status()
            self.screen_id = r.text.strip()
        return self.screen_id

    def ensure_token(self) -> str:
        if not self.token or time.time() > self.token_expires - 600:
            r = self.s.post(f"{LOUNGE}/pairing/get_lounge_token_batch", data={"screen_ids": self.ensure_screen()}, timeout=TIMEOUT)
            r.raise_for_status()
            scr = (r.json().get("screens") or [{}])[0]
            self.token = scr.get("loungeToken") or ""
            self.token_expires = (scr.get("expiration") or 0) / 1000 or time.time() + 3600
            if not self.token:
                raise RuntimeError("YouTube gave no lounge token")
        return self.token

    def pairing_code(self) -> str:
        """12 digits for the phone app's "Link with TV code" (valid a few minutes)."""
        r = self.s.get(
            f"{LOUNGE}/pairing/get_pairing_code",
            params={
                "ctx": "pair",
                "access_type": "permanent",
                "app": APP,
                "lounge_token": self.ensure_token(),
                "screen_id": self.screen_id,
                "screen_name": self.name,
                "device_id": self.device_id,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        code = re.sub(r"\D", "", r.text)
        if len(code) != 12:
            raise RuntimeError("YouTube gave no pairing code")
        return code

    def register(self, pairing_code: str) -> None:
        """A phone launching us over DIAL sends a code: registering it puts the phone in our lounge."""
        r = self.s.post(
            f"{LOUNGE}/pairing/register_pairing_code",
            data={
                "access_type": "permanent",
                "app": APP,
                "pairing_code": pairing_code,
                "screen_id": self.ensure_screen(),
                "screen_name": self.name,
                "device_id": self.device_id,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()

    # the bind channel
    def _params(self, **more) -> dict[str, Any]:
        p = {
            "device": "LOUNGE_SCREEN",
            "theme": "cl",
            "capabilities": "dsp,mic,dpa",
            "mdxVersion": "2",
            "VER": "8",
            "v": "2",
            "app": APP,
            "name": self.name,
            "id": self.device_id,
            "loungeIdToken": self.ensure_token(),
            "zx": zx(),
            "t": "1",
        }
        if self.sid:
            p.update({"SID": self.sid, "gsessionid": self.gsession, "AID": str(self.aid)})
        p.update(more)
        return p

    def bind(self) -> None:
        """A new session: SID and gsessionid (and whatever commands came with them)."""
        self.sid = self.gsession = ""
        self.aid, self.ofs = -1, 0
        self.rid += 1
        r = self.s.post(
            f"{LOUNGE}/bc/bind", params=self._params(RID=str(self.rid), CVER="1", AID="42"), data={"count": "0"}, timeout=TIMEOUT
        )
        r.raise_for_status()
        self._handle(parse_chunks(r.text))
        if not self.sid:
            raise RuntimeError("the lounge gave no session")

    def send(self, *cmds: tuple[str, dict[str, Any]]) -> None:
        if not self.sid or not cmds:
            return
        with self.lock:
            self.rid += 1
            form = outgoing(list(cmds), self.ofs)
            self.ofs += len(cmds)
            rid = self.rid
        try:
            r = self.s.post(f"{LOUNGE}/bc/bind", params=self._params(RID=str(rid)), data=form, timeout=TIMEOUT)
            if r.status_code in (400, 404, 410):  # the session's gone: the poll binds again
                self.sid = ""
        except requests.RequestException as err:
            log.warning("lounge: couldn't send %s (%s)", cmds[0][0], type(err).__name__)

    def poll_once(self) -> None:
        """One long poll: commands as they stream in, until YouTube closes it."""
        r = self.s.get(f"{LOUNGE}/bc/bind", params=self._params(RID="rpc", CI="0", TYPE="xmlhttp"), stream=True, timeout=POLL_TIMEOUT)
        if r.status_code in (400, 404, 410):
            self.sid = ""
            return
        r.raise_for_status()
        buf = ""
        for piece in r.iter_content(chunk_size=None, decode_unicode=True):
            if self.stopping:
                break
            buf += piece if isinstance(piece, str) else piece.decode("utf-8", "replace")
            entries, buf = split_chunks(buf)
            self._handle(entries)

    def _handle(self, entries: list[list[Any]]) -> None:
        for e in entries:
            aid, name, args = command(e)
            if aid > self.aid:
                self.aid = aid
            if name == "c" and len(e[1]) > 1:
                self.sid = e[1][1]
            elif name == "S" and len(e[1]) > 1:
                self.gsession = e[1][1]
            elif name and name not in ("noop",):
                try:
                    self.on_command(name, args)
                except Exception:  # noqa: BLE001
                    log.exception("lounge command %s", name)

    def run(self) -> None:
        """Bind and poll for as long as it runs, binding again after errors (with a pause)."""
        delay = 2
        while not self.stopping:
            try:
                if not self.sid:
                    self.bind()
                    log.info("lounge: bound as %s", self.name)
                self.poll_once()
                delay = 2
            except (requests.RequestException, RuntimeError, ValueError) as err:
                log.warning("lounge: %s; again in %d s", type(err).__name__, delay)
                self.sid = ""
                time.sleep(delay)
                delay = min(60, delay * 2)


# ------------------------------------------------------------------ DIAL: found and launched on the network
def device_xml(name: str, udn: str) -> str:
    return (
        '<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><specVersion><major>1</major><minor>0</minor></specVersion>'
        "<device><deviceType>urn:dial-multiscreen-org:device:dial:1</deviceType>"
        f"<friendlyName>{_x(name)}</friendlyName><manufacturer>Couchbox</manufacturer><modelName>Couchbox</modelName>"
        f"<UDN>uuid:{udn}</UDN></device></root>"
    )


def app_xml(running: bool, screen_id: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><service xmlns="urn:dial-multiscreen-org:schemas:dial" dialVer="1.7">'
        '<name>YouTube</name><options allowStop="true"/>'
        f"<state>{'running' if running else 'stopped'}</state>"
        + ('<link rel="run" href="run"/>' if running else "")
        + f"<additionalData><screenId>{_x(screen_id)}</screenId><theme>cl</theme></additionalData></service>"
    )


def ssdp_reply(location: str, udn: str) -> bytes:
    return (
        "HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nEXT:\r\n"
        f"LOCATION: {location}\r\nSERVER: Linux/6 UPnP/1.0 couchbox/1\r\nST: {DIAL_ST}\r\nUSN: uuid:{udn}::{DIAL_ST}\r\n"
        "BOOTID.UPNP.ORG: 1\r\nCONFIGID.UPNP.ORG: 1\r\n\r\n"
    ).encode()


def _x(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def local_ip(peer: str = "8.8.8.8") -> str:
    """This box's address on the network a peer would reach (no packet is sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((peer, 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Dial:
    """SSDP answers and the DIAL HTTP endpoints. running() says whether the app runs;
    launch(pairing_code) starts (or raises) it and pairs the phone."""

    def __init__(
        self,
        name: str,
        udn: str,
        screen_id: Callable[[], str],
        running: Callable[[], bool],
        launch: Callable[[dict[str, str]], None],
        stop: Callable[[], None],
        port: int = HTTP_PORT,
    ):
        self.name, self.udn, self.port = name, udn, port
        self.screen_id, self.running, self.launch, self.stop = screen_id, running, launch, stop

    def serve_ssdp(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)  # VacuumTube may be listening too
        sock.bind(("", SSDP_PORT))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, struct.pack("4sl", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY))
        while True:
            data, addr = sock.recvfrom(4096)
            msg = data.decode("utf-8", "replace")
            if not msg.startswith("M-SEARCH") or (DIAL_ST not in msg and "ssdp:all" not in msg):
                continue
            loc = f"http://{local_ip(addr[0])}:{self.port}/dd.xml"
            try:
                sock.sendto(ssdp_reply(loc, self.udn), addr)
            except OSError:
                pass

    def serve_http(self) -> None:
        dial = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body="", ctype="text/xml; charset=utf-8", headers=None):
                data = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Access-Control-Allow-Origin", "*")
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                host = self.headers.get("Host") or f"{local_ip()}:{dial.port}"
                if self.path.startswith("/dd.xml"):
                    self._send(200, device_xml(dial.name, dial.udn), headers={"Application-URL": f"http://{host}/apps/"})
                elif self.path.startswith("/apps/YouTube"):
                    self._send(200, app_xml(dial.running(), dial.screen_id()))
                else:
                    self._send(404)

            def do_POST(self):
                if not self.path.startswith("/apps/YouTube"):
                    self._send(404)
                    return
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n).decode("utf-8", "replace") if n else ""
                params = {k: v[0] for k, v in parse_qs(body).items()}
                was = dial.running()
                threading.Thread(target=dial.launch, args=(params,), daemon=True).start()
                host = self.headers.get("Host") or f"{local_ip()}:{dial.port}"
                self._send(200 if was else 201, "", headers={"Location": f"http://{host}/apps/YouTube/run"})

            def do_DELETE(self):
                if self.path.startswith("/apps/YouTube"):
                    threading.Thread(target=dial.stop, daemon=True).start()
                    self._send(200)
                else:
                    self._send(404)

        ThreadingHTTPServer(("", self.port), Handler).serve_forever()
