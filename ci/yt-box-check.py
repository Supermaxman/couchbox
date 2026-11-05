#!/usr/bin/env python3
"""The YouTube app's key flows, on the box itself: the real remote path (couchbox-remote through
couchbox-input and the compositor), a screenshot after each step (couchbox-screenshot) and what
had the focus then (the app's control socket: {"op": "focus"}).

  sudo python3 ci/yt-box-check.py [--profile guest|pick|ID] [--out /tmp/yt-check] [--keep]

It starts couchbox-yt muted (COUCHBOX_MUTE=1, as the TV user, replacing one that's running), then:
Home; Search from the guide, typing on a keyboard and Enter; back Home; a video from Home;
Description and Back; scrubbing with the controls hidden; the related row and Up; the clock
moving; a paused seek back to 0:00 still showing a picture; the Shorts tab; a guest's Library,
Subscriptions and Settings; Who's watching from the guide (and Back). Each step prints
PASS or FAIL with what it saw, and saves OUT/NN-name.png and OUT/NN-name.json. --keep leaves
the app running at the end.

Before every key and every reading it checks that couchbox-yt is still the window in front and
that no Frigate pop-up is up; if either fails it stops at once ("ABORT: ..."), pressing nothing
more: a stray OK into a pop-up would open a camera on the TV.
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


def cast_checks(r):
    """Casting (couchbox-yt-cast, which the app starts): its control socket, DIAL's device
    description, and an answer to an SSDP search (and whose answers came back: VacuumTube's?)."""
    import re
    import socket
    import urllib.request

    from couchbox import appctl

    r.n += 1
    ping = {}
    for _ in range(20):
        try:
            ping = appctl.call("yt-cast", {"op": "ping"}, timeout=3)
            break
        except Exception:  # noqa: BLE001  (still starting)
            time.sleep(1)
    ok = bool(ping.get("ok"))
    r.failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {r.n:02d} cast-running: {ping or 'no answer on its control socket'}", flush=True)

    r.n += 1
    try:
        dd = urllib.request.urlopen("http://127.0.0.1:56789/dd.xml", timeout=5).read().decode()
        name = (re.search(r"<friendlyName>(.*?)</friendlyName>", dd) or [None, ""])[1]
    except OSError as err:
        name = f"(none: {err})"
    ok = name == "Couchbox YouTube (beta)"
    r.failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {r.n:02d} cast-dial: /dd.xml names {name!r}", flush=True)

    r.n += 1
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.settimeout(0.5)
    msg = (
        b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\n'
        b"ST: urn:dial-multiscreen-org:service:dial:1\r\n\r\n"
    )
    seen = {}
    try:
        sock.sendto(msg, ("239.255.255.250", 1900))
        end = time.time() + 3
        while time.time() < end:
            try:
                data, _addr = sock.recvfrom(4096)
            except TimeoutError:
                continue
            loc = (re.search(r"(?im)^location:\s*(\S+)", data.decode("utf-8", "replace")) or [None, ""])[1]
            if loc and loc not in seen:
                try:
                    dd = urllib.request.urlopen(loc, timeout=3).read().decode()
                    seen[loc] = (re.search(r"<friendlyName>(.*?)</friendlyName>", dd) or [None, "?"])[1]
                except OSError:
                    seen[loc] = "?"
    finally:
        sock.close()
    ours = any(":56789/" in loc for loc in seen)
    r.failed += 0 if ours else 1
    others = [f"{name} ({loc})" for loc, name in seen.items() if ":56789/" not in loc]
    print(
        f"{'PASS' if ours else 'FAIL'} {r.n:02d} cast-ssdp: our answer {'came' if ours else 'did not come'}; "
        f"others: {', '.join(others) or 'none'}",
        flush=True,
    )


def save_log(unit, out):
    """The app's output (its journal) beside the screenshots: OUT/app.log."""
    try:
        log = subprocess.run(
            [*tv_env(), "journalctl", "--user", "-u", unit, "--no-pager", "-o", "short-monotonic"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
        with open(os.path.join(out, "app.log"), "w") as fh:
            fh.write(log)
    except (OSError, subprocess.TimeoutExpired) as err:
        print(f"(no app log: {err})")


def tv_env():
    uid = pwd.getpwnam(TV_USER).pw_uid
    run = f"/run/user/{uid}"
    return ["sudo", "-u", TV_USER, "env", f"XDG_RUNTIME_DIR={run}", f"DBUS_SESSION_BUS_ADDRESS=unix:path={run}/bus"]


def guard():
    """Stop here, pressing nothing more, if a Frigate pop-up is up or couchbox-yt isn't in front."""
    uid = pwd.getpwnam(TV_USER).pw_uid
    why = ""
    if os.path.exists(f"/run/user/{uid}/couchbox/frigate-popup.shown"):
        why = "a Frigate pop-up is showing"
    else:
        try:
            front = subprocess.run(
                [*tv_env(), "WAYLAND_DISPLAY=wayland-0", "/usr/lib/couchbox/bin/couchbox-active-window"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout
        except (OSError, subprocess.TimeoutExpired) as err:
            front = f"(couldn't tell: {err})"
        if "couchbox-yt" not in front:
            why = f"the window in front is {front.strip()[:200] or 'unknown'}"
    if why:
        print(f"ABORT: pop-up / another window in front ({why}); pressing nothing more", flush=True)
        os._exit(4)


def remote(*keys, gap=0.4):
    for k in keys:  # one at a time, checking before each
        guard()
        subprocess.run(["couchbox-remote", k], check=False, stdout=subprocess.DEVNULL)
        time.sleep(gap)


def brightness(png, box):
    """The mean brightness (0-255) of box = (x, y, w, h) in a screenshot, sampled on a grid."""
    from PySide6.QtGui import QImage

    img = QImage(png)
    if img.isNull():
        return -1.0
    sx, sy = img.width() / 1920, img.height() / 1080
    x0, y0, w, h = box
    total = n = 0
    for j in range(20):
        for i in range(40):
            c = img.pixelColor(int((x0 + w * (i + 0.5) / 40) * sx), int((y0 + h * (j + 0.5) / 20) * sy))
            total += (c.red() + c.green() + c.blue()) / 3
            n += 1
    return total / n


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
        guard()
        self.n += 1
        base = os.path.join(self.out, f"{self.n:02d}-{name}")
        self.png = base + ".png"
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


def picture(r, name):
    """The last screenshot's video area (above the chapters' strip and the bar, dimmed 45%) isn't black."""
    lum = brightness(r.png, (200, 60, 1520, 260))
    ok = lum > 10
    r.failed += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'} {r.n:02d} {name}: mean brightness {lum:.1f} of the video area (black is under 10)", flush=True)


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
    unit = f"{UNIT}-{int(time.time())}"
    subprocess.run(
        [
            *tv_env(),
            "systemd-run",
            "--user",
            "--quiet",
            "--collect",
            f"--unit={unit}",
            "--setenv=COUCHBOX_MUTE=1",
            "--setenv=COUCHBOX_MPV_LOG=1",  # mpv's warnings, and what draws after a seek (mpv-debug lines)
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
    remote("down")  # Home's second row (its cards large, the first row gone above)
    r.step("home-row2", lambda f: (f["page"] == "home" and "home" in f["focus"], "Home's second row"), settle=2)
    remote("up")

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

    # paused seeks still show a picture (not black): one back into the middle, one back to 0:00 and
    # one forward to 30 s, so "any paused seek" can be told from "only to the start". Up: the bar,
    # where Left / Right seek 10 s
    remote("playpause")
    f = r.step("paused", lambda f: (bool(d(f).get("paused")), f"paused at {d(f).get('position')}"), settle=1)
    picture(r, "paused-picture")
    at = d(f).get("position", 0)
    remote("up", *(["left"] if at >= 12 else []))
    r.step("paused-seek-mid", lambda f: (bool(d(f).get("paused")), f"position {at} -> {d(f).get('position')}"), settle=2.5)
    picture(r, "paused-seek-mid-picture")
    remote("left", "left", "left", "left")
    r.step(
        "paused-seek-0",
        lambda f: (d(f).get("position", 99) <= 1 and bool(d(f).get("paused")), f"position {d(f).get('position')}"),
        settle=2.5,
    )
    picture(r, "paused-seek-0-picture")
    remote("right", "right", "right")
    r.step("paused-seek-30", lambda f: (bool(d(f).get("paused")), f"position {d(f).get('position')}"), settle=2.5)
    picture(r, "paused-seek-30-picture")
    remote("playpause", "down")
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

    # the settings menu: Quality, then Playback speed (and Back out of each)
    remote(*["right"] * 13, "ok")
    r.step("player-settings", lambda f: (d(f).get("panel") == "settings", f"panel {d(f).get('panel')!r}"), settle=1.5)
    remote("ok")
    r.step("player-quality", lambda f: (d(f).get("panel") == "quality", f"panel {d(f).get('panel')!r}"), settle=1.5)
    remote("back", "down", "ok")
    r.step("player-speed", lambda f: (d(f).get("panel") == "speed", f"panel {d(f).get('panel')!r}"), settle=1.5)
    remote("back", "back")
    r.step(
        "player-settings-back", lambda f: (not d(f).get("panel") and "controls" in f["focus"], f"panel {d(f).get('panel')!r}"), settle=1.5
    )
    # captions: CC on (when the video has any: else the TV says so) and off again
    remote("left", "ok")
    f = r.step("captions-on", lambda f: (True, f"captions {d(f).get('captions')!r} (none: the video has no captions)"), settle=2)
    if d(f).get("captions"):
        remote("ok")
        r.step("captions-off", lambda f: (not d(f).get("captions"), f"captions {d(f).get('captions')!r}"), settle=1.5)
    # comments, from the Description panel's Comments card
    remote(*["left"] * 11, "ok")
    r.step("description-again", lambda f: (d(f).get("panel") == "description", f"panel {d(f).get('panel')!r}"), settle=2)
    for _ in range(4):  # Down to the Comments card (cards without content are skipped)
        if d(focus()).get("card") == 3:
            break
        remote("down")
    remote("ok")
    r.step(
        "comments",
        lambda f: (d(f).get("panel") == "comments", f"panel {d(f).get('panel')!r} (Summary may be missing: then the card above)"),
        settle=3,
    )
    remote("back")
    if d(focus()).get("panel"):
        remote("back")
    r.step("comments-back", lambda f: (not d(f).get("panel"), f"panel {d(f).get('panel')!r}"), settle=1.5)

    # the channel's panel (its picture, Subscribe, Go to channel), then its page, and Back to the player
    remote(*["left"] * 6, "ok")
    r.step("channel-panel", lambda f: (d(f).get("panel") == "channel" and "panel" in f["focus"], f"panel {d(f).get('panel')!r}"), settle=2)
    remote("down", "ok")
    r.step("channel-page", lambda f: (f.get("page") == "channel" and "channel" in f["focus"], f"page {f.get('page')}"), settle=4)
    remote("down")
    r.step("channel-page-down", lambda f: (f.get("page") == "channel", "the next shelf"), settle=1.5)
    remote("back")
    r.step("channel-back", lambda f: (f.get("page") == "player" and "controls" in f["focus"], f"page {f.get('page')}"), settle=2)

    # out of the player, then the Shorts tab: straight into Shorts
    remote("back", "back")
    r.step("player-left", lambda f: (f["page"] == "home", f"page {f.get('page')}"), settle=2)
    remote("left", "down", "ok")  # the guide on Home, Down: Shorts
    f = r.step("shorts", lambda f: ("shorts" in f["focus"], f"focus {f.get('focus')}"), settle=5)
    first = d(f).get("videoId")
    remote("down")  # the next Short
    r.step("shorts-next", lambda f: (bool(d(f).get("videoId")) and d(f).get("videoId") != first, f"Short {d(f).get('index')}"), settle=4)
    remote("up")
    r.step("shorts-previous", lambda f: (d(f).get("videoId") == first, f"Short {d(f).get('index')}"), settle=3)
    remote("back")
    r.step("shorts-back", lambda f: ("guide" in f["focus"], "back on the guide"), settle=1.5)

    # a guest's Library (the tiles that need no account), Subscriptions (the sign-in note), Settings
    # beside the open guide, and Who's watching from the guide's picture (and Back from it)
    # the tabs: Music, Gaming, Movies & TV (their shelves load), then Library
    remote("down", "ok")  # Shorts -> Music
    r.step(
        "tab-music",
        lambda f: (f.get("section") == "music" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    remote("left", "down", "down", "down", "ok")  # Music -> Subscriptions, Library, Gaming
    r.step(
        "tab-gaming",
        lambda f: (f.get("section") == "gaming" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    remote("left", "down", "down", "down", "ok")  # Gaming -> News, Podcasts, Movies & TV
    r.step(
        "tab-movies",
        lambda f: (f.get("section") == "movies" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    remote("left", "up", "up", "up", "up", "ok")  # Movies & TV -> Podcasts, News, Gaming, Library
    r.step("library", lambda f: (f.get("section") == "library" and "tiles" in f["focus"], f"section {f.get('section')}"), settle=2)
    remote("down")
    r.step("library-signin", lambda f: ("action" in f["focus"], "the Sign in button"), settle=1)
    remote("left", "up", "ok")
    r.step(
        "subscriptions",
        lambda f: (f.get("section") == "subscriptions" and "message" in f["focus"], f"section {f.get('section')}"),
        settle=2,
    )
    remote("left", *["down"] * 8, "ok", gap=0.35)  # Subscriptions -> ... -> Settings
    r.step(
        "settings",
        lambda f: (
            f.get("section") == "settings" and "settings" in f["focus"] and f.get("guideOpen"),
            f"guide open {f.get('guideOpen')}, on {d(f).get('item')}",
        ),
        settle=2,
    )
    # Extras: into its rows, Hide Shorts flipped and flipped back (the TV's setting is left as it was)
    remote(*["down"] * 6, "right", "down", "down")  # Accounts, Video, Player, Ads, Guide tabs, SponsorBlock -> Extras
    f = r.step("settings-row", lambda f: (d(f).get("row") == "hide_shorts", f"on row {d(f).get('row')}"), settle=1)
    was = d(f).get("on")
    remote("ok")
    r.step("settings-flip", lambda f: (d(f).get("on") == (not was), f"Hide Shorts {was} -> {d(f).get('on')}"), settle=1.5)
    remote("ok")
    r.step("settings-flip-back", lambda f: (d(f).get("on") == was, f"Hide Shorts back to {d(f).get('on')}"), settle=1.5)
    remote("left", "down")
    r.step("settings-about", lambda f: (d(f).get("item") == "about", f"on {d(f).get('item')}"), settle=1)
    remote("left", *["up"] * 13, "ok", gap=0.3)  # the guide, up to its picture: Who's watching
    r.step("profiles", lambda f: ("profiles" in f["focus"], f"focus {f.get('focus')}"), settle=2)
    remote("back")
    r.step("profiles-back", lambda f: ("guide" in f["focus"], f"focus {f.get('focus')}"), settle=1.5)

    cast_checks(r)
    save_log(unit, a.out)
    if not a.keep:
        subprocess.run(["pkill", "-u", TV_USER, "-f", APP], check=False)
    print(f"{r.n - r.failed}/{r.n} passed; screenshots and focus in {a.out}")
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
