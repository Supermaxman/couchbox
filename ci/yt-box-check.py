#!/usr/bin/env python3
"""The YouTube app's key flows, on the box itself: the real remote path (couchbox-remote through
couchbox-input and the compositor), a screenshot after each step (couchbox-screenshot) and what
had the focus then (the app's control socket: {"op": "focus"}).

  sudo python3 ci/yt-box-check.py [--profile guest|pick|ID] [--out /tmp/yt-check] [--keep]

It starts couchbox-yt muted (COUCHBOX_MUTE=1, as the TV user, replacing one that's running), then:
Home; Search from the guide, typing on a keyboard and Enter; back Home; a video from Home;
Description and Back; scrubbing with the controls hidden; the related row and Up; the clock
moving; the Shorts tab. Each step prints PASS or FAIL with what it saw, and saves
OUT/NN-name.png and OUT/NN-name.json. --keep leaves the app running at the end.
"""

import argparse
import json
import os
import pwd
import subprocess
import sys
import time

TV_USER = os.environ.get("COUCHBOX_TV_USER", "tv")
APP = "/usr/lib/couchbox/bin/couchbox-yt"
UNIT = "couchbox-yt-check"


def tv_env():
    uid = pwd.getpwnam(TV_USER).pw_uid
    run = f"/run/user/{uid}"
    return ["sudo", "-u", TV_USER, "env", f"XDG_RUNTIME_DIR={run}", f"DBUS_SESSION_BUS_ADDRESS=unix:path={run}/bus"]


def remote(*keys, gap=0.4):
    subprocess.run(["couchbox-remote", "--gap", str(gap), *keys], check=False, stdout=subprocess.DEVNULL)


def focus():
    """The app's focus report: {focus, shown, section, guideOpen, detail, page}."""
    from couchbox import appctl

    try:
        return appctl.call("yt", {"op": "focus"}, timeout=5)
    except Exception as err:  # noqa: BLE001  (not running, an old build...)
        return {"error": str(err)}


class Run:
    def __init__(self, out):
        self.out, self.n, self.failed = out, 0, 0
        os.makedirs(out, exist_ok=True)

    def step(self, name, ok, settle=1.5):
        """Wait, screenshot, read the focus; ok(f) -> (passed, what it saw)."""
        time.sleep(settle)
        self.n += 1
        base = os.path.join(self.out, f"{self.n:02d}-{name}")
        f = focus()  # first: the picture comes a moment later, and the focus is what's checked
        subprocess.run(["couchbox-screenshot", base + ".png"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        f2 = focus()
        if f2.get("detail", {}).get("mode") != f.get("detail", {}).get("mode"):
            f["changedDuringShot"] = f2  # the controls hid (or showed) while the picture was taken
        with open(base + ".json", "w") as fh:
            json.dump(f, fh, indent=1)
        try:
            passed, saw = ok(f)
        except Exception as err:  # noqa: BLE001
            passed, saw = False, f"check failed: {err}"
        self.failed += 0 if passed else 1
        print(
            f"{'PASS' if passed else 'FAIL'} {self.n:02d} {name}: {saw}  [{f.get('page')}: {f.get('focus')}{'' if f.get('shown', True) else ' (hidden!)'}]",
            flush=True,
        )
        return f


def d(f):
    return f.get("detail") or {}


def show_controls():
    """The player's controls up (from hidden, Down shows them, on Play/Pause)."""
    if d(focus()).get("mode") == "hidden":
        remote("down")
        time.sleep(0.6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="guest")
    ap.add_argument("--out", default="/tmp/yt-check")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    r = Run(a.out)

    # a fresh app, muted, as the TV user in its session
    subprocess.run(["pkill", "-u", TV_USER, "-f", APP], check=False)
    time.sleep(1)
    subprocess.run(
        [
            *tv_env(),
            "systemd-run",
            "--user",
            "--quiet",
            "--collect",
            f"--unit={UNIT}-{int(time.time())}",
            "--setenv=COUCHBOX_MUTE=1",
            "--",
            APP,
            "--profile",
            a.profile,
        ],
        check=True,
    )
    for _ in range(60):
        if "focus" in focus():
            break
        time.sleep(1)
    else:
        sys.exit("FAIL couchbox-yt didn't come up (no answer on its control socket)")

    r.step("home", lambda f: (f["page"] == "home" and "home" in f["focus"] and f["shown"], "Home, a card in focus"), settle=6)

    # Search from the guide: the keys (not the last results); typing on a keyboard, then Enter
    remote("left", "up", "ok")
    r.step(
        "search-open",
        lambda f: (
            f["page"] == "search" and "keys" in f["focus"] and not d(f).get("results"),
            f"keys page, {d(f).get('area')} {d(f).get('item')}",
        ),
    )
    remote("KEY_S", "KEY_K", "KEY_Y", gap=0.2)
    r.step("search-typed", lambda f: (d(f).get("query") == "sky", f"query {d(f).get('query')!r}"))
    remote("KEY_ENTER")
    r.step(
        "search-enter", lambda f: (bool(d(f).get("results")) and d(f).get("query") == "sky", f"results for {d(f).get('query')!r}"), settle=4
    )
    remote("left", "ok")  # the guide (on Search), OK: Search again
    r.step("search-reopen", lambda f: ("keys" in f["focus"] and not d(f).get("results"), "Search again: the keys"))

    # a video from Home
    remote("left", "down", "ok")
    r.step("home-again", lambda f: (f["page"] == "home", "Home"), settle=2)
    remote("ok")
    r.step(
        "player",
        lambda f: (
            f["page"] == "player" and "controls" in f["focus"] and d(f).get("button") == "play",
            f"mode {d(f).get('mode')}, on {d(f).get('button')}",
        ),
        settle=4,
    )
    show_controls()  # (they hide after 5 s: Left would seek instead)
    remote("left", "left", "left", "ok")
    r.step(
        "description",
        lambda f: ("description" in f["focus"] and f["shown"] and d(f).get("panel") == "description", f"panel {d(f).get('panel')!r}"),
        settle=3,
    )
    remote("back")
    r.step(
        "description-back",
        lambda f: (
            f["page"] == "player" and "controls" in f["focus"] and d(f).get("button") == "description",
            f"on {d(f).get('button')}, panel {d(f).get('panel')!r}",
        ),
    )

    # the clock moves; scrubbing with the controls hidden
    p1 = d(focus()).get("position", 0)
    r.step("clock", lambda f: (d(f).get("position", 0) > p1, f"position {p1} -> {d(f).get('position')}"), settle=3)
    time.sleep(6)  # the controls hide
    r.step("controls-hidden", lambda f: (d(f).get("mode") == "hidden", f"mode {d(f).get('mode')}"), settle=0)
    remote("right")
    r.step("scrub", lambda f: (d(f).get("mode") == "bar" and "controls" in f["focus"], f"mode {d(f).get('mode')}"), settle=0.6)
    remote("down")
    f = r.step("scrub-down", lambda f: (d(f).get("mode") == "controls", f"mode {d(f).get('mode')}, on {d(f).get('button')}"), settle=0.6)
    last = d(f).get("button") or "play"  # Up from the related row comes back to this one

    # the related row, and Up back to the controls
    remote("down")
    r.step("related", lambda f: (d(f).get("mode") == "related" and "related" in f["focus"], f"mode {d(f).get('mode')}"), settle=1)
    remote("up")
    r.step(
        "related-up",
        lambda f: (
            d(f).get("mode") == "controls" and "controls" in f["focus"] and d(f).get("button") == last,
            f"mode {d(f).get('mode')}, on {d(f).get('button')}",
        ),
        settle=1,
    )

    # out of the player, then the Shorts tab: straight into Shorts
    remote("back", "back")
    r.step("player-left", lambda f: (f["page"] == "home", f"page {f.get('page')}"), settle=2)
    remote("left", "down", "ok")  # the guide on Home, Down: Shorts
    r.step("shorts", lambda f: ("shorts" in f["focus"], f"focus {f.get('focus')}"), settle=5)
    remote("back")
    r.step("shorts-back", lambda f: ("guide" in f["focus"], "back on the guide"), settle=1.5)

    if not a.keep:
        subprocess.run(["pkill", "-u", TV_USER, "-f", APP], check=False)
    print(f"{r.n - r.failed}/{r.n} passed; screenshots and focus in {a.out}")
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
