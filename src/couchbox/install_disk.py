"""Install to the SSD: copy the running system onto the box's internal drive.

For setting a box up with nothing but a USB stick (or SD card) and the TV. You flash the
image to the stick on any computer, boot the Pi from it, and the setup wizard offers to copy
the system to the NVMe drive. The copy is the same box: settings, Wi-Fi, the paired remote
and the setup wizard's progress come along.

The new drive gets a FAT boot partition the size of the current one and an ext4 root
filling the rest. Its fstab and cmdline.txt point at its own partitions by PARTUUID, so it
boots right even with the stick still plugged in (the image's LABEL=writable would match
both). The Pi 5 bootloader's default order is SD card, NVMe, then USB:
- from a USB stick, a restart boots the SSD;
- from an SD card, the card has to come out first.

    status()              where we booted from, drives we can install to, the job's state
    start(device)         copy in a background thread; progress through on_progress
"""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from couchbox.system import CommandError, out, sh

log = logging.getLogger("couchbox.install")

MIN_BYTES = 16 * 10**9
MOUNT = Path("/run/couchbox/install")
# Not copied: other filesystems are skipped anyway (-x); these are per-boot or rebuilt.
EXCLUDE = ["/swapfile", "/var/cache/apt/archives/*.deb", "/lost+found"]

_job: dict[str, Any] = {"state": "idle"}
_lock = threading.Lock()


class InstallError(RuntimeError):
    pass


def _lsblk() -> list[dict[str, Any]]:
    r = out(["lsblk", "-J", "-b", "-o", "NAME,PATH,TYPE,SIZE,MODEL,TRAN,RM,MOUNTPOINTS,PKNAME"], check=False)
    try:
        return json.loads(r).get("blockdevices", [])
    except ValueError:
        return []


def _mounted(dev: dict[str, Any]) -> bool:
    if any(m for m in dev.get("mountpoints") or [] if m):
        return True
    return any(_mounted(c) for c in dev.get("children") or [])


def root_disk() -> dict[str, Any]:
    """The disk the running system is on: {path, tran} (tran: usb, mmc, nvme...)."""
    src = out(["findmnt", "-n", "-o", "SOURCE", "/"], check=False)
    if src.startswith("/dev/mapper/"):
        return {"path": "", "tran": "encrypted"}
    parent = out(["lsblk", "-n", "-d", "-o", "PKNAME", src], check=False) if src else ""
    path = f"/dev/{parent}" if parent else src
    for d in _lsblk():
        if d.get("path") == path:
            tran = d.get("tran") or ("mmc" if d["name"].startswith("mmcblk") else "")
            return {"path": path, "tran": tran, "model": (d.get("model") or "").strip(), "size": int(d.get("size") or 0)}
    return {"path": path, "tran": ""}


def targets() -> list[dict[str, Any]]:
    """Drives we can install to: whole disks, not the one we run from, nothing mounted, 16 GB+.
    The internal NVMe drive first."""
    me = root_disk()["path"]
    found = []
    for d in _lsblk():
        if d.get("type") != "disk" or d.get("path") == me or _mounted(d):
            continue
        if re.match(r"(zram|loop|ram|mtdblock|mmcblk\d+boot)", d["name"]):
            continue
        size = int(d.get("size") or 0)
        if size < MIN_BYTES:
            continue
        tran = d.get("tran") or ("mmc" if d["name"].startswith("mmcblk") else "")
        kind = {"nvme": "SSD", "usb": "USB drive", "mmc": "SD card"}.get(tran, "drive")
        found.append(
            {
                "path": d["path"],
                "model": (d.get("model") or "").strip(),
                "size": size,
                "tran": tran,
                "label": f"{kind} {(d.get('model') or '').strip()} ({size / 10**9:.0f} GB)".replace("  ", " "),
            }
        )
    return sorted(found, key=lambda t: (t["tran"] != "nvme", t["path"]))


def status() -> dict[str, Any]:
    me = root_disk()
    t = targets() if me["tran"] in ("usb", "mmc") else []
    return {"booted_from": me["tran"], "can_install": bool(t) and _job["state"] in ("idle", "failed"), "targets": t, "job": dict(_job)}


def part(disk: str, n: int) -> str:
    """/dev/nvme0n1 -> /dev/nvme0n1p1, /dev/sda -> /dev/sda1."""
    return f"{disk}p{n}" if disk[-1].isdigit() else f"{disk}{n}"


def fix_fstab(text: str, root_uuid: str, boot_uuid: str) -> str:
    """Point / and /boot/firmware at the new drive's partitions; other lines stay."""
    lines = []
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 2 and not line.lstrip().startswith("#"):
            if f[1] == "/":
                line = line.replace(f[0], f"PARTUUID={root_uuid}", 1)
            elif f[1] in ("/boot/firmware", "/boot"):
                line = line.replace(f[0], f"PARTUUID={boot_uuid}", 1)
        lines.append(line)
    return "\n".join(lines) + "\n"


def fix_cmdline(text: str, root_uuid: str) -> str:
    return re.sub(r"\broot=\S+", f"root=PARTUUID={root_uuid}", text.strip()) + "\n"


def _publish(on_progress: Callable[[dict[str, Any]], None] | None, **kw: Any) -> None:
    _job.update(kw)
    if on_progress:
        try:
            on_progress(dict(_job))
        except Exception:  # noqa: BLE001
            log.exception("progress")


def _used(p: str) -> int:
    st = os.statvfs(p)
    return (st.f_blocks - st.f_bfree) * st.f_frsize


def copy(disk: str, on_progress: Callable[[dict[str, Any]], None] | None = None, source: str = "/") -> None:
    """Partition, format and fill `disk` from the running system (or `source`, for tests)."""
    src = Path(source)
    boot_src = src / "boot/firmware"
    boot_mb = 512
    bsrc = out(["findmnt", "-n", "-o", "SOURCE", str(boot_src)], check=False)
    if bsrc:
        boot_mb = max(256, int(out(["lsblk", "-n", "-b", "-d", "-o", "SIZE", bsrc]) or 0) // 2**20)

    _publish(on_progress, state="running", step="Preparing the drive", percent=0)
    sh(["wipefs", "-a", disk])
    sh(["sfdisk", "--quiet", disk], input=f"label: dos\n,{boot_mb}MiB,c,*\n,,83\n")
    sh(["udevadm", "settle"], check=False)
    p1, p2 = part(disk, 1), part(disk, 2)
    for _ in range(20):
        if os.path.exists(p2):
            break
        time.sleep(0.5)
    sh(["mkfs.vfat", "-F", "32", "-n", "system-boot", p1])
    sh(["mkfs.ext4", "-q", "-F", "-L", "writable", p2], timeout=600)
    root_uuid = out(["blkid", "-s", "PARTUUID", "-o", "value", p2])
    boot_uuid = out(["blkid", "-s", "PARTUUID", "-o", "value", p1])

    mnt = MOUNT
    mnt.mkdir(parents=True, exist_ok=True)
    sh(["mount", p2, str(mnt)])
    try:
        need = max(1, _used(str(src)))
        if need > int(out(["lsblk", "-n", "-b", "-d", "-o", "SIZE", disk]) or 0) * 0.9:
            raise InstallError("The system doesn't fit on that drive.")

        _publish(on_progress, step="Copying the system", percent=1)
        done = threading.Event()

        def watch():
            while not done.wait(2):
                pct = min(98, int(100 * _used(str(mnt)) / need))
                if pct != _job.get("percent"):
                    _publish(on_progress, percent=pct)

        threading.Thread(target=watch, daemon=True).start()
        try:
            # The root first (-x: not into /boot/firmware, /proc...). The boot partition is
            # mounted only after: rsync -a can't set owners on the FAT mount point.
            sh(["rsync", "-aHAXx", "--numeric-ids", *[f"--exclude={e}" for e in EXCLUDE], f"{src}/", f"{mnt}/"], timeout=3 * 3600)
        finally:
            done.set()
        (mnt / "boot/firmware").mkdir(parents=True, exist_ok=True)
        sh(["mount", p1, str(mnt / "boot/firmware")])
        sh(["rsync", "-rt", "--modify-window=2", f"{boot_src}/", f"{mnt}/boot/firmware/"], timeout=600)

        _publish(on_progress, step="Making it bootable", percent=99)
        fstab = mnt / "etc/fstab"
        if fstab.exists():
            fstab.write_text(fix_fstab(fstab.read_text(), root_uuid, boot_uuid))
        for c in (mnt / "boot/firmware").rglob("cmdline.txt"):
            c.write_text(fix_cmdline(c.read_text(), root_uuid))
        swap = src / "swapfile"
        if swap.exists():  # not copied: made fresh, the size couchbox-swap picks for an SSD
            big = int(out(["lsblk", "-n", "-b", "-d", "-o", "SIZE", disk]) or 0) >= 100 * 10**9
            sh(["fallocate", "-l", "8G" if big else "2G", str(mnt / "swapfile")])
            os.chmod(mnt / "swapfile", 0o600)
            sh(["mkswap", "-q", str(mnt / "swapfile")])
        st = mnt / "var/lib/couchbox/state"
        st.mkdir(parents=True, exist_ok=True)
        (st / "installed-from.json").write_text(json.dumps({"time": time.time(), "from": root_disk().get("tran", "")}) + "\n")
        sh(["sync"], check=False, timeout=600)
    finally:
        sh(["umount", "-R", str(mnt)], check=False, timeout=300)


def start(device: str, on_progress: Callable[[dict[str, Any]], None] | None = None) -> dict[str, Any]:
    with _lock:
        if _job["state"] == "running":
            raise InstallError("Already copying.")
        me = root_disk()
        if me["tran"] == "encrypted":
            raise InstallError("Install to the SSD before turning on encryption.")
        ok = {t["path"]: t for t in targets()}
        if device not in ok:
            raise InstallError("That drive isn't available to install to.")
        _job.clear()
        _job.update({"state": "running", "device": device, "label": ok[device]["label"], "from": me["tran"], "percent": 0})

    def run():
        try:
            copy(device, on_progress)
            # From USB, a restart boots the SSD (SD, NVMe, USB is the bootloader's order).
            # From an SD card, the card has to come out first.
            _publish(on_progress, state="done", percent=100, step="Done", next="restart" if me["tran"] == "usb" else "remove_card")
        except (CommandError, InstallError, OSError) as e:
            log.error("install to %s: %s", device, e)
            _publish(on_progress, state="failed", error=str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("install to %s", device)
            _publish(on_progress, state="failed", error=f"Copy failed: {e}")

    threading.Thread(target=run, name="install-disk", daemon=True).start()
    return dict(_job)
