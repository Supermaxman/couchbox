"""Demo mode for the Settings app and setup wizard (screenshots, CI, development):
the real couchboxd, in this process, against a throwaway root and a fake system whose
commands answer with plausible output. Nothing on the machine is touched.

    from couchbox import demo
    demo.start()        # sets COUCHBOX_ROOT / COUCHBOX_SOCKET, starts the daemon thread
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ANSWERS = {
    ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION"): "eth0:ethernet:unavailable:\nwlan0:wifi:connected:couchbox-Home\n",
    ("nmcli", "-t", "networking"): "full\n",
    ("nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY,FREQ"): (
        "*:Home:84:WPA2:5180 MHz\n :Home:61:WPA2:2437 MHz\n :Neighbours 5G:48:WPA2 WPA3:5745 MHz\n"
        " :Coffee Shop:35::2412 MHz\n :DIRECT-printer:22:WPA2:2462 MHz\n"
    ),
    (
        "ip",
        "-4",
        "-o",
        "addr",
    ): "1: lo    inet 127.0.0.1/8 scope host lo\n3: wlan0    inet 192.168.1.42/24 brd 192.168.1.255 scope global wlan0\n",
    ("timedatectl", "show"): "Timezone=America/Chicago\nNTPSynchronized=yes\n",
    ("timedatectl", "list-timezones"): "\n".join(
        [
            "Africa/Cairo",
            "America/Chicago",
            "America/Denver",
            "America/Los_Angeles",
            "America/New_York",
            "America/Toronto",
            "Asia/Tokyo",
            "Australia/Sydney",
            "Europe/Berlin",
            "Europe/London",
            "Europe/Paris",
            "Pacific/Auckland",
            "UTC",
        ]
    ),
    ("tailscale", "status", "--json"): json.dumps({"BackendState": "NeedsLogin", "Self": {}}),
    ("systemctl", "is-active", "couchbox-reencrypt.service"): "inactive\n",
    ("systemctl", "is-active", "couchbox-updater.service"): "inactive\n",
    ("systemctl", "is-active"): "active\n",
    ("vcgencmd", "get_throttled"): "throttled=0x0\n",
    ("findmnt", "-no", "SOURCE", "/"): "/dev/mapper/root\n",
    ("cryptsetup", "status"): "/dev/mapper/root is active and is in use.\n  type:    LUKS2\n  device:  /dev/nvme0n1p2\n",
    ("cryptsetup", "luksDump"): json.dumps({"keyslots": {"0": {}}, "tokens": {}, "config": {}}),
    ("cryptsetup", "open", "--test-passphrase"): "",
    ("pgrep",): "1234\n",
    ("rsvg-convert",): "",
}


class Runner:
    def __call__(self, cmd, input, timeout):
        cmd = list(cmd)
        for prefix, out in sorted(ANSWERS.items(), key=lambda kv: -len(kv[0])):
            if tuple(cmd[: len(prefix)]) == prefix:
                return subprocess.CompletedProcess(cmd, 0, out, "")
        if cmd[0] == "rsvg-convert" and shutil.which("rsvg-convert"):
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return subprocess.CompletedProcess(cmd, 0, "", "")


def start(share: str | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="couchbox-demo-"))
    src = Path(share or os.environ.get("COUCHBOX_SHARE") or "/usr/share/couchbox")
    os.environ["COUCHBOX_ROOT"] = str(root)
    os.environ["COUCHBOX_SHARE"] = str(src)
    os.environ["COUCHBOX_SOCKET"] = str(root / "couchboxd.sock")
    os.environ["COUCHBOX_TV_HOME"] = str(root / "home/tv")
    (root / "etc/couchbox/luks").mkdir(parents=True)
    (root / "etc/couchbox/luks/image.key").write_text("demo")  # "not protected", as a fresh image
    (root / "etc/os-release").parent.mkdir(parents=True, exist_ok=True)
    (root / "etc/os-release").write_text('PRETTY_NAME="Ubuntu 26.10"\nVERSION_ID="26.10"\n')
    for n, v in (
        ("proc/device-tree/model", "Raspberry Pi 5 Model B Rev 1.0"),
        ("sys/class/thermal/thermal_zone0/temp", "52300"),
        ("proc/meminfo", "MemTotal:        8130000 kB\nMemAvailable:    5210000 kB\n"),
        ("sys/class/drm/card1-HDMI-A-1/status", "connected"),
        ("sys/class/drm/card1-HDMI-A-1/modes", "3840x2160\n2560x1440\n1920x1080\n1280x720\n"),
    ):
        f = root / n
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(v)
    from couchbox import remote, settings, system

    system.RUNNER = Runner()
    paired: list[dict] = []

    async def fake_pair(progress, mac="", seconds=45, stop=None):
        progress("searching", {"seconds": seconds})
        await asyncio.sleep(2)
        d = {
            "address": "AA:BB:CC:00:11:22",
            "name": "AR Remote",
            "paired": True,
            "connected": True,
            "trusted": True,
            "battery": 90,
            "remote": True,
        }
        progress("found", d)
        await asyncio.sleep(1)
        paired[:] = [d]
        progress("paired", d)
        return d

    async def fake_devices():
        return list(paired)

    async def fake_forget(address):
        paired.clear()

    remote.pair, remote.list_devices, remote.forget = fake_pair, fake_devices, fake_forget
    settings._schema_cache.clear()
    from couchbox.daemon import server

    loop = asyncio.new_event_loop()
    threading.Thread(target=lambda: loop.run_until_complete(server.serve()), daemon=True).start()
    for _ in range(200):
        if (root / "couchboxd.sock").exists():
            break
        time.sleep(0.02)
    return root
