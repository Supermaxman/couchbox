"""YouTube's JavaScript challenges (the "n" and signature functions in its player JS) solved in one
node process that stays up, as YouTube's own TV app keeps its player loaded: the player is read
once per player version and its solver functions kept, so each video's challenges are a function
call (milliseconds) instead of a new node reading the whole player again (1.7 s on the Pi).

It's a yt-dlp challenge provider (yt-dlp's JCP plugin interface) built on yt-dlp's own EJS
scripts: the same solver code as yt-dlp's node provider, which stays registered as the fallback
(chosen when this one can't run or errors). register() adds it, after yt-dlp is imported (the
stream worker, ytworker, does). The node process runs with --permission: no files, no network,
only its stdin and stdout.
"""

import json
import os
import subprocess
import threading
from typing import Any

# The server, after yt-dlp's lib and core scripts: one JSON request a line, one answer a line.
# {"id", "player_url", "player"?, "requests": [{type: "n"|"sig", challenges: [...]}]}
# The node side: a bootstrap reads its first stdin line (JSON: yt-dlp's lib and core scripts and
# HANDLER, too long for an argument), evaluates it to a function, and passes it each later line.
BOOT_JS = (
    'const rl = require("node:readline").createInterface({input: process.stdin, terminal: false}); let h = null;'
    "rl.on('line', l => { if (!h) { h = (0, eval)(JSON.parse(l)); return; } h(l); });"
)
# one request a line: {"id", "player_url", "player"?, "requests": [{type: "n"|"sig", challenges}]}
HANDLER_JS = r"""
;(() => {
  const solvers = new Map();
  return line => {
    let req;
    try { req = JSON.parse(line); } catch (e) { return; }
    const out = {id: req.id};
    try {
      let s = solvers.get(req.player_url);
      if (!s && !req.player && !req.prepared) { out.need_player = true; console.log(JSON.stringify(out)); return; }
      if (!s) {
        // the player read into its solver functions (the slow part: parsing ~2.5 MB of JS), or
        // the copy of that from before (prepared: a file the app keeps per player version)
        const prepared = req.prepared || jsc({type: "player", player: req.player, requests: [], output_preprocessed: true}).preprocessed_player;
        s = {n: null, sig: null};
        Function("_result", prepared)(s);
        if (solvers.size > 1) solvers.delete(solvers.keys().next().value);
        solvers.set(req.player_url, s);
        if (!req.prepared) out.prepared = prepared;
        if (global.gc) global.gc();          // the parse's garbage: node back to a small size
      }
      out.responses = req.requests.map(r => {
        const f = s[r.type];
        if (!f) return {type: "error", error: `Failed to extract ${r.type} function`};
        try { return {type: "result", data: Object.fromEntries(r.challenges.map(c => [c, f(c)]))}; }
        catch (e) { return {type: "error", error: String(e && e.message || e)}; }
      });
    } catch (e) { out.error = String(e && e.message || e); }
    console.log(JSON.stringify(out));
  };
})()
"""


class SolverError(RuntimeError):
    pass


class Node:
    """The node process (one, shared): started on first use, again if it died, and stopped after
    IDLE seconds unused (~95 MB; a new one starts from the kept reading of the player: ~0.5 s,
    usually while a card has the focus, before OK)."""

    lock = threading.Lock()
    proc: subprocess.Popen | None = None
    n = 0
    used = 0.0
    IDLE = 30
    watcher: threading.Thread | None = None

    @classmethod
    def _watch(cls) -> None:
        import time

        while True:
            time.sleep(30)
            with cls.lock:
                if cls.proc is not None and cls.proc.poll() is None and time.monotonic() - cls.used > cls.IDLE:
                    cls.proc.kill()
                    cls.proc = None

    @classmethod
    def ask(cls, path: str, script: str, req: dict[str, Any]) -> dict[str, Any]:
        import time

        with cls.lock:
            cls.used = time.monotonic()
            if cls.watcher is None:
                cls.watcher = threading.Thread(target=cls._watch, daemon=True)
                cls.watcher.start()
            if cls.proc is None or cls.proc.poll() is not None:
                cls.proc = subprocess.Popen(  # noqa: S603
                    [path, "--permission", "--expose-gc", "--max-old-space-size=192", "-e", BOOT_JS],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                cls.proc.stdin.write(json.dumps(script) + "\n")
            cls.n += 1
            req = dict(req, id=cls.n)
            try:
                cls.proc.stdin.write(json.dumps(req) + "\n")
                cls.proc.stdin.flush()
                while True:
                    line = cls.proc.stdout.readline()
                    if not line:
                        raise SolverError("the challenge solver stopped")
                    out = json.loads(line)
                    if out.get("id") == req["id"]:
                        return out
            except (OSError, ValueError) as err:
                cls.proc.kill()
                cls.proc = None
                raise SolverError(f"the challenge solver failed: {err}") from err


def _prepared_file(player_url: str):
    import hashlib
    from pathlib import Path

    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "couchbox-yt" / "jsc"
    return base / (hashlib.sha256(player_url.encode()).hexdigest()[:24] + ".js")


def ask_with_player(path: str, script: str, body: dict[str, Any], player_text) -> dict[str, Any]:
    """Node's answer to body, giving it the player when it hasn't read this version yet: the copy
    of it read before (a file per version, kept here, as the app's), else the player itself
    (player_text()), whose reading is then kept for next time."""
    out = Node.ask(path, script, body)
    if not out.get("need_player"):
        return out
    f = _prepared_file(body["player_url"])
    try:
        out = Node.ask(path, script, dict(body, prepared=f.read_text()))
        if not out.get("error"):
            return out
    except OSError:
        pass
    out = Node.ask(path, script, dict(body, player=player_text()))
    prepared = out.pop("prepared", None)
    if prepared:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            for old in sorted(f.parent.glob("*.js"), key=lambda x: x.stat().st_mtime)[:-1]:
                old.unlink()  # the newest other version is enough
            tmp = f.with_suffix(".tmp")
            tmp.write_text(prepared)
            tmp.replace(f)
        except OSError:
            pass
    return out


def server_script(lib: str, core: str) -> str:
    return f"{lib}\nObject.assign(globalThis, lib);\n{core}\n{HANDLER_JS}"


# ------------------------------------------------------------------ without yt-dlp's extractor
# (couchbox-yt's own /player calls, signed in: ytworker.signed_info)
_script = ""
PLAYER_URL = "https://www.youtube.com/s/player/{}/player_ias.vflset/en_US/base.js"  # yt-dlp's "main" variant
_player: dict[str, Any] = {}  # {"ver", "sts", "js", "until"}


def node_path() -> str:
    from couchbox.services import ytstream

    rt = ytstream.js_runtimes().get("node")
    if not rt:
        raise SolverError("no node on this box")
    return rt["path"]


def current_player(session: Any = None) -> dict[str, Any]:
    """The current player JS: {ver, sts, url}, looked at again after an hour (its version from
    iframe_api, ~50 kB; its signatureTimestamp kept per version, so the ~2.5 MB player itself is
    only fetched when it's new: player_js())."""
    import re
    import time

    import requests

    if _player.get("until", 0) > time.time():
        return _player
    s = session or requests.Session()
    page = s.get("https://www.youtube.com/iframe_api", timeout=(8, 20)).text
    ver = re.search(r"player\\?/([0-9a-fA-F]{8})\\?/", page)
    if not ver:
        raise SolverError("no player version in iframe_api")
    if _player.get("ver") != ver.group(1):
        _player.clear()
        _player.update(ver=ver.group(1), url=PLAYER_URL.format(ver.group(1)))
        known = _read_sts()
        if ver.group(1) in known:
            _player["sts"] = known[ver.group(1)]
        else:
            js = player_js(_player, s)
            m = re.search(r"(?:signatureTimestamp|sts)\s*:\s*(\d{5})", js)
            _player["sts"] = int(m.group(1)) if m else 0
            if _player["sts"]:
                _write_sts({**{k: v for k, v in list(known.items())[-3:]}, ver.group(1): _player["sts"]})
    _player["until"] = time.time() + 3600
    return _player


def player_js(p: dict[str, Any], session: Any = None) -> str:
    """The player's JavaScript (fetched once per version, while it's needed)."""
    import requests

    if not p.get("js"):
        p["js"] = (session or requests.Session()).get(p["url"], timeout=(8, 30)).text
    return p["js"]


def _sts_file():
    return _prepared_file("sts").with_name("sts.json")


def _read_sts() -> dict[str, int]:
    try:
        return json.loads(_sts_file().read_text())
    except (OSError, ValueError):
        return {}


def _write_sts(d: dict[str, int]) -> None:
    try:
        f = _sts_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d))
    except OSError:
        pass


def prepare() -> None:
    """Node up, with the current player read (from the copy if there is one): the app's start."""
    try:
        solve(["warmup"], [])
    except SolverError:
        pass


def solve(n: list[str], sig: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """({n challenge: answer}, {signature: answer}) with the current player, on the kept node."""
    global _script
    if not _script:
        import yt_dlp_ejs.yt.solver as ejs

        _script = server_script(ejs.lib(), ejs.core())
    p = current_player()
    reqs = [r for r in ({"type": "n", "challenges": sorted(set(n))}, {"type": "sig", "challenges": sorted(set(sig))}) if r["challenges"]]
    if not reqs:
        return {}, {}
    body = {"player_url": p["url"], "requests": reqs}
    out = ask_with_player(node_path(), _script, body, lambda: player_js(p))
    if out.get("error"):
        raise SolverError(out["error"])
    got: dict[str, dict[str, str]] = {"n": {}, "sig": {}}
    for r, data in zip(reqs, out["responses"], strict=True):
        if data["type"] == "error":
            raise SolverError(f"{r['type']}: {data['error']}")
        got[r["type"]] = data["data"]
    p.pop("js", None)  # (read: node keeps what it needs)
    return got["n"], got["sig"]


_registered = False


def register() -> bool:
    """Add the provider to yt-dlp (already imported). False if this yt-dlp has no EJS providers."""
    global _registered
    if _registered:
        return True
    try:
        from yt_dlp.extractor.youtube.jsc._builtin.node import NodeJCP
        from yt_dlp.extractor.youtube.jsc.provider import (
            JsChallengeProviderError,
            JsChallengeProviderResponse,
            JsChallengeResponse,
            JsChallengeType,
            NChallengeOutput,
            SigChallengeOutput,
            register_preference,
            register_provider,
        )
    except ImportError:
        return False

    @register_provider
    class CouchboxNodeJCP(NodeJCP):
        PROVIDER_NAME = "couchbox-node"

        def _script(self) -> str:
            if not hasattr(self, "_server"):
                self._server = server_script(self._lib_script.code, self._core_script.code)
            return self._server

        def _real_bulk_solve(self, /, requests):
            grouped: dict[str, list] = {}
            for r in requests:
                grouped.setdefault(r.input.player_url, []).append(r)
            for player_url, group in grouped.items():
                body = {"player_url": player_url, "requests": [{"type": r.type.value, "challenges": r.input.challenges} for r in group]}
                self.logger.info("Solving JS challenges using node (kept running)")
                try:
                    vid = next((r.video_id for r in group), None)
                    out = ask_with_player(self.runtime_info.path, self._script(), body, lambda: self._get_player(vid, player_url))
                except SolverError as err:
                    raise JsChallengeProviderError(str(err)) from err
                if out.get("error"):
                    raise JsChallengeProviderError(out["error"])
                for r, data in zip(group, out["responses"], strict=True):
                    if data["type"] == "error":
                        yield JsChallengeProviderResponse(r, None, data["error"])
                    else:
                        result = NChallengeOutput(data["data"]) if r.type is JsChallengeType.N else SigChallengeOutput(data["data"])
                        yield JsChallengeProviderResponse(r, JsChallengeResponse(r.type, result))

    @register_preference(CouchboxNodeJCP)
    def _preference(provider, requests) -> int:
        return 1000  # before yt-dlp's own node provider (900)

    _registered = True
    return True
