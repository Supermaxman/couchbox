"""Disk encryption: status, and turning "not protected" into "encrypted" while the box runs.

The image's root partition is LUKS2 from the start, opened at boot by a key file that's the
same on every image (IMAGE_KEY): bootable unattended, but not protected. encrypt():
  1. re-encrypts online with a new random volume key (cryptsetup reencrypt, resumable),
     unlocking with the image key, in the couchbox-reencrypt unit
  2. finish(): adds the passphrase (kept only in /run meanwhile), removes the image key's
     keyslot, binds Tang servers (Clevis), rebuilds the initrd without the key file and with
     networking (+ Wi-Fi) for Tang, installed through the Pi's test boot (piboot-try)
Design and threat model: docs/design/encryption.md.
"""

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from couchbox import paths
from couchbox.system import CommandError, out, sh

log = logging.getLogger("couchbox.encryption")

MAPPER = "root"


def image_key() -> Path:
    return paths.etc() / "luks/image.key"


def pending_file() -> Path:
    return paths.run() / "encrypt-pending.json"  # tmpfs: the passphrase never touches the disk


def progress_file() -> Path:
    return paths.run() / "reencrypt-progress.json"


def tang_file() -> Path:
    return paths.etc() / "luks/tang.json"


def root_device() -> str:
    """The partition under the root filesystem ("" when root isn't on LUKS)."""
    src = out(["findmnt", "-no", "SOURCE", "/"], check=False)
    if not src.startswith("/dev/mapper/"):
        return ""
    st = out(["cryptsetup", "status", src.rsplit("/", 1)[1]], check=False)
    m = re.search(r"^\s*device:\s*(\S+)", st, re.M)
    return m.group(1) if m else ""


def plain_root() -> str:
    src = out(["findmnt", "-no", "SOURCE", "/"], check=False)
    return src if src.startswith("/dev/") and not src.startswith("/dev/mapper/") else ""


def luks_meta(dev: str) -> dict[str, Any]:
    r = sh(["cryptsetup", "luksDump", "--dump-json-metadata", dev], check=False)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}


def image_key_works(dev: str) -> bool:
    k = image_key()
    if not k.exists():
        return False
    return sh(["cryptsetup", "open", "--test-passphrase", "--key-file", str(k), dev], check=False).returncode == 0


def tang_bindings(dev: str) -> list[str]:
    urls = []
    for line in out(["clevis", "luks", "list", "-d", dev], check=False).splitlines():
        urls += re.findall(r'"url":\s*"([^"]+)"', line)
    return urls


def reencrypt_running() -> bool:
    return sh(["systemctl", "is-active", "couchbox-reencrypt.service"], check=False).stdout.strip() in ("active", "activating")


def status() -> dict[str, Any]:
    dev = root_device()
    if not dev:
        return {"state": "plain", "device": plain_root(), "detail": "The disk isn't encrypted."}
    meta = luks_meta(dev)
    reqs = (meta.get("config") or {}).get("requirements") or {}
    in_progress = "online-reencrypt" in json.dumps(reqs) or reencrypt_running()
    keyslots = meta.get("keyslots") or {}
    tokens = [t for t in (meta.get("tokens") or {}).values() if t.get("type") == "clevis"]
    prog = {}
    try:
        prog = json.loads(progress_file().read_text())
    except (OSError, ValueError):
        pass
    if in_progress:
        return {
            "state": "encrypting",
            "device": dev,
            "percent": prog.get("percent"),
            "eta_s": prog.get("eta_s"),
            "detail": "Encrypting in the background. You can keep watching.",
        }
    if image_key_works(dev):
        return {
            "state": "unprotected",
            "device": dev,
            "keyslots": len(keyslots),
            "detail": "Not protected: this box's disk opens with the key every Couchbox image shares.",
        }
    st = {
        "state": "encrypted",
        "device": dev,
        "keyslots": len(keyslots),
        "network_unlock": len(tokens),
        "tang": tang_bindings(dev),
        "wifi_at_boot": (paths.etc() / "luks/initrd-wpa.conf").exists(),
        "finishing": pending_file().exists(),
    }
    st["detail"] = "Encrypted: passphrase" + (f" + {len(tokens)} network unlock" if tokens else "")
    return st


def check_tang(url: str) -> dict[str, Any]:
    """Fetch a Tang server's advertisement and its signing-key thumbprints (to confirm)."""
    if not re.fullmatch(r"https?://[A-Za-z0-9.\-\[\]:]+(/[A-Za-z0-9._~/-]*)?", url):
        raise CommandError("Tang addresses look like http://192.168.1.10:7500")
    import urllib.request

    try:
        with urllib.request.urlopen(url.rstrip("/") + "/adv", timeout=8) as r:
            adv = r.read()
    except OSError as e:
        raise CommandError(f"No answer from {url}: {e}") from None
    thumbs = out(["jose", "jwk", "thp", "-i-"], input=_adv_keys(adv), check=False).split()
    return {"url": url.rstrip("/"), "thumbprints": thumbs}


def _adv_keys(adv: bytes) -> str:
    import base64

    try:
        payload = json.loads(adv)["payload"]
        jwks = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        return json.dumps({"keys": [k for k in jwks.get("keys", []) if "verify" in k.get("key_ops", [])]})
    except (ValueError, KeyError):
        return "{}"


def start_encrypt(passphrase: str, tang: list[str], wifi: bool) -> dict[str, Any]:
    dev = root_device()
    if not dev:
        raise CommandError("This box's disk wasn't set up for encryption (installer systems: see docs/design/encryption.md, plan B).")
    if not image_key_works(dev):
        raise CommandError("The disk is already encrypted with your own key.")
    if len(passphrase) < 8:
        raise CommandError("Use at least 8 characters for the passphrase.")
    pending = pending_file()
    pending.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump({"passphrase": passphrase, "tang": tang, "wifi": wifi}, f)
    sh(["systemctl", "start", "--no-block", "couchbox-reencrypt.service"], check=False)
    return status()


def reencrypt(dev: str | None = None) -> None:
    """The couchbox-reencrypt unit: online re-encryption to a new volume key, then finish()."""
    dev = dev or root_device()
    meta = luks_meta(dev)
    resuming = "online-reencrypt" in json.dumps((meta.get("config") or {}).get("requirements") or {})
    cmd = ["cryptsetup", "reencrypt", "--batch-mode", "--progress-json", "--progress-frequency", "5", "--key-file", str(image_key())]
    cmd += ["--resume-only"] if resuming else ["--resilience", "checksum"]
    cmd.append(dev)
    log.info("%s %s", "resuming" if resuming else "starting", " ".join(cmd))
    proc = subprocess.Popen(["ionice", "-c", "3", "nice", "-n", "19", *cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        line = line.strip()
        if line.startswith("{"):
            try:
                p = json.loads(line)
                done, size = int(p.get("device_bytes", 0)), int(p.get("device_size", 0)) or 1
                progress_file().write_text(json.dumps({"percent": round(100 * done / size, 1), "eta_s": int(p.get("eta_ms", 0)) // 1000}))
            except (ValueError, OSError):
                pass
        else:
            log.info("cryptsetup: %s", line)
    if proc.wait() != 0:
        raise CommandError(f"cryptsetup reencrypt exited {proc.returncode}")
    progress_file().unlink(missing_ok=True)
    finish(dev)


def finish(dev: str | None = None) -> dict[str, Any]:
    """After re-encryption: passphrase in, image key out, Tang bound, initrd rebuilt."""
    dev = dev or root_device()
    try:
        p = json.loads(pending_file().read_text())
    except (OSError, ValueError):
        log.warning("re-encrypted, but the passphrase was lost (reboot mid-way): Settings asks for it again")
        return status()
    key = str(image_key())
    sh(["cryptsetup", "luksAddKey", "--batch-mode", "--pbkdf", "argon2id", "--key-file", key, dev, "-"], input=p["passphrase"])
    if p.get("tang"):
        bind_tang(dev, p["tang"], p["passphrase"])
    write_wifi_conf(p.get("wifi", False))
    sh(["cryptsetup", "luksRemoveKey", "--batch-mode", dev, key])
    image_key().unlink(missing_ok=True)
    (paths.root() / "etc/dracut.conf.d/90-couchbox-imagekey.conf").unlink(missing_ok=True)
    set_crypttab(dev, keyfile=None)
    rebuild_initrd(network=bool(p.get("tang")))
    pending_file().unlink(missing_ok=True)
    return status()


def bind_tang(dev: str, urls: list[str], passphrase: str) -> None:
    cfg = {"t": 1, "pins": {"tang": [{"url": u} for u in urls]}}
    sh(["clevis", "luks", "bind", "-y", "-k", "-", "-d", dev, "sss", json.dumps(cfg)], input=passphrase)
    tang_file().parent.mkdir(parents=True, exist_ok=True)
    tang_file().write_text(json.dumps({"urls": urls}) + "\n")


def unbind_tang(dev: str) -> None:
    meta = luks_meta(dev)
    for tid, t in (meta.get("tokens") or {}).items():
        if t.get("type") == "clevis":
            for slot in t.get("keyslots", []):
                sh(["clevis", "luks", "unbind", "-f", "-d", dev, "-s", str(slot)], check=False)
    tang_file().unlink(missing_ok=True)


def write_wifi_conf(enabled: bool) -> bool:
    """/etc/couchbox/luks/initrd-wpa.conf from NetworkManager's active Wi-Fi (hashed PSK)."""
    f = paths.etc() / "luks/initrd-wpa.conf"
    if not enabled:
        f.unlink(missing_ok=True)
        return False
    con = ""
    for line in out(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"], check=False).splitlines():
        parts = line.split(":")
        if len(parts) >= 2 and parts[1] == "802-11-wireless":
            con = parts[0]
    if not con:
        f.unlink(missing_ok=True)
        return False
    ssid = out(["nmcli", "-g", "802-11-wireless.ssid", "connection", "show", "id", con], check=False)
    psk = out(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", "id", con], check=False)
    if not ssid or not psk:
        return False
    conf = out(["wpa_passphrase", ssid], input=psk + "\n")
    conf = "\n".join(ln for ln in conf.splitlines() if not ln.strip().startswith("#psk="))
    from couchbox import settings

    country = settings.get("network.wifi_country") or "US"
    f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write(f"country={country}\n{conf}\n")
    return True


def set_crypttab(dev: str, keyfile: str | None) -> None:
    uuid = out(["cryptsetup", "luksUUID", dev])
    ct = paths.root() / "etc/crypttab"
    lines = [
        ln
        for ln in (ct.read_text().splitlines() if ct.exists() else [])
        if not ln.startswith(f"{MAPPER}\t") and not ln.startswith(f"{MAPPER} ")
    ]
    lines.append(f"{MAPPER}\tUUID={uuid}\t{keyfile or 'none'}\tluks,discard")
    ct.write_text("\n".join(lines) + "\n")


def rebuild_initrd(network: bool) -> None:
    """dracut with (or without) Clevis + networking, then install it as a test boot."""
    conf = paths.root() / "etc/dracut.conf.d/91-couchbox-unlock.conf"
    mods = "clevis clevis-pin-tang clevis-pin-sss systemd-networkd" if network else ""
    if network and (paths.etc() / "luks/initrd-wpa.conf").exists():
        mods += " couchbox"  # Wi-Fi in the initrd
    if mods:
        conf.write_text(f'# Couchbox: unlock root with Tang over Ethernet or Wi-Fi\nadd_dracutmodules+=" {mods} "\n')
    else:
        conf.unlink(missing_ok=True)
    kver = os.uname().release
    sh(["dracut", "--force", "--kver", kver], timeout=900)
    sh(["flash-kernel", kver], check=False, timeout=600)
    fw = paths.boot_firmware() / "new/cmdline.txt"
    if network and fw.exists() and "rd.neednet=1" not in fw.read_text():
        fw.write_text(fw.read_text().rstrip("\n") + " rd.neednet=1\n")


class _KeyFile:
    """A passphrase as a root-only file in /run (tmpfs), removed afterwards."""

    def __init__(self, text: str):
        self.text = text
        self.path = paths.run() / f".key-{os.getpid()}-{id(self)}"

    def __enter__(self) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(self.text)
        return str(self.path)

    def __exit__(self, *exc) -> None:
        self.path.unlink(missing_ok=True)


def change_passphrase(old: str, new: str) -> None:
    dev = root_device()
    if len(new) < 8:
        raise CommandError("Use at least 8 characters for the passphrase.")
    with _KeyFile(old) as oldf:
        sh(["cryptsetup", "luksAddKey", "--batch-mode", "--pbkdf", "argon2id", "--key-file", oldf, dev, "-"], input=new)
        sh(["cryptsetup", "luksRemoveKey", "--batch-mode", dev, oldf])
