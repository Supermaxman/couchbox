#!/usr/bin/env python3
"""The YouTube app's key flows, on the box itself: the real remote path (couchbox-remote through
couchbox-input and the compositor), a screenshot after each step (couchbox-screenshot) and what
had the focus then (the app's control socket: {"op": "focus"}).

  sudo python3 ci/yt-box-check.py [--profile auto|guest|pick|ACCOUNT[:PAGE]] [--out /tmp/yt-check] [--keep] [--perf]
  sudo python3 ci/yt-box-check.py --clean-history RUNDIR [--profile ACCOUNT] [--ids ID,ID...] [--dry-run]

It starts couchbox-yt muted (COUCHBOX_MUTE=1, as the TV user, replacing one that's running) and
walks it with the remote. Each step prints PASS or FAIL with what it saw, and saves
OUT/NN-name.png and OUT/NN-name.json. --keep leaves the app running at the end.

Signed in by default (--profile auto: the TV's first account; YouTube bot-checks a TV that starts
many guest streams), read only: nothing liked, subscribed, saved or changed on the account, every
OK checked against what has the focus first. Who's watching (the account, its brand channels),
Home, Subscriptions, Library's History, Watch later and Playlists; a part-watched video from
History (it must start where YouTube says) with its channel and notification panels and comments;
a Home video's player walk (Description, the clock, paused seeks still showing a picture, scrubbing
hidden, the related row, Quality and speed, captions, comments, the channel's panel and page);
Shorts next and before; the tabs and a live stream; Settings' rows (Hide Shorts flipped and back:
this TV's own setting); Settings → Accounts. Today's History before the run goes into
OUT/history-before.json.

--profile guest: a guest's walk, light on YouTube: Home, Search typed and entered, one video (it
plays, or the player offers a sign-in), the pages that ask to sign in, the tabs, Settings' rows,
Who's watching; and casting's control socket, DIAL and SSDP.

--clean-history RUNDIR removes from the account's History the videos that run played (from
RUNDIR/app.log) that weren't in it before (RUNDIR/history-before.json), only among today's
entries, listing them first (--dry-run: only that). --ids ID,ID... takes exactly those instead
(RUNDIR is then just where it looks for nothing more), whether or not they were there before.

--perf times the app instead (as the profile given): start until Home shows, a video at once and
one after 5 s on its card (prefetched) from OK to its first picture, a resumed one, 10 more and the
memory after, two 1080p videos' processor use, Search, Home's rows, every back-end call's median
and worst; PERF lines, a SUMMARY against the targets, OUT/perf.json. Then --clean-history.

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


def press_button(name, check=None):
    """The player's control `name`, one key at a time, and OK only once it has the focus."""
    if not button_to(name):
        print(f"(couldn't reach the player's {name} button)", flush=True)
        return False
    return ok_on(lambda f: d(f).get("button") == name and not d(f).get("panel") and (check is None or check(f)), f"the {name} button")


def open_long_video(r):
    """A video from Home over 5 minutes (a short one ends mid-walk: Up next takes over), opened."""
    anchor("home")
    r.step("home-again", lambda f: (f["page"] == "home", "Home"), settle=2)
    long_video = lambda c: c.get("type") == "video" and not c.get("live") and c.get("duration", 0) > 300  # noqa: E731
    found = None
    for _ in range(4):  # along a row, then the next row down
        found = card_to(long_video, tries=7)
        if found:
            break
        remote("down")
    print(f"(the video: {found and found.get('duration')} s long)" if found else "(no video over 5 minutes on Home's first rows)", flush=True)
    if not found or not ok_on(lambda f: long_video(f.get("card") or {}), "a video over 5 minutes"):
        return False
    r.step(
        "player",
        lambda f: (f["page"] == "player" and "controls" in f["focus"] and d(f).get("button") == "play" and not d(f).get("message"),
                   f"mode {d(f).get('mode')}, on {d(f).get('button')} {d(f).get('message') or ''}"),
        settle=4,
    )
    return True


def player_walk(r):
    """The player, read only (nothing liked, subscribed, saved: every OK checked first): the
    description, the clock, paused seeks still showing a picture, scrubbing hidden, the related row,
    the settings menu's quality and speed, captions on and off, the comments, the channel's panel
    and page."""
    if press_button("description"):
        r.step("description", lambda f: ("description" in f["focus"] and f["shown"] and d(f).get("panel") == "description",
                                         f"panel {d(f).get('panel')!r}"), settle=3)
        remote("back")
        r.step("description-back", lambda f: (f["page"] == "player" and "controls" in f["focus"] and d(f).get("button") == "description",
                                              f"on {d(f).get('button')}, panel {d(f).get('panel')!r}"))
    # the clock moves
    p1 = d(focus()).get("position", 0)
    r.step("clock", lambda f: (d(f).get("position", 0) > p1, f"position {p1} -> {d(f).get('position')}"), settle=3)
    # paused seeks still show a picture (not black): back into the middle, back to 0:00, forward to
    # 30 s. Up: the bar, where Left / Right seek 10 s
    remote("playpause")
    f = r.step("paused", lambda f: (bool(d(f).get("paused")), f"paused at {d(f).get('position')}"), settle=1)
    picture(r, "paused-picture")
    at = d(f).get("position", 0)
    remote("up", *(["left"] if at >= 12 else []))
    r.step("paused-seek-mid", lambda f: (bool(d(f).get("paused")), f"position {at} -> {d(f).get('position')}"), settle=2.5)
    mid = picture(r, "paused-seek-mid-picture")
    for _ in range(12):  # back to 0:00 (a resumed video starts minutes in): Left, 4 at a time, until there
        g = d(focus())  # (where it's going: a scrub goes there on OK or a moment after the last press)
        if (g.get("scrub", -1) if g.get("scrub", -1) >= 0 else g.get("position", 99)) <= 1:
            break
        remote("left", "left", "left", "left", gap=0.3)
        time.sleep(0.8)
    r.step("paused-seek-0", lambda f: (d(f).get("position", 99) <= 1 and bool(d(f).get("paused")), f"position {d(f).get('position')}"), settle=2.5)
    picture(r, "paused-seek-0-picture", ref=mid)
    remote("right", "right", "right")
    r.step("paused-seek-30", lambda f: (bool(d(f).get("paused")), f"position {d(f).get('position')}"), settle=2.5)
    picture(r, "paused-seek-30-picture")
    remote("playpause", "down")
    time.sleep(6)  # the controls hide
    r.step("controls-hidden", lambda f: (d(f).get("mode") == "hidden", f"mode {d(f).get('mode')}"), settle=0)
    p0 = d(focus()).get("position", 0)
    remote("right")
    r.step("scrub", lambda f: (d(f).get("mode") == "bar" and "controls" in f["focus"], f"mode {d(f).get('mode')}, to {d(f).get('scrub')}"), settle=0.6)
    # Up while scrubbing: the chapters when the video has some, else back to the video, the scrub
    # undone (YouTube's: only OK, or a moment's pause, goes there). Right and Up together: a
    # scrub goes there by itself 2 s after the last press (the step above took longer)
    time.sleep(2.5)
    p0 = d(focus()).get("position", 0)
    remote("right", "up", gap=0.4)
    f = r.step("scrub-up", lambda f: (d(f).get("mode") == "chapters"
                                      or (d(f).get("mode") == "hidden" and d(f).get("scrub", -1) < 0 and abs(d(f).get("position", 0) - p0) < 8),
                                      f"mode {d(f).get('mode')}, position {p0} -> {d(f).get('position')}, scrub {d(f).get('scrub')}"), settle=1)
    if d(f).get("mode") == "chapters":
        remote("back")  # the chapters: back to the bar
    else:
        p1 = d(focus()).get("position", 0)
        remote("right", "back", gap=0.4)  # scrubbing again, Back: undone too
        r.step("scrub-back", lambda f: (d(f).get("mode") == "hidden" and d(f).get("scrub", -1) < 0 and abs(d(f).get("position", 0) - p1) < 8,
                                        f"mode {d(f).get('mode')}, position {p1} -> {d(f).get('position')}"), settle=1)
        remote("right")
    time.sleep(0.5)
    remote("down")
    f = r.step("scrub-down", lambda f: (d(f).get("mode") == "controls", f"mode {d(f).get('mode')}, on {d(f).get('button')}"), settle=0.6)
    last = d(f).get("button") or "play"
    remote("down")
    r.step("related", lambda f: (d(f).get("mode") == "related" and "related" in f["focus"], f"mode {d(f).get('mode')}"), settle=1)
    remote("up")
    r.step("related-up", lambda f: (d(f).get("mode") == "controls" and "controls" in f["focus"] and d(f).get("button") == last,
                                    f"mode {d(f).get('mode')}, on {d(f).get('button')}"), settle=1)
    # the settings menu: Quality, then Playback speed (and Back out of each): this TV's own choices
    if press_button("settings"):
        r.step("player-settings", lambda f: (d(f).get("panel") == "settings", f"panel {d(f).get('panel')!r}"), settle=1.5)
        if ok_on(lambda f: d(f).get("panel") == "settings" and d(f).get("panelItem", "").startswith("Quality"), "Quality"):
            r.step("player-quality", lambda f: (d(f).get("panel") == "quality", f"panel {d(f).get('panel')!r}"), settle=1.5)
            remote("back", "down")
            if ok_on(lambda f: d(f).get("panel") == "settings" and "speed" in d(f).get("panelItem", "").lower(), "Playback speed"):
                r.step("player-speed", lambda f: (d(f).get("panel") == "speed", f"panel {d(f).get('panel')!r}"), settle=1.5)
                remote("back")
        remote("back")
        r.step("player-settings-back", lambda f: (not d(f).get("panel") and "controls" in f["focus"], f"panel {d(f).get('panel')!r}"), settle=1.5)
    # captions: on by themselves (Settings → Captions, Always show captions: on), their words on
    # the screen within 10 s; CC turns them off (and they stay off for the video), CC on again
    def words(r_, name):
        end = time.monotonic() + 10
        while time.monotonic() < end and not d(focus()).get("subText"):
            time.sleep(0.5)
        r_.step(name, lambda f: (bool(d(f).get("subText")), f"on screen: {(d(f).get('subText') or '')[:40]!r}"), settle=0)

    f = r.step("captions-auto", lambda f: (True, f"captions {d(f).get('captions')!r} (none: the video has none, or the setting's off)"), settle=0)
    if d(f).get("captions"):
        words(r, "captions-text")
        if press_button("cc"):
            r.step("captions-off", lambda f: (not d(f).get("captions"), f"captions {d(f).get('captions')!r}"), settle=1.5)
            time.sleep(3)
            r.step("captions-stay-off", lambda f: (not d(f).get("captions"), f"captions {d(f).get('captions')!r}"), settle=0)
            if press_button("cc"):  # (the controls hid meanwhile: up again, to CC)
                r.step("captions-on", lambda f: (bool(d(f).get("captions")), f"captions {d(f).get('captions')!r}"), settle=2)
                if ok_on(lambda f: d(f).get("button") == "cc", "the captions button"):
                    r.step("captions-off-again", lambda f: (not d(f).get("captions"), f"captions {d(f).get('captions')!r}"), settle=1.5)
    elif press_button("cc"):
        f = r.step("captions-on", lambda f: (True, f"captions {d(f).get('captions')!r} (none: the video has no captions)"), settle=2)
        if d(f).get("captions"):
            words(r, "captions-text")
            if ok_on(lambda f: d(f).get("button") == "cc", "the captions button"):
                r.step("captions-off", lambda f: (not d(f).get("captions"), f"captions {d(f).get('captions')!r}"), settle=1.5)
    # the comments (read)
    if press_button("comments"):
        f = r.step("comments", lambda f: (d(f).get("panel") == "comments", f"panel {d(f).get('panel')!r}"), settle=3)
        # a comment's replies (read): down to the first with replies, OK, they load; Back: the
        # comments again, on the same one
        at = (d(f).get("comments") or {}).get("withReplies", -1)
        if 0 <= at <= 20:
            remote(*["down"] * at, gap=0.35)
            time.sleep(0.6)
            if ok_on(lambda f: (d(f).get("comments") or {}).get("at") == at, "a comment with replies"):
                end = time.monotonic() + 8
                while time.monotonic() < end and not (d(focus()).get("comments") or {}).get("replies"):
                    time.sleep(0.5)
                r.step("comment-replies", lambda f: ((d(f).get("comments") or {}).get("thread") and (d(f).get("comments") or {}).get("replies", 0) > 0,
                                                     f"replies {(d(f).get('comments') or {}).get('replies')}"), settle=0)
                remote("back")
                r.step("comment-replies-back", lambda f: (not (d(f).get("comments") or {}).get("thread") and (d(f).get("comments") or {}).get("at") == at,
                                                          f"comments again, on {(d(f).get('comments') or {}).get('at')} (was {at})"), settle=1)
        else:
            print(f"(no comment with replies among the first ones: {at})", flush=True)
        remote("back")
        if d(focus()).get("panel"):
            remote("back")
        r.step("comments-back", lambda f: (not d(f).get("panel"), f"panel {d(f).get('panel')!r}"), settle=1.5)
    # the channel's panel (its first row is Subscribe: not pressed), then Go to channel, its page, Back
    if press_button("channel"):
        r.step("channel-panel", lambda f: (d(f).get("panel") == "channel" and "panel" in f["focus"], f"panel {d(f).get('panel')!r}"), settle=2)
        remote("down")
        if ok_on(lambda f: d(f).get("panel") == "channel" and d(f).get("panelItem") == "Go to channel", "Go to channel"):
            r.step("channel-page", lambda f: (f.get("page") == "channel" and "channel" in f["focus"], f"page {f.get('page')}"), settle=4)
            remote("down")
            r.step("channel-page-down", lambda f: (f.get("page") == "channel", "the next shelf"), settle=1.5)
            remote("back")
            r.step("channel-back", lambda f: (f.get("page") == "player" and "controls" in f["focus"], f"page {f.get('page')}"), settle=2)
        elif d(focus()).get("panel"):
            remote("back")
    anchor("home")
    r.step("player-left", lambda f: (f["page"] == "home", f"page {f.get('page')}"), settle=2)


def shorts_walk(r):
    """The Shorts tab: straight into Shorts, the next and the one before (Up / Down only: the side's
    Subscribe and like aren't touched). Shorts send YouTube no playback reports here."""
    to_entry("shorts")
    f = r.step("shorts", lambda f: ("shorts" in f["focus"], f"focus {f.get('focus')}"), settle=5)
    first = d(f).get("videoId")
    remote("down")
    r.step("shorts-next", lambda f: (bool(d(f).get("videoId")) and d(f).get("videoId") != first, f"Short {d(f).get('index')}"), settle=4)
    remote("up")
    r.step("shorts-previous", lambda f: (d(f).get("videoId") == first, f"Short {d(f).get('index')}"), settle=3)
    remote("back")
    r.step("shorts-back", lambda f: ("guide" in f["focus"], "back on the guide"), settle=1.5)


def tabs_walk(r, live=True):
    """The tabs: Music, Gaming, Movies & TV (their shelves load), Live; and a live stream from its
    first row: live, behind live, forward again (live streams send no playback reports)."""
    for key, name in (("music", "tab-music"), ("gaming", "tab-gaming"), ("movies", "tab-movies"), ("live", "tab-live")):
        to_entry(key)
        r.step(name, lambda f, k=key: (f.get("section") == k and d(f).get("rows", 0) > 0, f"{d(f).get('rows')} rows {d(f).get('problem') or ''}"),
               settle=4)
    if not live:
        return
    live_card = card_to(lambda c: c.get("live"), tries=5)
    if not live_card or not ok_on(lambda f: (f.get("card") or {}).get("live"), "a live stream"):
        return skip(r, "live-player", "no live stream on the Live tab's first row")
    f = r.step("live-player", lambda f: (f["page"] == "player" and bool(d(f).get("live")), f"live {d(f).get('live')}, {d(f).get('videoId')}"), settle=10)
    if d(f).get("live"):
        if d(focus()).get("mode") != "hidden":
            remote("back")  # the controls hide: Left / Right seek (Back with them hidden leaves)
            time.sleep(1)
        remote("left")
        r.step("live-behind", lambda f: ("behind live" in (f.get("toast") or ""), f"toast {f.get('toast')!r}"), settle=1)
        remote("right", "right")
        r.step("live-forward", lambda f: (bool(f.get("toast")), f"toast {f.get('toast')!r}"), settle=1)
    anchor("home")


def settings_to(item, row=None):
    """In Settings: Down the list to `item` (by its id), then Right and Down its rows to `row`."""
    if d(focus()).get("area") == "rows":
        remote("left")
    for _ in range(14):
        if d(focus()).get("item") == item:
            break
        remote("down", gap=0.3)
    if row is None or d(focus()).get("item") != item:
        return
    remote("right")
    for _ in range(14):
        if d(focus()).get("row") == row:
            return
        remote("down", gap=0.3)


def settings_walk(r):
    """Settings (the guide folded to its rail once the focus is in the list); Extras' Hide Shorts
    flipped and flipped back (this TV's own setting, not the account's); About."""
    to_entry("settings")
    r.step("settings", lambda f: (f.get("section") == "settings" and "settings" in f["focus"] and not f.get("guideOpen"),
                                  f"guide open {f.get('guideOpen')}, on {d(f).get('item')}"), settle=2)
    settings_to("extras", "hide_shorts")  # by the focus report's ids (groups come and go: Link TV & phone)
    f = r.step("settings-row", lambda f: (d(f).get("row") == "hide_shorts", f"on row {d(f).get('row')}"), settle=1)
    was = d(f).get("on")
    if d(f).get("row") == "hide_shorts":
        remote("ok")
        r.step("settings-flip", lambda f: (d(f).get("on") == (not was), f"Hide Shorts {was} -> {d(f).get('on')}"), settle=1.5)
        remote("ok")
        r.step("settings-flip-back", lambda f: (d(f).get("on") == was, f"Hide Shorts back to {d(f).get('on')}"), settle=1.5)
    settings_to("about")
    r.step("settings-about", lambda f: (d(f).get("item") == "about", f"on {d(f).get('item')}"), settle=1)


def guest(r):
    """A guest's flows, light on YouTube (its bot check comes from many guest streams): Home, Search,
    one video, the pages that ask to sign in, Settings, Who's watching."""
    r.step("home", lambda f: (f["page"] == "home" and "home" in f["focus"] and f["shown"], "Home, a card in focus"), settle=6)
    remote("down")  # Home's second row (its cards large, the first row gone above)
    r.step("home-row2", lambda f: (f["page"] == "home" and "home" in f["focus"], "Home's second row"), settle=2)
    remote("up")

    # Search from the guide: the keys (not the last results); typing on a keyboard, then Enter
    remote("left", "up", "ok")
    r.step("search-open", lambda f: (f["page"] == "search" and "keys" in f["focus"] and not d(f).get("results"),
                                     f"keys page, {d(f).get('area')} {d(f).get('item')}"))
    remote("KEY_S", "KEY_K", "KEY_Y", gap=0.2)
    r.step("search-typed", lambda f: (d(f).get("query") == "sky", f"query {d(f).get('query')!r}"))
    remote("KEY_ENTER")
    r.step("search-enter", lambda f: (bool(d(f).get("results")) and d(f).get("query") == "sky", f"results for {d(f).get('query')!r}"), settle=4)
    remote("left", "ok")  # the guide (on Search), OK: Search again
    r.step("search-reopen", lambda f: ("keys" in f["focus"] and not d(f).get("results"), "Search again: the keys"))

    # the one guest video: it plays, or YouTube asks for a sign-in and the player offers one
    if open_long_video(r):
        f = focus()
        if d(f).get("signInOffer"):
            r.step("guest-sign-in-offer", lambda f: (bool(d(f).get("signInOffer")), f"the player says: {d(f).get('message')!r}"), settle=0)
            anchor("home")
        else:
            p1 = d(f).get("position", 0)
            r.step("guest-clock", lambda f: (d(f).get("position", 0) > p1, f"position {p1} -> {d(f).get('position')}"), settle=3)
            anchor("home")
    # a guest's Library (the tiles that need no account) and Subscriptions (the sign-in note)
    to_entry("library")
    r.step("library", lambda f: (f.get("section") == "library" and "tiles" in f["focus"], f"section {f.get('section')}"), settle=2)
    remote("down")
    r.step("library-signin", lambda f: ("action" in f["focus"], "the Sign in button"), settle=1)
    to_entry("subscriptions")
    r.step("subscriptions", lambda f: (f.get("section") == "subscriptions" and "message" in f["focus"], f"section {f.get('section')}"), settle=2)
    tabs_walk(r, live=False)
    settings_walk(r)
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
            end = time.monotonic() + 1.5  # the press lands a moment later (the page behind loads): wait for it
            while time.monotonic() < end and focus().get("guideAt") == at:
                time.sleep(0.15)
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
    """The signed-in walk, read only: account_core, then a Home video's player walk (descriptions,
    seeks, settings, captions, comments, its channel), Shorts, the tabs and a live stream, Settings'
    rows. Videos played: the History one (it was there already) and the Home one (--clean-history
    takes it out again: this run's History before it is in OUT/history-before.json)."""
    if not account_core(r, want):
        return
    if open_long_video(r):
        player_walk(r)
    shorts_walk(r)
    tabs_walk(r)
    settings_walk(r)
    search_walk(r, want)


def search_walk(r, want):
    """Search's keys, suggestions and results, as a guest (a signed-in search would go into the
    account's search history), then back to the account. No video is played."""
    anchor("as:guest")
    r.step("search-as-guest", lambda f: (not f.get("signedIn"), f"signed in {f.get('signedIn')}"), settle=3)
    to_entry("search")
    r.step("search-keys", lambda f: (f.get("page") == "search" and "keys" in f["focus"] and not d(f).get("results"),
                                     f"{d(f).get('area')} {d(f).get('item')}"), settle=1.5)
    remote("KEY_S", "KEY_K", "KEY_Y", gap=0.2)
    r.step("search-suggestions", lambda f: (d(f).get("query") == "sky" and d(f).get("suggestions", 0) > 0,
                                            f"query {d(f).get('query')!r}, {d(f).get('suggestions')} suggestions"), settle=2)
    remote("KEY_ENTER")
    r.step("search-results", lambda f: (bool(d(f).get("results")) and d(f).get("query") == "sky", f"results for {d(f).get('query')!r}"), settle=4)
    remote("down")
    r.step("search-results-down", lambda f: (bool(d(f).get("results")), f"results, {f.get('item')}"), settle=2)
    anchor(f"as:{want}")
    r.step("search-back-to-account", lambda f: (f.get("signedIn") and f.get("profile") == want, f"profile {f.get('profile')}"), settle=4)


def menu_test(r, want):
    """The card menu's one write, undone: a Home video saved through the hold-OK menu's "Save to
    Watch later", checked, then taken out through Save to playlist's Watch later and checked. A
    video already in Watch later is left alone. Only with the owner's OK (--menu-test). Before:
    the menu's entries as YouTube sends them (menuProbe: words, icons, endpoint names)."""
    from couchbox import appctl

    def in_wl(vid):
        r_ = appctl.call("yt", {"op": "call", "fn": "saveOptions", "args": {"id": vid}}, timeout=30)
        return next((bool(p.get("saved")) for p in r_.get("playlists") or [] if p.get("id") == "WL"), None)

    f = r.step("menu-home", lambda f: (f.get("page") == "home" and f.get("signedIn") and (f.get("card") or {}).get("type") == "video",
                                       f"signed in {f.get('signedIn')}, on {(f.get('card') or {}).get('id')}"), settle=6)
    vid = (f.get("card") or {}).get("id", "")
    if not vid or not f.get("signedIn"):
        print("ABORT: no video in focus on Home, signed in; nothing saved", flush=True)
        return
    if in_wl(vid):
        print(f"(menu test: {vid} is in Watch later already: left alone, nothing tested)", flush=True)
        return
    try:
        probe = appctl.call("yt", {"op": "call", "fn": "menuProbe", "args": {}}, timeout=30)
        with open(os.path.join(r.out, "menu-probe.json"), "w") as fh:
            json.dump(probe, fh, indent=1)
        print(f"(a Home card's menu: {[e.get('label') for e in probe.get('entries') or []]}; in menu-probe.json)", flush=True)
    except Exception as err:  # noqa: BLE001
        print(f"(menuProbe: {err})", flush=True)

    def to_row(key):
        for _ in range(12):
            if d(focus()).get("at") == key:
                return True
            remote("down", gap=0.3)
        return d(focus()).get("at") == key

    remote("ok@1.2")  # hold OK: the card's menu
    r.step("menu-open", lambda f: ("later" in d(f).get("keys", []), f"menu {d(f).get('keys')}"), settle=1)
    to_row("later")
    remote("ok")  # Save to Watch later
    time.sleep(3)
    saved = in_wl(vid)
    r.step("menu-saved", lambda f: (saved is True, f"{vid} in Watch later: {saved}; notice {f.get('toast')!r}"), settle=0)
    remote("ok@1.2")  # the menu again: Save to playlist, Watch later (ticked): out of it
    to_row("playlist")
    remote("ok")
    r.step("menu-playlists", lambda f: (d(f).get("mode") == "playlists", f"mode {d(f).get('mode')}, on {d(f).get('at')}"), settle=2)
    remote("ok")  # the first: Watch later
    time.sleep(3)
    gone = in_wl(vid)
    r.step("menu-unsaved", lambda f: (gone is False, f"{vid} in Watch later: {gone}"), settle=0)
    if gone is not False:
        print(f"WARNING: {vid} may still be in Watch later: take it out by hand", flush=True)
    remote("back", "back")


def history_before(r):
    """Today's History before the run plays anything (for --clean-history: not to take those out)."""
    from couchbox import appctl

    try:
        ids = appctl.call("yt", {"op": "call", "fn": "historyToday", "args": {}}, timeout=60).get("ids") or []
    except Exception as err:  # noqa: BLE001
        print(f"(History before the run: {err})", flush=True)
        return
    with open(os.path.join(r.out, "history-before.json"), "w") as fh:
        json.dump(ids, fh)
    print(f"(History today before the run: {len(ids)} videos, kept in history-before.json)", flush=True)


def account_core(r, want):
    """Who's watching (the account, its brand channels), Home, Subscriptions, Library's lists, a video
    from History resuming where YouTube says, the channel and notification panels, Settings → Accounts."""
    f = r.step("profiles", lambda f: (f.get("page") == "profiles" and d(f).get("count", 0) >= 1,
                                      f"{d(f).get('count')} profiles, {d(f).get('brands')} brand channels"), settle=4)
    # it opens on the profile last watched as (first in the row), never on Add account
    r.step("profiles-last-first", lambda f: (d(f).get("index") == 0 and d(f).get("id") not in ("", "add"),
                                             f"on {d(f).get('id')} (index {d(f).get('index')}) of {d(f).get('ids')}"), settle=0)
    ids = d(f).get("ids") or []
    if want not in ids:
        print(f"ABORT: {want} isn't among Who's watching's profiles {ids}; pressing nothing", flush=True)
        return False

    def settled(check, wait=3.0):  # the remote's presses reach the app a moment later: wait for them
        end = time.monotonic() + wait
        while time.monotonic() < end:
            if check(focus()):
                return True
            time.sleep(0.25)
        return check(focus())

    remote(*["left"] * (len(ids) + 1), gap=0.3)  # to the first, then right to the one wanted (by its place)
    settled(lambda g: d(g).get("index") == 0)
    remote(*["right"] * ids.index(want), gap=0.4)
    settled(lambda g: d(g).get("id") == want)
    r.step("profiles-account", lambda f: (d(f).get("id") == want and d(f).get("area") == "row",
                                          f"on {d(f).get('id')}, the account at {ids.index(want)} of {len(ids)}"), settle=0.5)
    if not settled(lambda g: d(g).get("id") == want and d(g).get("area") == "row", 1.0) or not ok_on(
        lambda f: d(f).get("id") == want and d(f).get("area") == "row", "the account"
    ):
        print("ABORT: the account isn't on Who's watching; pressing nothing more", flush=True)
        return False
    r.step("home-signed-in", lambda f: (f.get("page") == "home" and f.get("signedIn") and f.get("profile") == want and d(f).get("rows", 0) > 0,
                                        f"signed in {f.get('signedIn')}, {d(f).get('rows')} rows {d(f).get('problem') or ''}"), settle=6)
    if not focus().get("signedIn"):
        print("ABORT: not signed in as the account; pressing nothing more", flush=True)
        return False
    history_before(r)
    remote("down")  # Home's second row (the first row's cards large, then gone above), and back up
    r.step("home-row2-signed-in", lambda f: (f.get("page") == "home" and d(f).get("row") == 1, f"row {d(f).get('row')}"), settle=2)
    remote("up")
    time.sleep(1)

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
        settings_accounts(r)
        return True
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
        settings_accounts(r)
        return True
    time.sleep(4)
    part = lambda c: c.get("type") == "video" and 0.03 < (c.get("progress") or 0) < 0.9  # noqa: E731
    c = card_to(part, tries=6) or card_to(part, keys=("down",), tries=3)
    if not c:
        skip(r, "history-video", "no part-watched video among History's first cards: resume not checked, nothing played")
        remote("back")
        settings_accounts(r)
        return True
    if not ok_on(lambda f: part(f.get("card") or {}), "a part-watched video"):
        settings_accounts(r)
        return True
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
    return True


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
    return "worker" if "ytworker" in cmd else "node" if "--permission" in cmd else "qjs" if "qjs" in cmd else "app"


def all_pids():
    """The app, its stream worker and the worker's node."""
    out = subprocess.run(["pgrep", "-u", TV_USER, "-f", f"{APP}|couchbox.services.ytworker|--permission -e|qjs --std"],
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
            + "; solver " + (
                f"{(m.get('solver') or {}).get('runtime')} ({'sandboxed' if (m.get('solver') or {}).get('sandboxed') else 'NOT sandboxed'}): "
                f"{(m.get('solver') or {}).get('solves')} solves, {(m.get('solver') or {}).get('readings')} player readings, "
                f"{(m.get('solver') or {}).get('starts')} starts, {(m.get('solver') or {}).get('rss')} MB now"
                if m.get("solver") and m["solver"].get("runtime") else "not used yet")
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
    if signed:  # (after Home's measured: it asks YouTube for the History)
        history_before(r)
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

    def cpu_sample(p, name, seconds=30, want=""):
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
        if want and (d(f).get("videoId") != want or not d(f).get("itags")):  # (mpv would still be playing the one before)
            p.say(name, f"{want} didn't play: the player shows {d(f).get('videoId')!r}, itags {d(f).get('itags')!r}, "
                  f"{d(f).get('message') or 'no message'}", None)
            return
        each = {}
        for x in pids:
            each[name_of(x)] = each.get(name_of(x), 0) + round(100 * (c1[x] - c0[x]) / seconds)
        total = sum(each.values())
        dec = d(f).get("decoded") or ""  # what mpv decodes: "1920x1080@24 h264"
        try:
            w, rest = dec.split("x", 1)
            hgt, fps = rest.split("@", 1)
            res, tall = f"{min(int(w), int(hgt))}p{fps.split()[0]} {fps.split()[1] if ' ' in fps else ''}".strip(), min(int(w), int(hgt))
        except ValueError:
            res, tall = f"{d(f).get('height')}p{d(f).get('fps')} (as the stream said)", d(f).get("height") or 0
        res += f", itags {d(f).get('itags')}"
        p.say(name, f"{total}% of one core over {seconds} s of {d(f).get('videoId')} ({res}"
              + ("" if tall >= 1080 else ": not 1080p, not comparable")
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

    # (signed in, as the rest: YouTube bot-checks a TV that starts many guest streams; the check's own
    # videos come out of the account's History with --clean-history after)
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
            cpu_sample(p, name, want=vid)
        anchor("home")

    p.phase("known-1080p", known_1080p)



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


def first_account():
    """The first account signed in on the TV (its id), or ""."""
    home = pwd.getpwnam(TV_USER).pw_dir
    d = os.path.join(home, ".local/share/couchbox-yt/accounts")
    try:
        return sorted(f.removesuffix(".json") for f in os.listdir(d) if f.endswith(".json"))[0]
    except (OSError, IndexError):
        return ""


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
    if a.ids:  # given: exactly these (the earlier runs' plays the owner OK'd), today's entries only
        ids, before = [v.strip() for v in a.ids.split(",") if v.strip()], set()
        print(f"{len(ids)} videos given: {' '.join(ids)}", flush=True)
    else:
        ids = played_in(a.clean_history)
        print(f"the run in {a.clean_history} played {len(ids)} videos: {' '.join(ids)}", flush=True)
        try:  # already in today's History before the run (the household's): left alone
            with open(os.path.join(a.clean_history, "history-before.json")) as fh:
                before = set(json.load(fh))
        except (OSError, ValueError):
            before = set()
    kept = [v for v in ids if v in before]
    ids = [v for v in ids if v not in before]
    for vid in kept:
        print(f"  left alone (in History before the run): {vid}", flush=True)
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
    ap.add_argument("--profile", default="auto", help="auto (the default): the first account on the TV, else a guest")
    ap.add_argument("--out", default="/tmp/yt-check")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--clean-history", metavar="RUNDIR", help="remove from the profile's History (today's entries) the videos a run played")
    ap.add_argument("--dry-run", action="store_true", help="with --clean-history: only list what would be removed")
    ap.add_argument("--ids", help="with --clean-history: these videos (comma-separated) instead of the run's, History before it or not")
    ap.add_argument("--menu-test", action="store_true", help="signed in: save a Home video to Watch later through the card menu, then remove it (a write: only with the owner's OK)")
    ap.add_argument("--perf", action="store_true", help="time the app instead (COUCHBOX_YT_TIMING): start, 3 videos, Search, Home's rows")
    a = ap.parse_args()
    if a.profile == "auto":  # signed in when there's an account: YouTube bot-checks a TV's many guest streams
        a.profile = first_account() or "guest"
        print(f"(profile: {a.profile})", flush=True)
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
            (want or a.profile) if a.perf or a.menu_test else "pick" if want else a.profile,
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

    if a.menu_test:
        if want:
            menu_test(r, want)
        else:
            print("ABORT: --menu-test needs an account (--profile)", flush=True)
    elif a.perf:
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
