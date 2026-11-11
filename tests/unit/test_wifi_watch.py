"""couchbox-wifi-watch against stand-ins for nmcli, ip, ping and modprobe: a dead router gets a
NetworkManager reconnect, then a driver reload, and its return is logged; a router that never
answered pings, Ethernet, or a Wi-Fi that was never set up are left alone."""

import os
import re
import subprocess
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WATCH = REPO / "bin" / "couchbox-wifi-watch"

NMCLI = """#!/bin/bash
echo "nmcli $*" >> "$T/calls"
case "$*" in
  "-t -f DEVICE,TYPE,STATE device") echo x >> "$T/loops"; echo "wlan0:wifi:connected" ;;
  "radio wifi") echo enabled ;;
  "-t -f TYPE,STATE device") echo "wifi:connected"; [ -e "$T/ethernet" ] && echo "ethernet:connected" ;;
  "-t -f TYPE connection show") echo 802-11-wireless ;;
  *" connect "*) echo "Device 'wlan0' successfully activated" ;;
esac
exit 0
"""
IP = '#!/bin/bash\necho "default via 192.0.2.1 dev wlan0 proto dhcp metric 600"\n'
# answers while the loop count is outside [DEAD_FROM, DEAD_TO)
PING = """#!/bin/bash
n=$(wc -l < "$T/loops")
(( n < DEAD_FROM || n >= DEAD_TO ))
"""
MODPROBE = '#!/bin/bash\necho "modprobe $*" >> "$T/calls"\n'


def run(tmp: Path, loops: int, dead=(3, 99), state: str | None = None, ethernet=False):
    sys_ = tmp / "sys"
    (sys_ / "module/brcmfmac/holders/brcmfmac_cyw").mkdir(parents=True)
    (sys_ / "class/net/wlan0/device/driver").mkdir(parents=True)
    (sys_ / "class/net/wlan0/device/driver/module").symlink_to(sys_ / "module/brcmfmac")
    script = WATCH.read_text()
    script = re.sub(r"^CHECK=60 ", "CHECK=0.01 ", script, flags=re.M)
    script = re.sub(r"^STATE=.*$", f"STATE={tmp}/router", script, flags=re.M)
    script = re.sub(r"^\[\[ \$EUID.*$", "", script, flags=re.M)
    script = re.sub(r"sleep [0-9]+\b", "sleep 0", script).replace("/sys/", f"{sys_}/")
    (tmp / "watch").write_text(script)
    bin_ = tmp / "bin"
    bin_.mkdir()
    for name, body in (("nmcli", NMCLI), ("ip", IP), ("ping", PING), ("modprobe", MODPROBE)):
        (bin_ / name).write_text(body)
        (bin_ / name).chmod(0o755)
    (tmp / "loops").touch()
    (tmp / "calls").touch()
    if state:
        (tmp / "router").write_text(state + "\n")
    if ethernet:
        (tmp / "ethernet").touch()
    env = {**os.environ, "T": str(tmp), "PATH": f"{bin_}:{os.environ['PATH']}", "DEAD_FROM": str(dead[0]), "DEAD_TO": str(dead[1])}
    p = subprocess.Popen(["bash", str(tmp / "watch")], env=env, stdout=subprocess.PIPE, text=True)
    deadline = time.time() + 20
    while len((tmp / "loops").read_text().splitlines()) < loops and time.time() < deadline:
        time.sleep(0.02)
    p.terminate()
    out, _ = p.communicate(timeout=5)
    calls = [c for c in (tmp / "calls").read_text().splitlines() if " -t -f " not in c and c != "nmcli radio wifi"]
    return out.splitlines(), calls


def test_dead_router_reconnect_then_driver_reload_then_recovery(tmp_path):
    # the router answers on loops 1-2 (remembered), is dead on loops 3-9, answers again from 10
    out, calls = run(tmp_path, loops=12, dead=(2, 9))
    assert out[0] == "wifi-watch: router 192.0.2.1 doesn't answer"
    assert out[1] == "wifi-watch: reconnecting wlan0 through NetworkManager"
    assert out[3] == "wifi-watch: restarting the Wi-Fi: reloading its driver (brcmfmac_cyw brcmfmac)"
    assert out[-1].startswith("wifi-watch: router 192.0.2.1 answers again, after ")
    assert calls == [
        "nmcli --wait 20 device disconnect wlan0",
        "nmcli --wait 60 device connect wlan0",
        "modprobe -r brcmfmac_cyw brcmfmac",
        "modprobe -a brcmfmac brcmfmac_cyw",
        "nmcli --wait 60 device connect wlan0",
    ]
    assert (tmp_path / "router").read_text().strip() == "192.0.2.1"


def test_waits_after_a_driver_reload_before_trying_again(tmp_path):
    out, calls = run(tmp_path, loops=14, dead=(2, 99))
    assert calls.count("modprobe -r brcmfmac_cyw brcmfmac") == 1
    assert calls.count("nmcli --wait 20 device disconnect wlan0") == 1


def test_router_that_never_answered_is_left_alone(tmp_path):
    out, calls = run(tmp_path, loops=8, dead=(0, 99))
    assert out == [] and calls == []


def test_a_router_known_from_before_a_reboot_counts(tmp_path):
    out, calls = run(tmp_path, loops=5, dead=(0, 99), state="192.0.2.1")
    assert "nmcli --wait 60 device connect wlan0" in calls


def test_ethernet_is_left_alone(tmp_path):
    out, calls = run(tmp_path, loops=8, dead=(0, 99), state="192.0.2.1", ethernet=True)
    assert out == [] and calls == []
