"""The TV home screen, built from the apps registry and settings.

build() writes everything the home screen reads:
  /var/lib/couchbox/home/home.json   the row (watched by the home QML: changes show at once)
  /var/lib/couchbox/home/tiles/*.png tile artwork (from share/tiles/*.svg)
  /usr/local/share/applications/couchbox-web-*.desktop   website launchers
  ~tv/.local/share/applications/<id>  renamed apps / extra launch arguments (same storage id)
  ~tv/.config/bigscreen-favs         Bigscreen's own favourites (its stock home screen)
and lays our QML over a copy of Bigscreen's home screen (overlay(), for the tested version).
"""

import json
import logging
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from couchbox import apps, paths, settings
from couchbox.system import sh

log = logging.getLogger("couchbox.home")

TESTED_BIGSCREEN = ("6.7.5",)
PLASMOID = "org.kde.bigscreen.homescreen"
STOCK = Path("/usr/share/plasma/plasmoids") / PLASMOID
# /usr/local/share comes before /usr/share in the session's XDG_DATA_DIRS, so Plasma prefers it.
LOCAL_SHARE = Path("/usr/local/share")
# YouTube opens DevTools on localhost for the voice assistant's tools.
EXTRA_ARGS = {"rocks.shy.VacuumTube.desktop": "--remote-debugging-port=9222"}


def home_dir() -> Path:
    return paths.state() / "home"


def _local_share() -> Path:
    return paths.root() / str(LOCAL_SHARE).lstrip("/")


def tv_home() -> Path:
    if os.environ.get("COUCHBOX_TV_HOME"):
        return Path(os.environ["COUCHBOX_TV_HOME"])
    try:
        return Path(pwd.getpwnam("tv").pw_dir)
    except KeyError:
        return paths.root() / "home/tv"


def _desktop_dirs() -> list[Path]:
    r = paths.root()
    return [r / "var/lib/flatpak/exports/share/applications", _local_share() / "applications", r / "usr/share/applications"]


def find_desktop(desktop_id: str) -> Path | None:
    for d in _desktop_dirs():
        if (d / desktop_id).is_file():
            return d / desktop_id
    return None


def desktop_field(text: str, key: str) -> str:
    section = ""
    for line in text.splitlines():
        if line.startswith("["):
            section = line.strip()
        elif section == "[Desktop Entry]" and line.split("=", 1)[0] == key:
            return line.split("=", 1)[1]
    return ""


def render_tile(tile: str) -> tuple[str, str]:
    """(png path, glow colour) for share/tiles/<tile>.svg, or ("", "")."""
    svg = paths.share() / "tiles" / f"{tile}.svg"
    if not tile or not svg.is_file():
        return "", ""
    out = home_dir() / "tiles" / f"{tile}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists() or out.stat().st_mtime < svg.stat().st_mtime:
        r = sh(["rsvg-convert", "-w", "800", "-h", "450", str(svg), "-o", str(out)], check=False)
        if r.returncode != 0:
            log.warning("tile %s: %s", tile, r.stderr.strip())
            return "", ""
    m = re.search(r'data-couchbox-glow="([^"]+)"', svg.read_text())
    return str(out), m.group(1) if m else ""


def web_launcher(app: apps.App, s: dict[str, Any]) -> str:
    ext = tv_home() / ".local/share/couchbox/web-extension"
    cache = s["apps.web_cache_mb"] * 1024 * 1024
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={app.name}",
            f"Comment={app.url}",
            f"Icon={app.icon or 'applications-internet'}",
            "Categories=AudioVideo;Video;",
            "Exec=flatpak run org.chromium.Chromium "
            f"--app={app.url} --start-fullscreen --class=couchbox-web-{app.id} --ozone-platform-hint=auto "
            f"--password-store=basic --disk-cache-size={cache} --autoplay-policy=no-user-gesture-required "
            "--no-default-browser-check --no-first-run --remote-debugging-port=9223 --enable-spatial-navigation "
            f"--load-extension={ext}",
            "",
        ]
    )


def row_json(s: dict[str, Any] | None = None) -> dict[str, Any]:
    """What home.json holds (no files touched besides tile PNGs)."""
    s = s or settings.load()
    d = settings.derived(s)
    out = []
    for a in apps.home_row(s):
        png, glow = render_tile(a.tile)
        out.append({"id": a.desktop, "app": a.id, "name": a.name, "icon": a.icon, "tile": png, "glow": glow, "hideable": a.hideable})
    w = None
    if d["weather"]:
        w = {"lat": s["location.lat"], "lon": s["location.lon"], "name": s["location.name"], "units": d["units"]}
    return {"apps": out, "weather": w, "clock24": d["clock24"], "units": d["units"]}


def _write(path: Path, text: str, owner: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    os.chmod(tmp, 0o644)
    if owner and os.geteuid() == 0:
        try:
            pw = pwd.getpwnam(owner)
            os.chown(tmp, pw.pw_uid, pw.pw_gid)
        except KeyError:
            pass  # no TV user (tests, image build before the package made it)
    os.replace(tmp, path)


def build(restart_shell: bool = False) -> dict[str, Any]:
    s = settings.load()
    data = row_json(s)

    # website launchers (built-in web versions and the user's websites)
    appdir = _local_share() / "applications"
    appdir.mkdir(parents=True, exist_ok=True)
    wanted = set()
    for a in apps.all_apps(s):
        if a.kind == "web":
            f = appdir / a.desktop
            wanted.add(f.name)
            _write(f, web_launcher(a, s))
    for f in appdir.glob("couchbox-web-*.desktop"):
        if f.name not in wanted:
            f.unlink()

    # renamed apps and extra launch arguments: a per-user .desktop with the same storage id
    user_apps = tv_home() / ".local/share/applications"
    favs = []
    for i, entry in enumerate(data["apps"]):
        src = find_desktop(entry["id"])
        if not src:
            continue
        text = src.read_text()
        own = desktop_field(text, "Name")
        args = EXTRA_ARGS.get(entry["id"], "")
        path = src
        if entry["name"] != own or args:
            lines = [ln for ln in text.splitlines() if not ln.startswith("Name[")]
            lines = [f"Name={entry['name']}" if ln.startswith("Name=") else ln for ln in lines]
            if args:
                lines = [f"{ln} {args}" if ln.startswith("Exec=") and args not in ln else ln for ln in lines]
            path = user_apps / entry["id"]
            _write(path, "\n".join(lines) + "\n", owner="tv")
        if not entry["icon"]:
            entry["icon"] = desktop_field(text, "Icon")
        cats = desktop_field(text, "Categories").rstrip(";").replace(";", ",")
        favs.append(
            "\n".join(
                [
                    f"[Favs][{i}]",
                    f"categories={cats}",
                    f"comment={desktop_field(text, 'Comment')}",
                    f"desktopPath={path}",
                    f"entryPath={desktop_field(text, 'Exec')}",
                    f"icon={entry['icon']}",
                    f"name={entry['name']}",
                    f"startupNotify={desktop_field(text, 'StartupNotify') or 'false'}",
                    f"storageId={entry['id']}",
                    "",
                ]
            )
        )
    _write(tv_home() / ".config/bigscreen-favs", "\n".join(favs), owner="tv")
    _write(home_dir() / "home.json", json.dumps(data, indent=2) + "\n")
    overlay(data)
    if restart_shell:
        restart_plasmashell()
    return data


def bigscreen_version() -> str:
    try:
        v = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "plasma-bigscreen"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return ""
    return v.split("-")[0]


def overlay(data: dict[str, Any]) -> str:
    """Copy Bigscreen's home screen and lay ours over it. Returns 'couchbox', 'stock' or 'none'."""
    ours = _local_share() / "plasma/plasmoids" / PLASMOID
    stock = paths.root() / str(STOCK).lstrip("/")
    version = bigscreen_version()
    if not stock.is_dir():
        return "none"
    if version not in TESTED_BIGSCREEN and os.environ.get("COUCHBOX_HOME_FORCE") != "1":
        if ours.exists():
            shutil.rmtree(ours)
        log.warning("Bigscreen %s isn't tested with the Couchbox home screen; using the stock one", version)
        return "stock"
    tmp = ours.with_name(ours.name + ".new")
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.copytree(stock, tmp, symlinks=True)
    shutil.copytree(paths.share() / "shell/home", tmp / "contents/ui", dirs_exist_ok=True)
    # first paint before home.json is read (and if file reads are blocked)
    js = ".pragma library\n// Written by couchbox (couchbox.home)\n" + f"var data = {json.dumps(data)};\n"
    (tmp / "contents/ui/couchbox/home-data.js").write_text(js)
    for p in tmp.rglob("*"):
        os.chmod(p, 0o755 if p.is_dir() else 0o644)
    if ours.exists():
        shutil.rmtree(ours)
    tmp.rename(ours)
    stamp = home_dir() / "bigscreen-version"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(version + "\n")
    return "couchbox"


def restart_plasmashell() -> None:
    if sh(["pgrep", "-u", "tv", "-x", "plasmashell"], check=False).returncode == 0:
        sh(["systemctl", "--user", "-M", "tv@", "restart", "plasma-plasmashell.service"], check=False)
