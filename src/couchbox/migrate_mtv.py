"""couchbox import-mtv: settings from the mtv prototype (/etc/mtv/mtv.conf, secrets, home.tsv,
apps.tsv) as Couchbox settings and secrets. Read-only: the caller writes them."""

import re
import shlex
from pathlib import Path
from typing import Any

# home.tsv desktop ids -> Couchbox app ids
DESKTOP_IDS = {
    "rocks.shy.VacuumTube.desktop": "youtube",
    "mtv-jellyfin.desktop": "jellyfin",
    "mtv-seerr.desktop": "seerr",
    "mtv-dropout.desktop": "dropout",
    "mtv-2ndtry.desktop": "2ndtry",
    "mtv-nebula.desktop": "nebula",
    "mtv-twitch.desktop": "twitch",
}
BUILTIN_WEB = {"dropout", "2ndtry", "nebula", "twitch", "seerr", "jellyfin"}


def parse_conf(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(MTV_[A-Z0-9_]+)=(.*)$", line)
        if not m:
            continue
        try:
            parts = shlex.split(m.group(2), comments=True)
        except ValueError:
            continue
        out[m.group(1)] = parts[0] if parts else ""
    return out


def read(path: str = "/etc/mtv") -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(path)
    c = parse_conf((root / "mtv.conf").read_text())
    s: dict[str, Any] = {}

    def put(key, value):
        if value not in (None, ""):
            s[key] = value

    put("network.hostname", c.get("MTV_HOSTNAME"))
    put("time.timezone", c.get("MTV_TIMEZONE"))
    if c.get("MTV_WEATHER"):
        lat, lon, *name = c["MTV_WEATHER"].split(",")
        s.update({"location.lat": float(lat), "location.lon": float(lon), "location.name": ",".join(name) or "Home"})
    if c.get("MTV_MODE"):
        s["display.mode"] = c["MTV_MODE"]
    if c.get("MTV_SCALE"):
        s["appearance.scale"] = float(c["MTV_SCALE"])
    if c.get("MTV_OUTPUTS"):
        s["display.outputs"] = c["MTV_OUTPUTS"].split()
    put("tv.cec.device", c.get("MTV_CEC_DEV"))
    put("tv.cec.name", c.get("MTV_OSD_NAME"))
    put("tv.volume", c.get("MTV_VOLUME"))
    if c.get("MTV_TV_INPUTS"):
        s["tv.inputs"] = c["MTV_TV_INPUTS"].split()
    put("apps.airplay.name", c.get("MTV_AIRPLAY_NAME"))
    put("apps.airplay.pin", c.get("MTV_AIRPLAY_PIN"))
    put("tailscale.tags", c.get("MTV_TS_TAGS"))
    put("ssh.github_user", c.get("MTV_GITHUB_KEYS"))
    put("voice.llm.url", c.get("MTV_LLM_URL"))
    put("voice.llm.model", c.get("MTV_LLM_MODEL"))
    put("voice.stt.url", c.get("MTV_STT_URL"))
    put("voice.stt.model", c.get("MTV_STT_MODEL"))
    put("media.seerr.url", c.get("MTV_SEERR_URL"))
    if "MTV_YT_CAPTIONS" in c:
        s["apps.youtube.captions"] = c["MTV_YT_CAPTIONS"]
    if c.get("MTV_APP_IDLE_MINUTES"):
        s["apps.idle_minutes"] = int(c["MTV_APP_IDLE_MINUTES"])
    if c.get("MTV_SWAP_GB"):
        s["system.swap_gb"] = int(c["MTV_SWAP_GB"])
    if c.get("MTV_WEB_CACHE_BYTES"):
        s["apps.web_cache_mb"] = max(64, int(c["MTV_WEB_CACHE_BYTES"]) // (1024 * 1024))
    if c.get("MTV_LLM_URL") and c.get("MTV_STT_URL"):
        s["voice.mode"] = "assistant"
    s["tailscale.enabled"] = True  # the prototype always ran it
    s["ssh.enabled"] = True

    layout = []
    home = root / "home.tsv"
    if home.exists():
        for line in home.read_text().splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            did = line.split("\t")[0]
            if did in DESKTOP_IDS:
                layout.append(DESKTOP_IDS[did])
    if layout:
        s["home.layout"] = layout
    apps = root / "apps.tsv"
    web = []
    if apps.exists():
        for line in apps.read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and not line.startswith("#"):
                if parts[0] == "jellyfin":
                    s["media.jellyfin.url"] = parts[2]
                elif parts[0] not in BUILTIN_WEB:
                    web.append({"name": parts[1], "url": parts[2]})
    if web:
        s["home.web_apps"] = web
    notes = root / "voice-notes.md"
    if notes.exists():
        s["voice.notes"] = notes.read_text()

    secrets = {}
    for name, f in (("voice.llm.api_key", "llm-key"), ("media.seerr.api_key", "seerr-key")):
        p = root / "secrets" / f
        if p.exists():
            secrets[name] = p.read_text().strip()
    return s, secrets
