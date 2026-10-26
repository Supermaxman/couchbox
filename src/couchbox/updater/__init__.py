"""couchbox-updater: signed releases from GitHub Releases, installed when nobody's watching.

    check()    newest release for the channel, newer than this one (or None)
    download() fetch, verify the signed manifest and every asset's SHA-256
    run()      the timer's job: check, download, then install now (automatic and idle) or
               mark "available" (manual)
    install()  apt-get install the debs, health-check, roll back on failure
    rollback() reinstall the kept previous version

Design: docs/design/updates-and-releases.md. State: /var/lib/couchbox/state/update.json.
"""

import datetime as dt
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from couchbox import __version__, paths, settings
from couchbox.system import sh

log = logging.getLogger("couchbox.updater")

NAMESPACE = "couchbox-release"
SIGNER = "release@couchbox"
UA = f"couchbox-updater/{__version__}"
MANIFEST = "release.json"


class UpdateError(RuntimeError):
    pass


# ------------------------------------------------------------------ versions
_SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


@dataclass(frozen=True, order=False)
class Version:
    major: int
    minor: int
    patch: int
    pre: tuple = ()

    @classmethod
    def parse(cls, s: str) -> "Version":
        m = _SEMVER.match(s.strip())
        if not m:
            raise ValueError(f"not a version: {s}")
        pre = tuple(int(p) if p.isdigit() else p for p in m.group(4).split(".")) if m.group(4) else ()
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)

    def _key(self):
        # a release sorts after its prereleases; numeric pre parts before text parts
        pre = tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in self.pre)
        return (self.major, self.minor, self.patch, 1 if not self.pre else 0, pre)

    def __lt__(self, o: "Version") -> bool:
        return self._key() < o._key()

    def __le__(self, o: "Version") -> bool:
        return self._key() <= o._key()

    def __gt__(self, o: "Version") -> bool:
        return self._key() > o._key()

    def __ge__(self, o: "Version") -> bool:
        return self._key() >= o._key()

    @property
    def prerelease(self) -> bool:
        return bool(self.pre)

    def __str__(self) -> str:
        s = f"{self.major}.{self.minor}.{self.patch}"
        return s + ("-" + ".".join(map(str, self.pre)) if self.pre else "")


def current() -> Version:
    return Version.parse(__version__)


# ------------------------------------------------------------------ state
def state_file() -> Path:
    return paths.state() / "state/update.json"


def updates_dir() -> Path:
    return paths.state() / "updates"


def load_state() -> dict[str, Any]:
    try:
        return json.loads(state_file().read_text())
    except (OSError, ValueError):
        return {"bad": [], "history": []}


def save_state(st: dict[str, Any]) -> None:
    f = state_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2) + "\n")
    os.replace(tmp, f)


def _record(st: dict[str, Any], event: str, **kw: Any) -> None:
    st.setdefault("history", []).append({"t": time.time(), "event": event, **kw})
    st["history"] = st["history"][-50:]


# ------------------------------------------------------------------ network
def _get(url: str, timeout: float = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/octet-stream, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _download(url: str, dest: Path, size: int | None = None) -> None:
    """Resumable download to dest (a .part file is kept between tries)."""
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": UA}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        mode = "ab" if have and r.status == 206 else "wb"
        with open(part, mode) as f:
            shutil.copyfileobj(r, f, 1 << 20)
    if size is not None and part.stat().st_size != size:
        raise UpdateError(f"{dest.name}: got {part.stat().st_size} bytes, expected {size}")
    os.replace(part, dest)


def base_url(source: str) -> str:
    return os.environ.get("COUCHBOX_RELEASES_URL", f"https://github.com/{source}/releases")


def candidates(channel: str, source: str) -> list[tuple[Version, str]]:
    """(version, download base URL) of releases on this channel, newest first."""
    base = base_url(source)
    if channel == "stable" and "COUCHBOX_RELEASES_URL" not in os.environ:
        # one redirect, no API rate limit
        try:
            m = json.loads(_get(f"{base}/latest/download/{MANIFEST}"))
            return [(Version.parse(m["version"]), f"{base}/download/v{m['version']}")]
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            # the newest release is tagged but its files aren't attached yet (~15 min): list the
            # releases instead; check() skips the unfinished one
            log.info("the latest release is still being published: looking at the ones before it")
    if "COUCHBOX_RELEASES_URL" in os.environ:
        idx = json.loads(_get(f"{base}/index.json"))  # test servers: [{"tag": "v0.2.0", "prerelease": false}]
    else:
        idx = json.loads(_get(f"https://api.github.com/repos/{source}/releases?per_page=15"))
        idx = [{"tag": r["tag_name"], "prerelease": r["prerelease"], "draft": r.get("draft")} for r in idx]
    out = []
    for r in idx:
        if r.get("draft"):
            continue
        try:
            v = Version.parse(r["tag"])
        except ValueError:
            continue
        if v.prerelease and channel != "beta":
            continue
        out.append((v, f"{base}/download/{r['tag']}"))
    return sorted(out, key=lambda x: x[0]._key(), reverse=True)


# ------------------------------------------------------------------ verification
def allowed_signers() -> Path:
    return Path(os.environ.get("COUCHBOX_ALLOWED_SIGNERS", str(paths.share() / "keys/allowed_signers")))


def verify_manifest(data: bytes, sig: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as d:
        sf = Path(d) / "release.json.sig"
        sf.write_bytes(sig)
        r = subprocess.run(
            ["ssh-keygen", "-Y", "verify", "-f", str(allowed_signers()), "-I", SIGNER, "-n", NAMESPACE, "-s", str(sf)],
            input=data,
            capture_output=True,
        )
    if r.returncode != 0:
        raise UpdateError("The update's signature doesn't match Couchbox's release key.")
    m = json.loads(data)
    if m.get("schema") != 1 or "version" not in m or "assets" not in m:
        raise UpdateError("The update's manifest isn't one this version understands.")
    return m


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ check and download
def check(st: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """The newest installable release manifest (verified), or None."""
    s = settings.load()
    st = st if st is not None else load_state()
    me = current()
    for v, url in candidates(s["updates.channel"], s["updates.source"]):
        if v <= me or str(v) in st.get("bad", []):
            continue
        try:
            m = verify_manifest(_get(f"{url}/{MANIFEST}"), _get(f"{url}/{MANIFEST}.sig"))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            log.info("%s is still being published (no %s yet): skipped for now", v, MANIFEST)
            continue  # its files are attached ~15 min after the tag; an older one may be ready
        if Version.parse(m["version"]) != v:
            raise UpdateError("The update's manifest is for another version.")
        if m.get("base", {}).get("version") and m["base"]["version"] != os_version():
            log.info("%s is for Ubuntu %s; this is %s: offered as a system upgrade only", v, m["base"]["version"], os_version())
            continue
        if m.get("min_from") and me < Version.parse(m["min_from"]):
            continue  # need an intermediate release first; an older candidate may be it
        m["_url"] = url
        return m
    return None


def os_version() -> str:
    try:
        for line in (paths.root() / "etc/os-release").read_text().splitlines():
            if line.startswith("VERSION_ID="):
                return line.split("=", 1)[1].strip('"')
    except OSError:
        pass
    return ""


def wanted_assets(m: dict[str, Any]) -> list[str]:
    names = [n for n in m["assets"] if n.endswith(".deb")]
    have_media = (paths.root() / "var/lib/dpkg/info/couchbox-media.list").exists()
    return [n for n in names if not n.startswith("couchbox-media_") or have_media]


def download(m: dict[str, Any]) -> Path:
    d = updates_dir() / m["version"]
    d.mkdir(parents=True, exist_ok=True)
    for name in wanted_assets(m):
        a = m["assets"][name]
        f = d / name
        if not f.exists() or sha256(f) != a["sha256"]:
            _download(f"{m['_url']}/{name}", f, a.get("size"))
        if sha256(f) != a["sha256"]:
            f.unlink(missing_ok=True)
            raise UpdateError(f"{name} doesn't match the signed manifest.")
    (d / MANIFEST).write_text(json.dumps({k: v for k, v in m.items() if k != "_url"}, indent=2))
    return d


# ------------------------------------------------------------------ when to install
def _in_window(window: str, now: dt.datetime) -> bool:
    a, b = window.split("-")
    start = dt.time(*map(int, a.split(":")))
    end = dt.time(*map(int, b.split(":")))
    t = now.time()
    return start <= t < end if start <= end else (t >= start or t < end)


def idle_reason(
    s: dict[str, Any],
    st: dict[str, Any],
    now: dt.datetime | None = None,
    *,
    playing: bool | None = None,
    tv_on: bool | None = None,
    input_age: float | None = None,
) -> str:
    """ "" when it's a good time to install, else why not."""
    from couchbox import session

    now = now or dt.datetime.now()
    playing = session.anything_playing() if playing is None else playing
    if playing:
        return "something is playing"
    if tv_on is None:
        tv_on = tv_is_on()
    input_age = session.seconds_since_input() if input_age is None else input_age
    if tv_on and input_age < 30 * 60:
        return "the TV is in use"
    waiting_since = st.get("pending_since") or now.timestamp()
    if not _in_window(s["updates.window"], now) and now.timestamp() - waiting_since < 3 * 86400:
        return f"waiting for {s['updates.window']}"
    return ""


def tv_is_on() -> bool:
    r = sh(["/usr/lib/couchbox/bin/couchbox-tv", "status"], check=False, timeout=10)
    return "standby" not in r.stdout.lower() if r.returncode == 0 else True


# ------------------------------------------------------------------ install, health, rollback
def installed_debs() -> list[Path]:
    """The debs of the running version (kept for rollback), if we have them."""
    d = updates_dir() / __version__
    return sorted(d.glob("*.deb")) if d.is_dir() else []


def ensure_rollback_set() -> bool:
    """Keep the running version's debs (from its own signed release) so we can go back."""
    if installed_debs():
        return True
    s = settings.load()
    url = f"{base_url(s['updates.source'])}/download/v{__version__}"
    try:
        m = verify_manifest(_get(f"{url}/{MANIFEST}"), _get(f"{url}/{MANIFEST}.sig"))
        m["_url"] = url
        download(m)
        return True
    except (OSError, ValueError, UpdateError) as e:
        log.warning("can't keep %s for rollback: %s", __version__, e)
        return False


def _apt_install(debs: list[Path]) -> None:
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive", NEEDRESTART_MODE="a", COUCHBOX_UPDATING="1")
    r = subprocess.run(
        [
            "apt-get",
            "-o",
            "DPkg::Lock::Timeout=600",
            "-o",
            "Dpkg::Options::=--force-confold",
            "install",
            "-y",
            "--allow-downgrades",
            *map(str, debs),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=3600,
    )
    if r.returncode != 0:
        raise UpdateError("Installing failed: " + (r.stderr.strip().splitlines() or ["apt-get error"])[-1])


def health_check() -> list[str]:
    """Problems after an update (empty = healthy)."""
    r = sh(["/usr/bin/couchbox", "doctor", "--post-update", "--json"], check=False, timeout=240)
    try:
        d = json.loads(r.stdout)
        return [c["name"] + ": " + c.get("detail", "") for c in d.get("checks", []) if c.get("status") == "fail"]
    except ValueError:
        return [f"doctor didn't answer ({r.returncode})"]


def install(m: dict[str, Any] | None = None, *, version: str | None = None, check_health: bool = True) -> dict[str, Any]:
    st = load_state()
    if m is None:
        d = updates_dir() / (version or st.get("available", ""))
        m = json.loads((d / MANIFEST).read_text())
    d = updates_dir() / m["version"]
    debs = [d / n for n in wanted_assets(m)]
    for f in debs:
        if not f.exists() or sha256(f) != m["assets"][f.name]["sha256"]:
            raise UpdateError(f"{f.name} is missing or changed since it was verified.")
    from_v = __version__
    ensure_rollback_set()
    if paths.settings_file().exists():
        shutil.copy2(paths.settings_file(), paths.state() / "state/settings.before-update.json")
    st.update(installing={"from": from_v, "to": m["version"], "t": time.time()})
    save_state(st)
    _apt_install(debs)
    problems = health_check() if check_health else []
    st = load_state()
    st.pop("installing", None)
    if problems:
        _record(st, "failed", version=m["version"], problems=problems)
        st.setdefault("bad", []).append(m["version"])
        save_state(st)
        rollback(reason="health check: " + "; ".join(problems[:3]), to=from_v)
        raise UpdateError(f"{m['version']} failed its checks and was rolled back.")
    _record(st, "installed", version=m["version"], **{"from": from_v})
    st.pop("available", None)
    st.pop("pending_since", None)
    st["just_updated"] = {"version": m["version"], "notes_md": m.get("notes_md", "")}
    save_state(st)
    _prune(keep={m["version"], from_v})
    return st


def rollback(reason: str = "requested", to: str | None = None) -> dict[str, Any]:
    st = load_state()
    if to is None:
        hist = [h for h in st.get("history", []) if h["event"] == "installed"]
        to = hist[-1].get("from") if hist else None
    if not to:
        raise UpdateError("There's no earlier version kept to go back to.")
    d = updates_dir() / to
    debs = sorted(d.glob("*.deb"))
    if not debs:
        raise UpdateError(f"Version {to} isn't kept on this box any more.")
    _apt_install(debs)
    before = paths.state() / "state/settings.before-update.json"
    if before.exists():
        shutil.copy2(before, paths.settings_file())
        settings.write_env()
    st = load_state()
    _record(st, "rolled_back", to=to, reason=reason)
    save_state(st)
    return st


def _prune(keep: set[str]) -> None:
    for d in updates_dir().iterdir():
        if d.is_dir() and d.name not in keep:
            shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ the timer's job
def run(force_install: bool = False) -> dict[str, Any]:
    s = settings.load()
    st = load_state()
    st["last_check"] = time.time()
    try:
        m = check(st)
    except (OSError, urllib.error.URLError, UpdateError, ValueError) as e:
        st["last_error"] = str(e)
        save_state(st)
        log.warning("check failed: %s", e)
        return st
    st.pop("last_error", None)
    if not m:
        st.pop("available", None)
        save_state(st)
        return st
    download(m)
    if st.get("available") != m["version"]:
        st["available"] = m["version"]
        st["available_notes_md"] = m.get("notes_md", "")
        st["pending_since"] = time.time()
    save_state(st)
    if s["updates.mode"] != "automatic" and not force_install:
        return st
    why = "" if force_install else idle_reason(s, st)
    if why:
        st["waiting"] = why
        save_state(st)
        return st
    st.pop("waiting", None)
    save_state(st)
    return install(json.loads((updates_dir() / m["version"] / MANIFEST).read_text()))


def status() -> dict[str, Any]:
    s = settings.load()
    st = load_state()
    return {
        "version": __version__,
        "channel": s["updates.channel"],
        "mode": s["updates.mode"],
        "available": st.get("available"),
        "notes_md": st.get("available_notes_md", ""),
        "waiting": st.get("waiting"),
        "last_check": st.get("last_check"),
        "last_error": st.get("last_error"),
        "history": st.get("history", [])[-10:],
        "can_rollback": any(h["event"] == "installed" for h in st.get("history", [])),
        "just_updated": st.get("just_updated"),
    }
