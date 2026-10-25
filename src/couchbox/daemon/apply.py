"""Making settings take effect. apply(changed, settings) runs after every change and returns
notes for the screen ("Restarting the home screen"). Each step is best-effort: a failure is
logged and reported, never leaves the setting half-written."""

import logging
from collections.abc import Callable
from typing import Any

from couchbox import home, paths, settings
from couchbox.system import sh, systemctl, user_systemctl

log = logging.getLogger("couchboxd.apply")

TOOLS = "/usr/lib/couchbox/bin"


def tool(name: str, *args: str, check: bool = False):
    return sh([f"{TOOLS}/couchbox-{name}", *args], check=check, timeout=300)


def _hostname(s: dict[str, Any]) -> None:
    name = s["network.hostname"]
    sh(["hostnamectl", "set-hostname", name], check=False)
    hosts = paths.root() / "etc/hosts"
    try:
        lines = hosts.read_text().splitlines()
        lines = [ln for ln in lines if not ln.startswith("127.0.1.1")]
        lines.insert(1 if lines and lines[0].startswith("127.0.0.1") else 0, f"127.0.1.1\t{name}")
        hosts.write_text("\n".join(lines) + "\n")
    except OSError as e:
        log.warning("/etc/hosts: %s", e)
    systemctl("try-restart", "avahi-daemon")
    if s["tailscale.enabled"]:
        sh(["tailscale", "set", f"--hostname={name}"], check=False)


def _timezone(s: dict[str, Any]) -> None:
    sh(["timedatectl", "set-timezone", s["time.timezone"]], check=False)


def _wifi_country(s: dict[str, Any]) -> None:
    c = s["network.wifi_country"]
    if c:
        sh(["iw", "reg", "set", c], check=False)


def _ssh(s: dict[str, Any]) -> None:
    if s["ssh.enabled"]:
        systemctl("enable", "--now", "ssh.service")
    else:
        systemctl("disable", "--now", "ssh.service", "ssh.socket")


def _airplay(s: dict[str, Any]) -> None:
    if s["apps.airplay.enabled"]:
        user_systemctl("tv", "restart", "couchbox-airplay.service")
    else:
        user_systemctl("tv", "stop", "couchbox-airplay.service")


def tailscale_serve(s: dict[str, Any]) -> None:
    if s["tailscale.enabled"] and s["tailscale.serve_phone_page"] and s["phone.enabled"]:
        sh(["tailscale", "serve", "--bg", "--https=443", "http://127.0.0.1:8791"], check=False)
    else:
        sh(["tailscale", "serve", "--https=443", "off"], check=False)


def _tailscale(s: dict[str, Any]) -> None:
    if not s["tailscale.enabled"]:
        sh(["tailscale", "down"], check=False)
    tailscale_serve(s)


def _journal(s: dict[str, Any]) -> None:
    d = paths.root() / "etc/systemd/journald.conf.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / "60-couchbox-size.conf").write_text(f"[Journal]\nSystemMaxUse={s['system.logs_mb']}M\n")
    systemctl("restart", "systemd-journald")


def _os_updates(s: dict[str, Any]) -> None:
    on = "0" if s["updates.os"] == "off" else "1"
    f = paths.root() / "etc/apt/apt.conf.d/20auto-upgrades"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f'APT::Periodic::Update-Package-Lists "{on}";\nAPT::Periodic::Unattended-Upgrade "{on}";\n')
    origins = paths.root() / "etc/apt/apt.conf.d/52couchbox-unattended"
    if s["updates.os"] == "all":
        origins.write_text('Unattended-Upgrade::Allowed-Origins:: "${distro_id}:${distro_codename}-updates";\n')
    else:
        origins.unlink(missing_ok=True)


def _home(s: dict[str, Any]) -> None:
    home.build()


# key prefix -> (step, note shown on screen or "")
STEPS: list[tuple[tuple[str, ...], Callable[[dict[str, Any]], None], str]] = [
    (("network.hostname",), _hostname, ""),
    (("network.wifi_country",), _wifi_country, ""),
    (("time.timezone",), _timezone, ""),
    (("ssh.enabled",), _ssh, ""),
    (("network.hostname", "apps.airplay."), _airplay, ""),
    (("tailscale.",), _tailscale, ""),
    (("phone.enabled",), tailscale_serve, ""),
    (("system.logs_mb",), _journal, ""),
    (("updates.os",), _os_updates, ""),
    (("home.", "apps.disabled", "apps.web_cache_mb", "location.", "media.jellyfin.url", "media.seerr.url", "time.timezone"), _home, ""),
    (("appearance.theme",), lambda s: tool("theme"), "Theme applied."),
    (("appearance.scale", "display."), lambda s: tool("display"), "Display updated."),
    (("system.swap_gb",), lambda s: tool("swap"), ""),
]


def apply(changed: dict[str, Any], s: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if not changed:
        return notes
    for prefixes, step, note in STEPS:
        if any(k.startswith(p) for k in changed for p in prefixes):
            try:
                step(s)
                if note:
                    notes.append(note)
            except Exception as e:  # noqa: BLE001
                log.exception("applying %s", step.__name__ if hasattr(step, "__name__") else step)
                notes.append(f"Couldn't apply everything: {e}")
    # services that read their settings at start
    restart = set()
    for k in changed:
        hint = settings.spec(k).get("restart", "")
        if hint.startswith("service:") and hint != "service:couchbox-airplay":
            restart.add(hint.split(":", 1)[1])
        if hint == "session":
            notes.append("Restarts the home screen to take effect.")
    for unit in sorted(restart):
        systemctl("try-restart", f"{unit}.service")
    return notes


def secret_changed(name: str) -> None:
    if name.startswith("voice."):
        systemctl("try-restart", "couchbox-voice.service")
    if name == "phone.token":
        systemctl("try-restart", "couchbox-phone.service")


def wifi_changed() -> None:
    """Keep the disk's network unlock on the current Wi-Fi (when it's set up)."""
    try:
        from . import api_encryption

        api_encryption.refresh_initrd_wifi()
    except Exception as e:  # noqa: BLE001
        log.warning("initrd Wi-Fi refresh: %s", e)
