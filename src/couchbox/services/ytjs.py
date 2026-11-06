"""YouTube's JavaScript challenges (the "n" and signature functions in its player JS) solved in one
JavaScript process that stays up, as YouTube's own TV app keeps its player loaded: the player is
read once per player version and its solver functions kept, so each video's challenges are a
function call (milliseconds) instead of a new process reading the whole player again (1.7 s on
the Pi with node).

The runtime: QuickJS (qjs, the quickjs package) when it's there, else node. QuickJS holds the
solver in a few tens of MB where node took ~95. Reading a new player version takes it ~4 s
here (node ~0.4), once: that reading is kept (a file per version) and loads in ~0.5 s.

It's a yt-dlp challenge provider (yt-dlp's JCP plugin interface) built on yt-dlp's own EJS
scripts: the same solver code as yt-dlp's providers, which stay registered as the fallback
(chosen when this one can't run or errors). register() adds it, after yt-dlp is imported (the
stream worker, ytworker, does). node runs with --permission (no files, no network: only its
stdin and stdout); QuickJS has its std and os modules (as yt-dlp runs it: the player is
YouTube's own), which the bootstrap keeps from the global scope.
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
# QuickJS (qjs --std): the same, reading lines with std (kept in this function, out of the global
# scope the player's code runs in)
BOOT_QJS = (
    "(() => { const IN = std.in, OUT = std.out, parse = JSON.parse; delete globalThis.std; delete globalThis.os;"
    " let h = null, l; while ((l = IN.getline()) !== null) { if (!h) { h = (0, eval)(parse(l)); continue; } h(l); OUT.flush(); } })()"
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
        if (typeof gc === "function") gc();   // the parse's garbage: back to a small size (node --expose-gc)
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


def _reap(proc) -> None:
    try:
        proc.wait(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _is_qjs(path: str) -> bool:
    return os.path.basename(path).startswith(("qjs", "quickjs"))


class Node:
    """The solver process (one, shared; node or QuickJS by its path): started on first use, again
    if it died, and stopped after IDLE seconds unused (node ~95 MB: 30 s; QuickJS, small and
    slower to start: 10 min). A new one starts from the kept reading of the player, usually while
    a card has the focus, before OK."""

    lock = threading.Lock()
    proc: subprocess.Popen | None = None
    path = ""
    n = 0
    sandbox = True  # (bubblewrap, while it works here)
    stats: dict[str, Any] = {"runtime": "", "sandboxed": False, "starts": 0, "solves": 0, "readings": 0}
    used = 0.0
    IDLE = {"node": 30, "quickjs": 600}
    watcher: threading.Thread | None = None

    @classmethod
    def _watch(cls) -> None:
        import time

        while True:
            time.sleep(15)
            with cls.lock:
                idle = cls.IDLE["quickjs" if _is_qjs(cls.path) else "node"]
                if cls.proc is not None and cls.proc.poll() is None and time.monotonic() - cls.used > idle:
                    cls.proc.kill()
                    _reap(cls.proc)
                    cls.proc = None

    @classmethod
    def recycle(cls) -> None:
        """Stop it (the next ask starts a fresh one)."""
        with cls.lock:
            if cls.proc is not None:
                cls.proc.kill()
                _reap(cls.proc)
                cls.proc = None

    @classmethod
    def ask(cls, path: str, script: str, req: dict[str, Any]) -> dict[str, Any]:
        import time

        with cls.lock:
            cls.used = time.monotonic()
            if cls.watcher is None:
                cls.watcher = threading.Thread(target=cls._watch, daemon=True)
                cls.watcher.start()
            if cls.proc is not None and cls.path != path:  # (another runtime asked: one at a time)
                cls.proc.kill()
                _reap(cls.proc)
                cls.proc = None
            fresh = cls.proc is None or cls.proc.poll() is not None
            if fresh:
                cls._start(path, script)
            cls.stats["solves"] += 1
            if req.get("player"):
                cls.stats["readings"] += 1
            try:
                return cls._ask(req)
            except SolverError:
                if not (fresh and cls.stats.get("sandboxed")):
                    raise
                # the sandbox didn't let it run (no user namespaces here?): without it, said once
                import sys

                print(f"ytjs: {path} wouldn't run in bubblewrap here: running it without", file=sys.stderr, flush=True)
                cls.sandbox = False
                cls._start(path, script)
                return cls._ask(req)

    @classmethod
    def _start(cls, path: str, script: str) -> None:
        import sys

        if _is_qjs(path):  # QuickJS reaches files and programs (its std and os modules): in a sandbox
            cmd = [path, "--std", "-e", BOOT_QJS]
            box = sandboxed(cmd) if cls.sandbox else None
            if box is None and cls.sandbox:
                print(f"ytjs: no {BWRAP}: QuickJS runs without a sandbox", file=sys.stderr, flush=True)
                cls.sandbox = False
            cmd = box or cmd
        else:  # node: its own --permission (no files, programs or network)
            cmd = [path, "--permission", "--expose-gc", "--max-old-space-size=192", "-e", BOOT_JS]
        cls.proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        cls.path = path
        cls.stats.update(runtime="quickjs" if _is_qjs(path) else "node", sandboxed=cmd[0] == BWRAP, pid=cls.proc.pid)
        cls.stats["starts"] += 1
        try:
            cls.proc.stdin.write(json.dumps(script) + "\n")
        except OSError:
            pass

    @classmethod
    def _ask(cls, req: dict[str, Any]) -> dict[str, Any]:
        """(cls.lock held)"""
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
            _reap(cls.proc)
            cls.proc = None
            raise SolverError(f"the challenge solver failed: {err}") from err

    @classmethod
    def status(cls) -> dict[str, Any]:
        """Which runtime solves, how often, and its memory now (MB; 0: not running)."""
        rss = 0
        if cls.proc is not None and cls.proc.poll() is None:
            todo = [cls.proc.pid]  # (in the sandbox: bwrap, and the runtime under it)
            while todo:
                pid = todo.pop()
                try:
                    with open(f"/proc/{pid}/status") as fh:
                        rss += next((int(ln.split()[1]) for ln in fh if ln.startswith("VmRSS:")), 0) // 1024
                    with open(f"/proc/{pid}/task/{pid}/children") as fh:
                        todo += [int(x) for x in fh.read().split()]
                except (OSError, ValueError):
                    pass
        return dict(cls.stats, alive=bool(rss), rss=rss)


BWRAP = "/usr/bin/bwrap"


def sandboxed(cmd: list[str]) -> list[str] | None:
    """cmd in a bubblewrap sandbox: no network or other namespaces shared, nothing of the system
    but the program and its libraries (read-only), no home, an empty /tmp, gone with its parent.
    None without bwrap."""
    if not os.access(BWRAP, os.X_OK):
        return None
    prog = os.path.realpath(cmd[0])
    paths = {prog}
    try:
        out = subprocess.run(["ldd", prog], capture_output=True, text=True, timeout=5).stdout  # noqa: S607
    except (OSError, subprocess.SubprocessError):
        return None
    for ln in out.splitlines():
        for part in ln.split():
            if part.startswith("/"):
                # the file where the loader looks for it (its folder's links followed: /lib/x ->
                # /usr/lib/x, itself maybe a link), and what it finally is
                paths.add(os.path.join(os.path.realpath(os.path.dirname(part)), os.path.basename(part)))
                paths.add(os.path.realpath(part))
    args = [
        BWRAP,
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
    ]
    for link in ("/lib", "/lib64", "/bin", "/sbin"):  # (merged /usr: the loader's paths go through these)
        if os.path.islink(link):
            args += ["--symlink", os.readlink(link), link]
    for p in sorted(paths):
        if os.path.exists(p) and not any(p.startswith(link + "/") for link in ("/lib", "/lib64", "/bin", "/sbin") if os.path.islink(link)):
            args += ["--ro-bind", p, p]
    return args + [prog, *cmd[1:]]


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
    # reading a new version: node does it in ~0.4 s (QuickJS ~4 s here, ~3x that on the Pi), when
    # it's there; then QuickJS goes on from the copy
    reader = path
    if _is_qjs(path):
        from couchbox.services import ytstream

        reader = (ytstream.js_runtimes().get("node") or {}).get("path") or path
    out = Node.ask(reader, script, dict(body, player=player_text()))
    prepared = out.pop("prepared", None)
    if prepared:
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            for old in sorted(f.parent.glob("*.js"), key=lambda x: x.stat().st_mtime)[:-1]:
                old.unlink()  # the newest other version is enough
            tmp = f.with_suffix(".tmp")
            tmp.write_text(prepared)
            tmp.replace(f)
            Node.recycle()  # reading the whole player left it big (QuickJS 198 MB): from the copy it's 44
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
    """The runtime for the app's own solving: QuickJS first (small), else node."""
    from couchbox.services import ytstream

    rts = ytstream.js_runtimes()
    rt = rts.get("quickjs") or rts.get("node")
    if not rt:
        raise SolverError("no QuickJS or node on this box")
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
        from yt_dlp.extractor.youtube.jsc._builtin.quickjs import QuickJSJCP
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

    class Kept:
        """The provider's solving, on the process kept running (either runtime)."""

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
                self.logger.info(f"Solving JS challenges using {self.JS_RUNTIME_NAME} (kept running)")
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

    @register_provider
    class CouchboxQuickJSJCP(Kept, QuickJSJCP):
        PROVIDER_NAME = "couchbox-quickjs"

    @register_provider
    class CouchboxNodeJCP(Kept, NodeJCP):
        PROVIDER_NAME = "couchbox-node"

    # (yt-dlp adds up every preference that applies, its own classes' too: node 900, QuickJS 850)
    @register_preference(CouchboxQuickJSJCP)
    def _preference_qjs(provider, requests) -> int:
        return 2000  # first: small

    @register_preference(CouchboxNodeJCP)
    def _preference_node(provider, requests) -> int:
        return 1000

    _registered = True
    return True
