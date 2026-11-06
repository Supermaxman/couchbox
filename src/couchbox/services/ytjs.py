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
      if (!s && !req.player) { out.need_player = true; console.log(JSON.stringify(out)); return; }
      if (!s) {
        const prepared = jsc({type: "player", player: req.player, requests: [], output_preprocessed: true}).preprocessed_player;
        s = {n: null, sig: null};
        Function("_result", prepared)(s);
        if (solvers.size > 4) solvers.delete(solvers.keys().next().value);
        solvers.set(req.player_url, s);
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
    """The node process (one, shared): started on first use, again if it died."""

    lock = threading.Lock()
    proc: subprocess.Popen | None = None
    n = 0

    @classmethod
    def ask(cls, path: str, script: str, req: dict[str, Any]) -> dict[str, Any]:
        with cls.lock:
            if cls.proc is None or cls.proc.poll() is not None:
                cls.proc = subprocess.Popen(  # noqa: S603
                    [path, "--permission", "-e", BOOT_JS],
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
    """The current player JS: {ver, sts, url, js}, looked at again after an hour."""
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
        url = PLAYER_URL.format(ver.group(1))
        js = s.get(url, timeout=(8, 30)).text
        sts = re.search(r"(?:signatureTimestamp|sts)\s*:\s*(\d{5})", js)
        _player.update(ver=ver.group(1), url=url, js=js, sts=int(sts.group(1)) if sts else 0)
    _player["until"] = time.time() + 3600
    return _player


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
    out = Node.ask(node_path(), _script, body)
    if out.get("need_player"):
        out = Node.ask(node_path(), _script, dict(body, player=p["js"]))
    if out.get("error"):
        raise SolverError(out["error"])
    got: dict[str, dict[str, str]] = {"n": {}, "sig": {}}
    for r, data in zip(reqs, out["responses"], strict=True):
        if data["type"] == "error":
            raise SolverError(f"{r['type']}: {data['error']}")
        got[r["type"]] = data["data"]
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
                    out = Node.ask(self.runtime_info.path, self._script(), body)
                    if out.get("need_player"):  # a player version it hasn't read yet
                        player = self._get_player(next((r.video_id for r in group), None), player_url)
                        out = Node.ask(self.runtime_info.path, self._script(), dict(body, player=player))
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
