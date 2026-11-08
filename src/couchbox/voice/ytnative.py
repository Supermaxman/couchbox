"""YouTube in Couchbox's own app (couchbox-yt: the YouTube tile, unless Settings → Apps → YouTube
app says VacuumTube), for the voice tools, links sent to the TV and Continue watching. All of it
goes through the app's control socket (couchbox.appctl, site "yt"): lists come from the app's own
sign-in (the profile watching), what's asked for opens on screen, and the app is started on it
when it isn't running (in a unit named like the home screen's, so couchbox-memory treats it as
any app).

Lists are lines of '<kind> <id> | title | channel · views · age · length', as the VacuumTube
tools gave them: kind is video, channel, playlist or page; open takes the id of the last three.
"""

import os
import re
import subprocess
import time
import uuid

from couchbox import appctl

SITE = "yt"
EXE = "/usr/lib/couchbox/bin/couchbox-yt"
DESKTOP = "couchbox-yt.desktop"
TV_USER = "tv"
NOT_SIGNED_IN = "YouTube isn't signed in on this TV: pick or add an account on its Who's watching screen."


# ------------------------------------------------------------------ the app
def running():
    return appctl.running(SITE)


def state():
    """What the app shows ({} when it isn't running): page, section, showing, title, query,
    profile, paused, position, duration, live."""
    try:
        return appctl.call(SITE, {"op": "state"}, timeout=3)
    except Exception:  # noqa: BLE001
        return {}


def call(fn, **args):
    """One of the app's own back-end calls (its sign-in): home, search, browse, channel..."""
    return appctl.call(SITE, {"op": "call", "fn": fn, "args": args}, timeout=40)


def launch_command(target="", unit=""):
    """Start the app (on target), as the TV user: in its own unit, as the home screen does."""
    unit = unit or f"app-couchbox-yt@{uuid.uuid4().hex[:8]}.service"
    cmd = ["systemd-run", "--user", "--quiet", "--collect", f"--unit={unit}", "--", EXE]
    if os.geteuid() == 0:
        cmd[2:2] = ["-M", f"{TV_USER}@"]
    return cmd + (["--open", target] if target else [])


def launch(target=""):
    try:
        subprocess.run(launch_command(target), check=True, capture_output=True, timeout=10)
    except (OSError, subprocess.SubprocessError):  # no user manager (a bare session)
        subprocess.Popen(
            [EXE] + (["--open", target] if target else []), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


def show(target, raise_app=None, wait=25):
    """Open target in the app (video:ID[@SECONDS], search:TEXT, channel:ID, playlist:ID, history,
    home, subscriptions...), starting the app on it if it isn't running, and wait until the app
    is past its start. False if it didn't come up."""
    if running():
        appctl.call(SITE, {"op": "open", "target": target}, timeout=10)
    else:
        launch(target)
        end = time.time() + wait
        while state().get("page") in (None, "starting"):
            if time.time() > end:
                return False
            time.sleep(0.5)
    if raise_app:
        raise_app()
    return True


def target_of(browse_id):
    """What open shows for an id from a list: a channel, a playlist, or another page."""
    if browse_id.startswith("UC"):
        return f"channel:{browse_id}"
    if browse_id.startswith("VL") or re.match(r"(PL|OL|UU|LL|RD|FL)[\w-]{8,}$", browse_id):
        return f"playlist:{browse_id}"
    return f"browse:{browse_id}"


# ------------------------------------------------------------------ lists as text
def line(it):
    kind = {"short": "video", "live": "video", "game": "channel", "browse": "page"}.get(it.get("type"), it.get("type") or "video")
    bits = [x for x in it.get("lines") or [] if x]
    if it.get("live"):
        bits.append("LIVE")
    elif it.get("duration"):
        bits.append(it["duration"])
    if it.get("type") == "short":
        bits.append("Short")
    if it.get("progress"):
        bits.append(f"watched {round(it['progress'] * 100)}%")
    return f"{kind} {it.get('id')} | {it.get('title', '')}" + (f" | {' · '.join(bits)}" if bits else "")


def items(page, limit=15):
    """A page's cards, shelf by shelf, each once."""
    out, seen = [], set()
    for shelf in (page or {}).get("shelves") or []:
        for it in shelf.get("items") or []:
            if it.get("id") and it["id"] not in seen:
                seen.add(it["id"])
                out.append(it)
    return out[:limit]


def lines(page, limit=15):
    found = items(page, limit)
    return "\n".join(line(it) for it in found) if found else "Nothing listed."


def norm(s):
    return re.sub(r"[\W_]+", "", (s or "").lower())


def age(it):
    """Seconds since upload from a card's 'n units ago' (unknown: very old)."""
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s+ago", " ".join(it.get("lines") or []))
    if not m:
        return 10**10
    unit = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000, "year": 31536000}
    return int(m.group(1)) * unit[m.group(2)]


def mmss(s):
    s = int(s or 0)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def state_line(st=None, name="YouTube"):
    """What the app shows, for the screen note."""
    st = state() if st is None else st
    page = st.get("page")
    if not page:
        return f"{name} in front"
    if page == "player":
        what = f"“{st.get('title') or 'a video'}”"
        if st.get("live"):
            return f"{name} in front, watching {what} live" + (" (paused)" if st.get("paused") else "")
        return f"{name} in front: {what} {'paused' if st.get('paused') else 'playing'} at {mmss(st.get('position'))} of {mmss(st.get('duration'))}"
    if page == "profiles":
        return f"{name} in front, asking who's watching"
    if page == "search" and st.get("query"):
        return f"{name} in front, searching “{st['query']}”"
    if page in ("channel", "list"):
        return f"{name} in front, on {st.get('showing') or 'a page'}" + (f" (id {st['id']})" if st.get("id") else "")
    return f"{name} in front, on its {st.get('section') or page} page"


# ------------------------------------------------------------------ the voice tool
def signed_in():
    return state().get("profile", "guest") != "guest"


def subscribed(query=""):
    """The subscribed channels (the Subscriptions page's side list), those matching query first."""
    chans = [c for c in call("subscriptions").get("channels") or [] if c.get("id", "").startswith("UC")]
    q = norm(query)
    if not q:
        return chans
    exact = [c for c in chans if norm(c["title"]) == q]
    return exact or [c for c in chans if q in norm(c["title"]) or (len(norm(c["title"])) >= 5 and norm(c["title"]) in q)]


def latest(query, raise_app):
    """New videos from one or more channels (comma-separated): each subscribed channel's own feed,
    newest first; the channel that posted most recently is put on screen."""
    names = [n.strip() for n in (query or "").split(",") if n.strip()]
    if not names:
        return "latest needs a channel name."
    feeds, missing = [], []
    for n in names:
        ch = next(iter(subscribed(n)), None)
        if not ch:
            missing.append(n)
            continue
        vids = [it for it in items(call("browse", id=ch["id"], params=ch.get("params", "")), 8) if it.get("type") in ("video", "live")]
        feeds.append((ch, vids, min([age(v) for v in vids] or [10**10])))
    out = []
    if feeds:
        feeds.sort(key=lambda f: f[2])
        show(f"channel:{feeds[0][0]['id']}", raise_app)
        for ch, vids, _ in feeds:
            out.append(f"{ch['title']} (newest first):\n" + ("\n".join(line(v) for v in vids[:6]) or "no videos listed"))
        out[0] += "\n(its channel is on screen now)"
    for n in missing:
        out.append(f"{n}: not a subscribed channel; youtube search for it and open its channel id.")
    return "\n\n".join(out)


def resume(query, raise_app):
    """Continue the most recent video in the history whose title or channel matches query (any
    video without one); an unfinished one first. The app starts it where it was left."""
    q = norm(query)
    vids = [it for it in items(call("browse", id="FEhistory"), 60) if it.get("type") in ("video", "live")]
    vids = [it for it in vids if not q or q in norm(it.get("title")) or q in norm(" ".join(it.get("lines") or []))]
    if not vids:
        return f"Nothing{' from ' + query if query else ''} in the recent YouTube history."
    it = next((v for v in vids if (v.get("progress") or 0) < 0.95), vids[0])
    show(f"video:{it['id']}", raise_app)
    channel = (it.get("lines") or [""])[0]
    return f"Playing {it['title']}" + (f" ({channel})." if channel else ".")


def browse_id(item_id):
    """The browse id of what open shows: a playlist's is VL + its id."""
    kind, _, rest = target_of(item_id).partition(":")
    return ("VL" + rest).replace("VLVL", "VL", 1) if kind == "playlist" else rest


ACCOUNT = ("history", "subscriptions", "channels", "resume", "latest")


def run(action, query=None, id=None, raise_app=None):
    q = (query or "").strip()
    if action == "search" and not q or action in ("open", "play") and not id:
        return f"{action} needs {'query' if action == 'search' else 'id'}."
    if action == "play":
        return f"Playing video {id}." if show(f"video:{id}", raise_app) else "YouTube didn't start."
    if action == "list":
        if not running():
            return "YouTube isn't running."
        st = appctl.call(SITE, {"op": "screen"}, timeout=5)
        head = state_line(st) + "."
        if st.get("page") in ("player", "profiles"):
            return head
        return head + "\n" + lines((st.get("shown") or {}).get("page") or {})
    screens = {
        "search": f"search:{q}",
        "history": "history",
        "subscriptions": "subscriptions",
        "channels": "subscriptions",
        "home": "home",
        "open": target_of(id or ""),
        "resume": "",
        "latest": "",
    }
    if action not in screens:
        return f"Unknown action {action}."
    target = screens[action] or ("" if running() else "home")  # resume, latest: they show their own pick
    if target and not show(target, raise_app):
        return "YouTube didn't start."
    if action in ACCOUNT and not signed_in():
        return NOT_SIGNED_IN
    if action == "resume":
        return resume(q, raise_app)
    if action == "latest":
        return latest(q, raise_app)
    if action == "channels":
        chans = subscribed(q)
        listing = lambda cs: "\n".join(f"channel {c['id']} | {c['title']}" for c in cs)
        if q and not chans:
            return "No subscribed channel matches; all of them:\n" + listing(subscribed())
        return listing(chans) or "No subscriptions."
    page = {
        "search": lambda: call("search", q=q),
        "history": lambda: call("browse", id="FEhistory"),
        "subscriptions": lambda: call("subscriptions").get("page") or {},
        "home": lambda: call("home"),
        "open": lambda: call("channel", id=browse_id(id)),
    }[action]()
    return lines(page)
