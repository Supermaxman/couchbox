"""The boot screen: the Couchbox Plymouth theme, switched on by the package.

apply() makes "couchbox" Plymouth's theme and, when the theme or its initrd side changed since
the boot image was last built (or the boot command line doesn't ask for the splash yet), builds
a new initrd and installs it as a test boot: flash-kernel writes /boot/firmware/new, the box
tries it once at the next restart (piboot-try) and keeps it only if it boots, else it falls
back to the current one. The splash arguments go on the test boot's command line only, so they
reach the current one together with the initrd that has the theme.
"""

import hashlib
import logging
import os
from pathlib import Path

from couchbox import paths, settings
from couchbox.system import sh

log = logging.getLogger(__name__)

THEME = "usr/share/plymouth/themes/couchbox"
MODULE = "usr/lib/dracut/modules.d/89couchbox-boot"
HELPER = "usr/lib/couchbox/bin/couchbox-boot-status"
# quiet kernel and systemd, the splash, no kernel messages above errors, no blinking cursor, and
# the splash on the TV even though the serial console is on too
SPLASH_ARGS = ("quiet", "splash", "loglevel=3", "vt.global_cursor_default=0", "plymouth.ignore-serial-consoles")


def video_args() -> list[str]:
    """The TV session's resolution from the start of the boot (video=HDMI-A-1:1920x1080@60), so
    the TV doesn't switch modes, and go black for a moment, when the boot screen hands over."""
    mode = settings.get("display.mode")
    return [f"video={o}:{mode}" for o in settings.get("display.outputs")]


def with_splash(cmdline: str) -> str:
    """cmdline.txt's one line with the splash arguments added (those already there stay put)
    and the outputs' video= modes set to the TV session's."""
    video = video_args()
    outs = {v.split("=", 1)[1].split(":", 1)[0] for v in video}
    words = [w for w in cmdline.split() if not (w.startswith("video=") and w[6:].split(":", 1)[0] in outs)]
    return " ".join(words + [w for w in SPLASH_ARGS if w not in words] + video) + "\n"


def fingerprint() -> str:
    """What the boot image's splash is made of: the theme, the dracut module and the helper."""
    h = hashlib.sha256()
    root = paths.root()
    for base in (THEME, MODULE, HELPER):
        p = root / base
        for f in sorted([p] if p.is_file() else p.rglob("*") if p.is_dir() else []):
            if f.is_file():
                h.update(str(f.relative_to(root)).encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def _stamp() -> Path:
    return paths.state() / "boot-screen.stamp"


def _kernel() -> str:
    """The newest installed kernel (the one the next boot runs)."""
    if os.environ.get("COUCHBOX_KVER"):
        return os.environ["COUCHBOX_KVER"]
    r = sh(["linux-version", "list"], check=False)
    kvers = r.stdout.split()
    if kvers:
        s = sh(["linux-version", "sort"], input="\n".join(kvers) + "\n", check=False)
        if s.stdout.split():
            return s.stdout.split()[-1]
    return os.uname().release


def needs_rebuild() -> bool:
    cur = paths.boot_firmware() / "current/cmdline.txt"
    words = cur.read_text().split() if cur.exists() else []
    stamp = _stamp()
    return not all(w in words for w in (*SPLASH_ARGS, *video_args())) or not stamp.exists() or stamp.read_text().strip() != fingerprint()


def apply() -> str:
    """Theme on; a new test boot if needed. Returns what it did, for the log."""
    root = paths.root()
    if not (root / THEME / "couchbox.plymouth").exists():
        return "no theme"
    plymouth = f"/{THEME}/couchbox.plymouth"
    sh(["update-alternatives", "--quiet", "--install", "/usr/share/plymouth/themes/default.plymouth",
        "default.plymouth", plymouth, "150"], check=False)
    sh(["update-alternatives", "--quiet", "--set", "default.plymouth", plymouth], check=False)
    fw = paths.boot_firmware()
    if not (fw / "current/cmdline.txt").exists():
        return "no piboot layout"  # not a Pi with flash-kernel's try-once boot: leave it alone
    if not needs_rebuild():
        return "up to date"
    kver = _kernel()
    sh(["dracut", "--force", "--kver", kver], timeout=900)
    fk = sh(["flash-kernel", kver], check=False, timeout=600)
    new = fw / "new/cmdline.txt"
    if fk.returncode != 0 or not new.exists():
        log.warning("flash-kernel %s: %s", kver, (fk.stderr or fk.stdout).strip()[-500:])
        return "flash-kernel failed: the current boot stays"
    new.write_text(with_splash(new.read_text()))
    _stamp().parent.mkdir(parents=True, exist_ok=True)
    _stamp().write_text(fingerprint() + "\n")
    return f"test boot ready ({kver})"
