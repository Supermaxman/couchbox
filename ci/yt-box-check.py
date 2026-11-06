#!/usr/bin/env python3
"""The YouTube app's key flows, on the box itself: the real remote path (couchbox-remote through
couchbox-input and the compositor), a screenshot after each step (couchbox-screenshot) and what
had the focus then (the app's control socket: {"op": "focus"}).

  sudo python3 ci/yt-box-check.py [--profile guest|pick|ACCOUNT[:PAGE]] [--out /tmp/yt-check] [--keep] [--perf]

It starts couchbox-yt muted (COUCHBOX_MUTE=1, as the TV user, replacing one that's running), then:
Home; Search from the guide, typing on a keyboard and Enter; back Home; a video from Home;
Description and Back; scrubbing with the controls hidden; the related row and Up; the clock
moving; a paused seek back to 0:00 still showing a picture; the Shorts tab; a guest's Library,
Subscriptions and Settings; Who's watching from the guide (and Back). Each step prints
PASS or FAIL with what it saw, and saves OUT/NN-name.png and OUT/NN-name.json. --keep leaves
the app running at the end.

--profile ACCOUNT (an account id from ~/.local/share/couchbox-yt/accounts, or ACCOUNT:PAGE for a
brand channel) runs the signed-in steps instead, read only, for the household's real account:
Who's watching, Home, Subscriptions, Library's History, Watch later and Playlists, one
part-watched video from History (under a minute: it must start where YouTube says), the channel
and notification panels opened and closed, and Settings → Accounts. Nothing is liked,
subscribed, saved or changed; the guest's "Sign in" steps and casting aren't run.

--clean-history RUNDIR --profile ACCOUNT [--dry-run] removes from the account's History the
videos that run played (from RUNDIR/app.log), only their entries in today's History, listing
them first (--dry-run: only that). Signed-in runs go into the household's History otherwise.

--perf times the app instead (as the profile given, guest by default): start until Home shows,
3 videos at once and 3 after 5 s on their card (prefetched) from OK to their first picture (the stream in yt-dlp's parts, mpv opening it,
the first frame, a TV refresh switch), opening Search, 3 of Home's rows (keys, calls, late
frames), every back-end call's median and worst, and the app's processor use and memory: PERF
lines, and OUT/perf.json.

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


def picture(r, name, ref=None):
    """The last screenshot's video area (above the chapters' strip and the bar, dimmed 45%) isn't
    black: over 10, or at least a quarter as bright as ref (another frame of the same video: its
    first frame may be dark). Returns the brightness."""
    lum = brightness(r.png, (200, 60, 1520, 260))
    ok = lum > 10 or (ref is not None and ref > 0 and lum >= 0.25 * ref)
    r.failed += 0 if ok else 1
    than = f", {ref:.1f} mid-video" if ref is not None else ""
    print(f"{'PASS' if ok else 'FAIL'} {r.n:02d} {name}: mean brightness {lum:.1f} of the video area (black is under 10{than})", flush=True)
    return lum


def show_controls():
    """The player's controls up (from hidden, Down shows them, on Play/Pause)."""
    if d(focus()).get("mode") == "hidden":
        remote("down")
        time.sleep(0.6)


def anchor(target="home"):
    """Show target (home, settings...) through the app's control socket: no keys pressed."""
    from couchbox import appctl

    guard()
    try:
        appctl.call("yt", {"op": "open", "target": target}, timeout=5)
    except Exception as err:  # noqa: BLE001
        print(f"(couldn't open {target}: {err})", flush=True)
    time.sleep(2)


def to_entry(key):
    """From Home (opened through the socket), the guide, Up / Down to its entry `key`, and OK."""
    anchor("home")
    if guide_to(key):
        ok_on(lambda f: f.get("guideAt") == key, f"the guide's {key}")
    else:
        print(f"(the guide has no {key} entry)", flush=True)


def guest(r):
    """A guest's flows (the steps that expect "Sign in" among them)."""
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

    # a video from Home longer than 5 minutes (a short one ends mid-walk: Up next takes over)
    remote("left", "down", "ok")
    r.step("home-again", lambda f: (f["page"] == "home", "Home"), settle=2)
    long_video = lambda c: c.get("type") == "video" and not c.get("live") and c.get("duration", 0) > 300  # noqa: E731
    found = None
    for _ in range(4):  # along a row, then the next row down
        found = card_to(long_video, tries=7)
        if found:
            break
        remote("down")
    print(f"(the video: {found and found.get('duration')} s long)" if found else "(no video over 5 minutes on Home's first rows: the first card)", flush=True)
    if found:
        ok_on(lambda f: long_video(f.get("card") or {}), "a video over 5 minutes")
    else:
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
    mid = picture(r, "paused-seek-mid-picture")
    remote("left", "left", "left", "left")
    r.step(
        "paused-seek-0",
        lambda f: (d(f).get("position", 99) <= 1 and bool(d(f).get("paused")), f"position {d(f).get('position')}"),
        settle=2.5,
    )
    picture(r, "paused-seek-0-picture", ref=mid)
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

    # out of the player, then the Shorts tab: straight into Shorts. From here each part starts from
    # Home, opened through the control socket, so one that goes wrong doesn't throw the rest out
    remote("back", "back")
    r.step("player-left", lambda f: (f["page"] == "home", f"page {f.get('page')}"), settle=2)
    to_entry("shorts")
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
    to_entry("music")
    r.step(
        "tab-music",
        lambda f: (f.get("section") == "music" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    to_entry("gaming")
    r.step(
        "tab-gaming",
        lambda f: (f.get("section") == "gaming" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    to_entry("movies")
    r.step(
        "tab-movies",
        lambda f: (f.get("section") == "movies" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
        settle=4,
    )
    # a live stream from the Live tab's first row: it's live, seeks back (behind live) and forward
    to_entry("live")
    r.step("tab-live", lambda f: (f.get("section") == "live" and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows"), settle=4)
    remote("ok")
    f = r.step(
        "live-player",
        lambda f: (f["page"] == "player" and bool(d(f).get("live")), f"live {d(f).get('live')}, {d(f).get('videoId')}"),
        settle=10,
    )
    if d(f).get("live"):
        if d(focus()).get("mode") != "hidden":
            remote("back")  # the controls hide: Left / Right seek (Back with them hidden leaves)
            time.sleep(1)
        remote("left")
        r.step("live-behind", lambda f: ("behind live" in (f.get("toast") or ""), f"toast {f.get('toast')!r}"), settle=1)
        remote("right", "right")  # forward to live again
        r.step("live-forward", lambda f: (bool(f.get("toast")), f"toast {f.get('toast')!r}"), settle=1)
    remote("back", "back")  # out of the player, back on the Live tab
    r.step("live-left", lambda f: (f.get("section") == "live" and f["page"] != "player", f"page {f.get('page')}"), settle=2)
    to_entry("library")
    r.step("library", lambda f: (f.get("section") == "library" and "tiles" in f["focus"], f"section {f.get('section')}"), settle=2)
    remote("down")
    r.step("library-signin", lambda f: ("action" in f["focus"], "the Sign in button"), settle=1)
    to_entry("subscriptions")
    r.step(
        "subscriptions",
        lambda f: (f.get("section") == "subscriptions" and "message" in f["focus"], f"section {f.get('section')}"),
        settle=2,
    )
    to_entry("settings")
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
    to_entry("who")  # the guide's picture: Who's watching
    r.step("profiles", lambda f: ("profiles" in f["focus"], f"focus {f.get('focus')}"), settle=2)
    remote("back")
    r.step("profiles-back", lambda f: ("guide" in f["focus"], f"focus {f.get('focus')}"), settle=1.5)



# ------------------------------------------------------------------ signed in (read only)
# The household's own account: nothing here may change it. No like, subscribe, bell level, save or
# playlist changes; comments are only read. OK is pressed only where it was checked, just before,
# that it opens something (ok_on); the player's buttons are reached one key at a time, reading which
# one has the focus. One video plays (from History), for under a minute.
PLAY_LIMIT = 45  # seconds in the player before leaving it


def skip(r, name, why):
    r.n += 1
    print(f"SKIP {r.n:02d} {name}: {why}", flush=True)


def ok_on(check, what):
    """OK, if check(focus) still holds (else nothing is pressed): returns whether it was pressed."""
    f = focus()
    if not check(f):
        print(f"(not pressing OK: the focus isn't on {what}: {f.get('focus')} {d(f)} {f.get('card')})", flush=True)
        return False
    remote("ok")
    return True


def guide_to(key):
    """The guide, then Up / Down to its entry `key` (None if it isn't in the guide)."""
    for _ in range(4):  # Left until the guide opens (from a page's first card)
        if focus().get("guideAt"):
            break
        remote("left")
        time.sleep(0.4)
    if not focus().get("guideAt"):
        return False
    for step in ("up", "down"):  # all the way up first (Who's watching is above the entries), then down
        for _ in range(16):
            at = focus().get("guideAt")
            if at == key:
                return True
            if step == "up" and at == "who":
                break
            remote(step, gap=0.3)
    return focus().get("guideAt") == key


def card_to(match, keys=("right",), tries=8):
    """Move (Right by default) until the focused card satisfies match(card)."""
    for _ in range(tries):
        c = focus().get("card") or {}
        if match(c):
            return c
        remote(*keys, gap=0.35)
    c = focus().get("card") or {}
    return c if match(c) else None


def button_to(name):
    """The player's control `name`, one Left / Right at a time (controls showing: else they seek)."""
    show_controls()
    order = ["channel", "description", "bell", "prev", "play", "next", "like", "dislike", "comments", "ask", "save", "thanks", "cc", "settings"]
    for _ in range(16):
        f = focus()
        b = d(f).get("button")
        if d(f).get("mode") != "controls" or d(f).get("panel"):
            return False
        if b == name:
            return True
        remote("left" if order.index(name) < order.index(b or "play") else "right", gap=0.3)
    return d(focus()).get("button") == name


def account(r, want):
    """Who's watching (the account, its brand channels), Home, Subscriptions, Library's lists, a video
    from History resuming where YouTube says, the channel and notification panels, Settings → Accounts."""
    f = r.step("profiles", lambda f: (f.get("page") == "profiles" and d(f).get("count", 0) >= 1,
                                      f"{d(f).get('count')} profiles, {d(f).get('brands')} brand channels"), settle=4)
    count = d(f).get("count", 0)
    remote(*["left"] * count, gap=0.3)  # the first, then each in turn, to the one wanted
    seen = []
    for _ in range(count + 1):
        g = focus()
        if d(g).get("area") != "row":
            break
        seen.append(d(g).get("id"))
        if d(g).get("id") == want:
            break
        remote("right", gap=0.4)
    r.step("profiles-account", lambda f: (d(f).get("id") == want and d(f).get("area") == "row",
                                          f"on the account after {len(seen)} ({len(set(seen))} different)"), settle=0.5)
    if not ok_on(lambda f: d(f).get("id") == want and d(f).get("area") == "row", "the account"):
        print("ABORT: the account isn't on Who's watching; pressing nothing more", flush=True)
        return
    r.step("home-signed-in", lambda f: (f.get("page") == "home" and f.get("signedIn") and f.get("profile") == want and d(f).get("rows", 0) > 0,
                                        f"signed in {f.get('signedIn')}, {d(f).get('rows')} rows {d(f).get('problem') or ''}"), settle=6)

    # Subscriptions: the channels down the side and the feed; a channel's own feed
    if guide_to("subscriptions") and ok_on(lambda f: f.get("guideAt") == "subscriptions", "Subscriptions"):
        r.step("subscriptions", lambda f: (f.get("section") == "subscriptions" and d(f).get("channels", 0) > 1 and d(f).get("rows", 0) > 0,
                                           f"{d(f).get('channels')} channels, {d(f).get('rows')} rows {d(f).get('problem') or ''}"), settle=4)
        remote("right")
        r.step("subscriptions-feed", lambda f: (d(f).get("inFeed") and (f.get("card") or {}).get("type") in ("video", "live", "short"),
                                                f"in the feed on a {(f.get('card') or {}).get('type')}"), settle=1)
        remote("left")
        remote("down")
        r.step("subscriptions-channel", lambda f: (d(f).get("picked") == 1 and d(f).get("rows", 0) > 0,
                                                   f"channel {d(f).get('picked')}: {d(f).get('rows')} rows"), settle=3)
    else:
        skip(r, "subscriptions", "not in the guide")

    # Library: History, Watch later, Playlists (each opened and Back)
    if not (guide_to("library") and ok_on(lambda f: f.get("guideAt") == "library", "Library")):
        skip(r, "library", "not in the guide")
        return settings_accounts(r)
    r.step("library", lambda f: (f.get("section") == "library" and (f.get("card") or {}).get("type") == "tile",
                                 f"{d(f).get('rows')} rows, on {(f.get('card') or {}).get('title')}"), settle=3)
    for tile, name in (("FEhistory", "history"), ("VLWL", "watch-later"), ("FEplaylist_aggregation", "playlists")):
        c = card_to(lambda c, t=tile: c.get("id") == t, tries=5)  # left to right: Back leaves the focus on the last
        if not c or not ok_on(lambda f, t=tile: (f.get("card") or {}).get("id") == t, tile):
            skip(r, f"library-{name}", "no such tile")
            continue
        r.step(f"library-{name}", lambda f, t=tile: (f.get("page") == "list" and d(f).get("browseId") == t and d(f).get("loaded"),
                                                     f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"), settle=4)
        remote("back")
        r.step(f"library-{name}-back", lambda f: (f.get("section") == "library" and f.get("page") != "list", f"page {f.get('page')}"), settle=1.5)

    # a part-watched video from History: it starts where YouTube says this account left off
    if not (card_to(lambda c: c.get("id") == "FEhistory", keys=("left",), tries=3) and ok_on(lambda f: (f.get("card") or {}).get("id") == "FEhistory", "History")):
        skip(r, "history-video", "no History tile")
        return settings_accounts(r)
    time.sleep(4)
    part = lambda c: c.get("type") == "video" and 0.03 < (c.get("progress") or 0) < 0.9  # noqa: E731
    c = card_to(part, tries=6) or card_to(part, keys=("down",), tries=3)
    if not c:
        skip(r, "history-video", "no part-watched video among History's first cards: resume not checked, nothing played")
        remote("back")
        return settings_accounts(r)
    if not ok_on(lambda f: part(f.get("card") or {}), "a part-watched video"):
        return settings_accounts(r)
    started = time.time()
    f = r.step("history-video", lambda f: (f.get("page") == "player" and d(f).get("startAt", 0) > 0,
                                           f"starts at {d(f).get('startAt')} s of {d(f).get('duration')} (card: {round(c['progress'] * 100)}% watched)"),
               settle=8)
    expect = c["progress"] * (d(f).get("duration") or 0)
    r.step("history-resumed", lambda f: (d(f).get("startAt", 0) > 0 and d(f).get("position", 0) >= d(f).get("startAt", 0) - 3
                                         and (not expect or abs(d(f).get("startAt", 0) - expect) < max(30, 0.05 * expect)),
                                         f"position {d(f).get('position')}, from {d(f).get('startAt')} (the card says about {round(expect)})"), settle=1)

    # the channel's panel (Back only: its first row is Subscribe), the bell's levels (only when
    # already subscribed: else the bell subscribes), the comments (read)
    if button_to("channel") and ok_on(lambda f: d(f).get("button") == "channel" and not d(f).get("panel"), "the channel button"):
        r.step("channel-panel", lambda f: (d(f).get("panel") == "channel", f"panel {d(f).get('panel')!r}"), settle=2)
        remote("back")
        r.step("channel-panel-closed", lambda f: (not d(f).get("panel"), f"panel {d(f).get('panel')!r}"), settle=1.5)
    else:
        skip(r, "channel-panel", "couldn't reach the channel button")
    if not d(focus()).get("subscribed"):
        skip(r, "notifications", "not subscribed to this channel: the bell would subscribe, so it isn't pressed")
    elif button_to("bell") and ok_on(lambda f: d(f).get("button") == "bell" and d(f).get("subscribed") and not d(f).get("panel"), "the bell"):
        r.step("notifications", lambda f: (d(f).get("panel") == "notify", f"panel {d(f).get('panel')!r}"), settle=2)
        remote("back")
        r.step("notifications-closed", lambda f: (not d(f).get("panel"), f"panel {d(f).get('panel')!r}"), settle=1.5)
    if time.time() - started < PLAY_LIMIT - 10 and button_to("comments") and ok_on(lambda f: d(f).get("button") == "comments", "Comments"):
        r.step("comments", lambda f: (d(f).get("panel") == "comments", f"panel {d(f).get('panel')!r}"), settle=3)
        remote("back")
        if d(focus()).get("panel"):
            remote("back")
    remote("back", "back")  # out of the player: History
    r.step("player-left", lambda f: (f.get("page") != "player", f"page {f.get('page')} after {round(time.time() - started)} s of playing"), settle=1.5)
    remote("back")
    settings_accounts(r)


def settings_accounts(r):
    if guide_to("settings") and ok_on(lambda f: f.get("guideAt") == "settings", "Settings"):
        r.step("settings-accounts", lambda f: (f.get("section") == "settings" and d(f).get("item") == "accounts",
                                               f"on {d(f).get('item')}"), settle=2)
    else:
        skip(r, "settings-accounts", "Settings isn't in the guide")


# ------------------------------------------------------------------ perf: where the time goes
def pss(pid):
    try:
        with open(f"/proc/{pid}/smaps_rollup") as fh:
            return next((int(ln.split()[1]) for ln in fh if ln.startswith("Pss:")), 0) / 1024
    except (OSError, ValueError):
        return 0.0


def name_of(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            cmd = fh.read().decode(errors="replace")
    except OSError:
        return "?"
    return "worker" if "ytworker" in cmd else "node" if "--permission" in cmd else "app"


def all_pids():
    """The app, its stream worker and the worker's node."""
    out = subprocess.run(["pgrep", "-u", TV_USER, "-f", f"{APP}|couchbox.services.ytworker|--permission -e"],
                         capture_output=True, text=True, check=False).stdout.split()
    return [int(x) for x in out]


def app_pid():
    out = subprocess.run(["pgrep", "-u", TV_USER, "-f", APP], capture_output=True, text=True, check=False).stdout.split()
    return int(out[0]) if out else 0


def usage(pid):
    """(processor seconds used so far, resident MB) of pid."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            st = fh.read().rsplit(")", 1)[1].split()
        cpu = (int(st[11]) + int(st[12])) / os.sysconf("SC_CLK_TCK")
        with open(f"/proc/{pid}/status") as fh:
            rss = next((int(ln.split()[1]) for ln in fh if ln.startswith("VmRSS:")), 0) / 1024
        return cpu, rss
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0


def timing_since(mark):
    """The app's timing events (couchbox.services.yttiming) after `mark` (their "at")."""
    from couchbox import appctl

    try:
        ev = appctl.call("yt", {"op": "timing"}, timeout=5).get("timing") or []
    except Exception:  # noqa: BLE001
        return []
    return [e for e in ev if e.get("at", 0) > mark]


def last_at():
    ev = timing_since(-1)
    return ev[-1]["at"] if ev else 0.0


class Perf:
    def __init__(self, out):
        self.out, self.rows, self.pid = out, {}, app_pid()

    def memory(self, name):
        """The app's memory in parts (its control socket's "memory")."""
        from couchbox import appctl

        try:
            m = appctl.call("yt", {"op": "memory"}, timeout=10)
        except Exception as err:  # noqa: BLE001
            return self.say(f"{name}-memory", f"(no answer: {err})")
        a, procs = m.get("app") or {}, m.get("processes") or {}
        self.say(
            f"{name}-memory",
            f"app {a.get('Rss')} MB resident, {a.get('Pss')} proportional ({a.get('Anonymous')} anonymous, {a.get('Pss_File')} files); "
            "mpv cache " + (", ".join(f"{c['bytes_mb']} MB / {c['ahead_s']} s" for c in m.get("mpv_cache") or []) or "none")
            + "; " + ", ".join(f"{k} {sum(x.get('Rss', 0) for x in v)} MB ({sum(x.get('Pss', 0) for x in v)} PSS)" for k, v in procs.items())
            + f"; {m.get('python_objects')} Python objects; QML: {(m.get('qml') or {}).get('items')} items, "
            + f"{(m.get('qml') or {}).get('images')} pictures ({(m.get('qml') or {}).get('image_mb')} MB decoded); app by kind: "
            + ", ".join(f"{k} {v}" for k, v in (m.get("app_by_kind") or {}).items()),
            m,
        )
        return m

    def say(self, name, value, data=None):
        print(f"PERF {name}: {value}", flush=True)
        self.rows[name] = data if data is not None else value

    def phase(self, name, fn):
        """Run fn(); say its processor use and memory after it."""
        c0, _ = usage(self.pid)
        t0 = time.monotonic()
        fn()
        c1, rss = usage(self.pid)
        wall = time.monotonic() - t0
        self.memory(name)
        self.say(f"{name}-cpu", f"{100 * (c1 - c0) / max(wall, 0.1):.0f}% of one core over {wall:.0f} s, {rss:.0f} MB resident",
                 {"cpu_pct": round(100 * (c1 - c0) / max(wall, 0.1)), "seconds": round(wall, 1), "rss_mb": round(rss)})

    def save(self):
        with open(os.path.join(self.out, "perf.json"), "w") as fh:
            json.dump(self.rows, fh, indent=1)


def perf(r, started, signed=False):
    """Open the app, Home ready, 3 videos in turn to their first picture, Search, 3 of Home's rows:
    what each took (and the app's processor use and memory), from the app's own timing."""
    p = Perf(r.out)
    for _ in range(300):
        f = focus()
        if f.get("page") == "home" and d(f).get("rows", 0) > 0:
            break
        time.sleep(0.1)
    p.say("home-ready", f"{time.monotonic() - started:.1f} s from start", round(time.monotonic() - started, 2))
    time.sleep(1)
    steps = [e for e in timing_since(-1) if e["kind"] == "startup"]
    p.say("start-steps", ", ".join(f"{e['step']} {e['ms']} ms" for e in steps), steps)
    calls = [e for e in timing_since(-1) if e["kind"] == "call"]
    p.say("start-calls", ", ".join(f"{e['op']} {e['ms']} ms" for e in calls[:8]), calls[:8])
    p.pid = app_pid()
    p.phase("idle-home", lambda: time.sleep(10))

    # signed in: 3 videos in all (each goes into the household's History): 1 cold, 1 warm, 1 resumed;
    # the 10 videos for memory run as a guest only
    count = 1 if signed else 3

    def videos(kind, row, dwell):
        """Videos from Home's row `row`: OK at once (cold: no prefetch), or after `dwell` s on the card."""
        for i in range(count):
            anchor("home")
            time.sleep(2)
            remote(*["down"] * row, *["right"] * i, gap=0.35)
            c = card_to(lambda c: c.get("type") == "video" and not c.get("live"), tries=5)
            time.sleep(dwell)
            mark = last_at()
            name = f"video-{kind}-{i + 1}"
            if not c or not ok_on(lambda f: (f.get("card") or {}).get("type") == "video", "a video"):
                p.say(name, "no video card")
                continue
            play = None
            for _ in range(160):  # up to 40 s
                ev = timing_since(mark)
                play = next((e for e in ev if e["kind"] == "play"), None)
                if play:
                    break
                time.sleep(0.25)
            time.sleep(3)  # a refresh switch comes a few seconds in
            ev = timing_since(mark)
            stream = next((e for e in ev if e["kind"] == "stream"), {})
            rate = next((e for e in ev if e["kind"] == "rate"), None)
            key = next((e for e in ev if e["kind"] == "key"), {})
            stalls = [e["ms"] for e in ev if e["kind"] == "stall"]
            if not play:
                p.say(name, "no first frame in 40 s", {"events": ev})
                continue
            parts = {k: v for k, v in stream.items() if k not in ("at", "kind", "id")}
            p.say(
                name,
                f"first frame {play['total']} ms after OK (player page {key.get('ms', '?')} ms; stream {play['stream']} ms: "
                f"{', '.join(f'{k} {v}' for k, v in parts.items())}; mpv open {play['open']} ms, first frame {play['frame']} ms more"
                + (f", from {play.get('start')} s" if play.get("start") else "")
                + ")"
                + (f"; TV refresh switch {rate['ms']} ms ({rate['mode']}), {round((rate['at'] - play['at']) * 1000)} ms after the first frame"
                   if rate else "; no refresh switch")
                + (f"; GUI held up {stalls} ms" if stalls else ""),
                {"play": play, "stream": stream, "key": key, "rate": rate, "stalls": stalls},
            )
        anchor("home")

    p.phase("videos-cold", lambda: videos("cold", 1, 0))
    p.phase("videos-warm", lambda: videos("warm", 2, 5))

    def search():
        anchor("home")
        mark = last_at()
        if guide_to("search") and ok_on(lambda f: f.get("guideAt") == "search", "Search"):
            time.sleep(2)
            ev = timing_since(mark)
            keys = [e for e in ev if e["kind"] == "key"]
            p.say("search-open", f"{keys[-1]['ms'] if keys else '?'} ms from OK to the keys; "
                  + ", ".join(f"{e['op']} {e['ms']} ms" for e in ev if e["kind"] == "call"), ev)
        else:
            p.say("search-open", "Search isn't in the guide")

    p.phase("search", search)

    def rows():
        anchor("home")
        time.sleep(2)
        mark = last_at()
        for _ in range(3):
            remote("down")
            time.sleep(1.5)
        ev = timing_since(mark)
        keys = [e["ms"] for e in ev if e["kind"] == "key"]
        stalls = [e["ms"] for e in ev if e["kind"] == "stall"]
        p.say("home-rows", f"keys moved the focus in {keys} ms; {len(stalls)} late frames" + (f" (worst {max(stalls)} ms)" if stalls else "")
              + "; " + ", ".join(f"{e['op']} {e['ms']} ms" for e in ev if e["kind"] == "call"), ev)

    p.phase("home-rows", rows)

    def resume():
        """A long video opened at 5:00, as Continue watching does (no key: the control socket), and
        30 s of it playing: the processor use of the app, the worker and node."""
        anchor("home")
        time.sleep(2)
        long = None
        for _ in range(3):
            long = card_to(lambda c: c.get("type") == "video" and not c.get("live") and c.get("duration", 0) > 900, tries=6)
            if long:
                break
            remote("down", gap=0.35)
        if not long:
            p.say("resume", "no video over 15 minutes on Home's first rows")
            return
        mark = last_at()
        anchor(f"video:{long['id']}@300")
        play = None
        for _ in range(120):
            play = next((e for e in timing_since(mark) if e["kind"] == "play"), None)
            if play:
                break
            time.sleep(0.25)
        if not play:
            p.say("resume", "no first frame in 30 s")
            return
        ev = timing_since(mark)
        stream = next((e for e in ev if e["kind"] == "stream"), {})
        p.say("resume", f"first frame {play['total']} ms after it was asked for, from {play.get('start')} s "
              f"(stream {play['stream']} ms, {stream.get('protocol')}; mpv open {play['open']} ms, first frame {play['frame']} ms more)",
              {"play": play, "stream": stream})
        cpu_sample(p, "playing-cpu")
        anchor("home")

    def cpu_sample(p, name, seconds=30):
        """The processor use of the app, the worker and node while the video plays (it's made to
        play, and the position must move), with the video's resolution and fps."""
        from couchbox import appctl

        if d(focus()).get("paused"):
            appctl.call("yt", {"op": "media", "action": "play"}, timeout=5)
            time.sleep(1)
        pos0 = d(focus()).get("position", 0)
        pids = all_pids()
        c0 = {x: usage(x)[0] for x in pids}
        time.sleep(seconds)
        c1 = {x: usage(x)[0] for x in pids}
        f = focus()
        moved = d(f).get("position", 0) - pos0
        each = {}
        for x in pids:
            each[name_of(x)] = each.get(name_of(x), 0) + round(100 * (c1[x] - c0[x]) / seconds)
        total = sum(each.values())
        res = f"{d(f).get('height')}p{d(f).get('fps')}"
        p.say(name, f"{total}% of one core over {seconds} s of {d(f).get('videoId')} ({res}"
              + ("" if (d(f).get("height") or 0) >= 1080 else ": not 1080p, not comparable")
              + f"; it played {moved} s" + ("" if moved >= seconds - 3 else ": NOT PLAYING THROUGHOUT") + "): "
              + ", ".join(f"{k} {v}%" for k, v in each.items()), total if moved >= seconds - 3 else None)
        p.rows[f"{name}-video"] = res

    p.phase("resume", resume)

    def ten():
        """10 videos in turn, 6 s each: the memory after (app, worker and node)."""
        for i in range(10):
            anchor("home")
            time.sleep(1.5)
            remote(*["down"] * (i // 3), *["right"] * (i % 3), gap=0.3)
            if card_to(lambda c: c.get("type") == "video" and not c.get("live"), tries=4) and ok_on(
                lambda f: (f.get("card") or {}).get("type") == "video", "a video"
            ):
                time.sleep(6)
        anchor("home")
        time.sleep(3)
        p.memory("after-10-videos")
        total = sum(usage(x)[1] for x in all_pids())
        prop = sum(pss(x) for x in all_pids())
        p.say("after-10-videos-rss", f"{total:.0f} MB resident in all (app, worker, node), {prop:.0f} MB proportional (PSS)", round(total))
        p.rows["after-10-videos-pss"] = round(prop)

    def preload_quiet():
        """A card rested on (preloaded) without OK reports nothing to YouTube (no History)."""
        anchor("home")
        time.sleep(1)
        remote("down", gap=0.3)
        card_to(lambda c: c.get("type") == "video" and not c.get("live"), tries=4)
        mark = last_at()
        time.sleep(6)  # well past the prefetch and the preload
        ev = timing_since(mark)
        reports = [e for e in ev if e["kind"] == "call" and e.get("op") == "report"]
        streams = [e for e in ev if e["kind"] == "call" and e.get("op") == "stream"]
        r.n += 1
        ok = not reports
        r.failed += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'} {r.n:02d} preload-reports-nothing: {len(streams)} stream asked for (the preload), "
              f"{len(reports)} playback reports", flush=True)
        p.say("preload-reports", len(reports))

    p.phase("preload-quiet", preload_quiet)

    if signed:  # as a guest (the household's History stays out of it), then the account again
        anchor("as:guest")
        time.sleep(3)
    p.phase("ten-videos", ten)

    def known_1080p():
        """As a guest: a 1080p30 and a 1080p60 H.264 video, 30 s each, for comparing with VacuumTube."""
        for name, vid in (("cpu-1080p30", "kJQP7kiw5Fk"), ("cpu-1080p60", "LXb3EKWsInQ")):
            mark = last_at()
            anchor(f"video:{vid}@60")
            for _ in range(80):
                if any(e["kind"] == "play" for e in timing_since(mark)):
                    break
                time.sleep(0.25)
            time.sleep(2)
            cpu_sample(p, name)
        anchor("home")

    p.phase("known-1080p", known_1080p)


    if signed:
        anchor(f"as:{signed}")
        time.sleep(3)

    allcalls = [e for e in timing_since(-1) if e["kind"] == "call"]
    by = {}
    for e in allcalls:
        by.setdefault(e["op"], []).append(e["ms"])
    p.say("calls", "; ".join(f"{op} x{len(v)} median {sorted(v)[len(v) // 2]} max {max(v)} ms" for op, v in sorted(by.items())), by)
    stalls = [e["ms"] for e in timing_since(-1) if e["kind"] == "stall"]
    p.say("late-frames", f"{len(stalls)}" + (f", worst {max(stalls)} ms" if stalls else ""), stalls)
    summary(p)
    p.save()


TARGETS = (  # name, the perf rows' value, the most it may be, the unit (VacuumTube on the box: 406-484 ms, ~1081 MB)
    ("warm start", lambda r: max([v["play"]["total"] for k, v in r.items() if k.startswith("video-warm") and isinstance(v, dict) and "play" in v] or [None]), 400, "ms"),
    ("cold start", lambda r: max([v["play"]["total"] for k, v in r.items() if k.startswith("video-cold") and isinstance(v, dict) and "play" in v] or [None]), 700, "ms"),
    ("resume start", lambda r: (r.get("resume") or {}).get("play", {}).get("total") if isinstance(r.get("resume"), dict) else None, 800, "ms"),
    ("Home ready", lambda r: round(r["home-ready"] * 1000) if isinstance(r.get("home-ready"), (int, float)) else None, 1500, "ms"),
    ("worst GUI stall", lambda r: max(r.get("late-frames") or [0]), 100, "ms"),
    ("memory after 10 videos (RSS)", lambda r: r.get("after-10-videos-rss"), 450, "MB"),
    ("memory after 10 videos (PSS; VacuumTube 621-649)", lambda r: r.get("after-10-videos-pss"), 450, "MB"),
    ("CPU playing", lambda r: r.get("playing-cpu"), None, "% of a core"),
    ("CPU 1080p30 (as a guest)", lambda r: r.get("cpu-1080p30"), None, "% of a core"),
    ("CPU 1080p60 (as a guest; VacuumTube 157)", lambda r: r.get("cpu-1080p60"), None, "% of a core"),
    ("playback reports from a preload", lambda r: r.get("preload-reports"), 0, ""),
)


def summary(p):
    """One line per target: the value, and PASS or FAIL (CPU: compared with VacuumTube's, by hand)."""
    out = []
    for name, get, most, unit in TARGETS:
        try:
            v = get(p.rows)
        except (KeyError, TypeError, ValueError):
            v = None
        verdict = "n/a" if v is None else "info" if most is None else "PASS" if v <= most else "FAIL"
        out.append(f"{verdict} {name}: {v if v is not None else '-'} {unit}" + (f" (at most {most})" if most is not None else ""))
    print("SUMMARY\n  " + "\n  ".join(out), flush=True)
    p.rows["summary"] = out


def played_in(rundir):
    """The videos a run opened (its app.log: the timing's play lines, SponsorBlock's look-ups)."""
    import re

    ids = []
    try:
        with open(os.path.join(rundir, "app.log"), errors="replace") as fh:
            for ln in fh:
                m = re.search(r"yt-timing play id=([\w-]{11})\b", ln) or re.search(r"\byt ([\w-]{11}): SponsorBlock", ln)
                if m and m.group(1) not in ids:
                    ids.append(m.group(1))
    except OSError as err:
        sys.exit(f"no app.log in {rundir}: {err}")
    return ids


def clean_history(a):
    """--clean-history RUNDIR [--dry-run] --profile ACCOUNT: today's History entries of the videos
    that run played, removed from the account (listed first; --dry-run lists only). Run it the
    day of the run: entries are matched in History's "Today", and only those videos'."""
    from couchbox import appctl

    want = a.profile if ":" in a.profile else a.profile + ":"
    if a.profile in ("guest", "pick"):
        sys.exit("--clean-history needs --profile ACCOUNT (the account the run played as)")
    ids = played_in(a.clean_history)
    print(f"the run in {a.clean_history} played {len(ids)} videos: {' '.join(ids)}", flush=True)
    if not ids:
        return 0
    if not appctl.running("yt"):
        subprocess.run([*tv_env(), "systemd-run", "--user", "--quiet", "--collect", f"--unit={UNIT}-clean-{int(time.time())}",
                        "--setenv=COUCHBOX_MUTE=1", "--", APP, "--profile", want], check=True)
        for _ in range(60):
            if appctl.running("yt"):
                break
            time.sleep(1)
    look = appctl.call("yt", {"op": "call", "fn": "historyRemove", "args": {"ids": ids, "dryRun": True, "profile": want}}, timeout=60)
    for e in look["entries"]:
        print(f"  {'would remove' if e['removable'] else 'CAN NOT remove'} {e['id']} ({e['shelf']}): {e['title']}", flush=True)
    for vid in look["notToday"]:
        print(f"  not in today's History: {vid}", flush=True)
    if a.dry_run or not any(e["removable"] for e in look["entries"]):
        print("dry run: nothing removed" if a.dry_run else "nothing to remove", flush=True)
        return 0
    done = appctl.call("yt", {"op": "call", "fn": "historyRemove", "args": {"ids": ids, "dryRun": False, "profile": want}}, timeout=120)
    for e in done["entries"]:
        print(f"  {'removed' if e['removed'] else 'NOT removed'} {e['id']}: {e['title']}", flush=True)
    return 0 if all(e["removed"] for e in done["entries"] if e["removable"]) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="guest")
    ap.add_argument("--out", default="/tmp/yt-check")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--clean-history", metavar="RUNDIR", help="remove from the profile's History (today's entries) the videos a run played")
    ap.add_argument("--dry-run", action="store_true", help="with --clean-history: only list what would be removed")
    ap.add_argument("--perf", action="store_true", help="time the app instead (COUCHBOX_YT_TIMING): start, 3 videos, Search, Home's rows")
    a = ap.parse_args()
    if a.clean_history:
        sys.exit(clean_history(a))
    r = Run(a.out)
    # an account (its id, or account:page for a brand channel): the signed-in steps, read only
    want = "" if a.profile in ("guest", "pick") else a.profile if ":" in a.profile else a.profile + ":"

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
            "--setenv=COUCHBOX_YT_TIMING=1",  # yt-timing lines in app.log (and the focus report's timing)
            "--",
            APP,
            "--profile",
            (want or a.profile) if a.perf else "pick" if want else a.profile,
        ],
        check=True,
    )
    started = time.monotonic()
    for _ in range(600):  # (every 0.1 s: perf's Home ready counts from here)
        if "focus" in focus():
            break
        time.sleep(0.1)
    else:
        sys.exit("FAIL couchbox-yt didn't come up (no answer on its control socket)")

    if a.perf:
        perf(r, started, signed=want)
    elif want:
        account(r, want)
    else:
        guest(r)
        cast_checks(r)
    save_log(unit, a.out)
    if not a.keep:
        subprocess.run(["pkill", "-u", TV_USER, "-f", APP], check=False)
    print(f"{r.n - r.failed}/{r.n} passed; screenshots and focus in {a.out}" + (f", timings in {a.out}/perf.json" if a.perf else ""))
    sys.exit(1 if r.failed else 0)


if __name__ == "__main__":
    main()
