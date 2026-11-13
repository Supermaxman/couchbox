#!/usr/bin/python3
"""keys.py OUT.csv LASTKEY_MTIME STEP...: press remote buttons through couchbox-input (as root), noting
when each went in (CLOCK_MONOTONIC ns). Steps: a button name, name@HOLD (seconds held), NAMExN (N
presses), wait:SECONDS, gap:SECONDS (between presses, from then on), shot:NAME (a screenshot beside
OUT.csv), mode:NAME (the screen's mode now, into modes.txt). Stops if the real remote is pressed
(last-key changes: exit 5) or, with EXPECT=window-class, once that app is no longer in front (exit 6)."""

import json
import os
import pwd
import socket
import sys
import time

BUTTONS = {
    "up": "KEY_UP",
    "down": "KEY_DOWN",
    "left": "KEY_LEFT",
    "right": "KEY_RIGHT",
    "ok": "KEY_SELECT",
    "back": "KEY_BACK",
    "home": "KEY_HOMEPAGE",
    "menu": "KEY_MENU",
    "playpause": "KEY_PLAYPAUSE",
    "rewind": "KEY_REWIND",
    "forward": "KEY_FASTFORWARD",
}


RUN = f"/run/user/{pwd.getpwnam(os.environ.get('COUCHBOX_TV_USER', 'tv')).pw_uid}"  # the TV session's runtime folder
EXPECT = os.environ.get("EXPECT", "")  # the window class that must be in front for a key to be pressed


def front():
    import subprocess

    return subprocess.run(
        [
            "sudo",
            "-u",
            "tv",
            "env",
            f"XDG_RUNTIME_DIR={RUN}",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path={RUN}/bus",
            "WAYLAND_DISPLAY=wayland-0",
            "/usr/lib/couchbox/bin/couchbox-active-window",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout


def send(key, value):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect("/run/couchbox/input.sock")
    with s:
        s.sendall((json.dumps({"key": key, "value": value}) + "\n").encode())
        s.makefile("r").readline()


def main():
    out, key0, steps = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
    gap = 0.5
    with open(out, "w", buffering=1) as f:
        for st in steps:
            if st.startswith("wait:"):
                time.sleep(float(st[5:]))
                continue
            if st.startswith("shot:"):  # a screenshot of the TV, beside the key log
                import subprocess

                dst = os.path.join(os.path.dirname(out), st[5:] + ".png")
                subprocess.run(
                    [
                        "sudo",
                        "-u",
                        "tv",
                        "env",
                        f"XDG_RUNTIME_DIR={RUN}",
                        f"DBUS_SESSION_BUS_ADDRESS=unix:path={RUN}/bus",
                        "WAYLAND_DISPLAY=wayland-0",
                        "/usr/lib/couchbox/bin/couchbox-screenshot",
                        dst,
                    ],
                    capture_output=True,
                    timeout=20,
                )
                continue
            if st.startswith("mode:"):  # note the screen's mode now (refresh-rate matching)
                import re
                import subprocess

                o = subprocess.run(
                    ["sudo", "-u", "tv", "env", f"XDG_RUNTIME_DIR={RUN}", "WAYLAND_DISPLAY=wayland-0", "kscreen-doctor", "-o"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                ).stdout
                m = re.search(r"(\d+x\d+@[\d.]+)\*", re.sub(r"\x1b\[[0-9;]*m", "", o))
                with open(os.path.join(os.path.dirname(out), "modes.txt"), "a") as mf:
                    mf.write(f"{st[5:]} {m.group(1) if m else '?'}\n")
                continue
            if st.startswith("gap:"):
                gap = float(st[4:])
                continue
            name, _, n = st.partition("x")
            name, _, hold = name.partition("@")
            for _i in range(int(n or 1)):
                if int(os.stat("/run/couchbox/last-key").st_mtime) != key0:
                    sys.exit(5)
                if EXPECT and EXPECT not in front():  # the app under test left the front: no keys to anything else
                    sys.exit(6)
                t = time.monotonic_ns()
                send(BUTTONS[name], 1)
                time.sleep(float(hold or 0.04))
                send(BUTTONS[name], 0)
                f.write(f"{t},{name},{hold or 0}\n")
                time.sleep(gap)


main()
