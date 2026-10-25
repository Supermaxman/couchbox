"""Voice tools for the native streaming apps (couchbox-streaming): Dropout, 2nd Try, Nebula,
Twitch. They work through the app's control socket (couchbox.appctl), so lists come from the
app's own signed-in session; the app starts if it isn't running."""

import re
import time

from couchbox import appctl

# tool name -> (site, app id in the registry)
SITES = {
    "dropout": ("dropout", "dropout"),
    "second_try": ("2ndtry", "2ndtry"),
    "nebula": ("nebula", "nebula"),
    "twitch": ("twitch", "twitch"),
}
SHOW_KINDS = ("series", "collection", "movie")


def site_of_app(app_id):
    return next((s for s, a in SITES.values() if a == app_id), None)


def ensure(site, start):
    """The app's socket, starting the app (start()) if needed."""
    if appctl.running(site):
        return
    start()
    for _ in range(40):
        time.sleep(0.5)
        if appctl.running(site):
            return
    raise RuntimeError("The app didn't start.")


def call(site, fn, **args):
    return appctl.call(site, {"op": "call", "fn": fn, "args": args}, timeout=40)


def mmss(s):
    s = int(s or 0)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def line(c):
    """One card as text: '<kind> <id> | title | details'."""
    kind = {"collection": "series", "movie": "series", "category": "category"}.get(c.get("kind"), c.get("kind") or "video")
    if c.get("live"):
        kind = "live"
    bits = []
    if c.get("series") and c["series"] != c.get("title"):
        bits.append(c["series"])
    if c.get("seasonNumber") or c.get("episode"):
        bits.append(f"S{c.get('seasonNumber') or '?'}E{c.get('episode') or '?'}")
    if c.get("live"):
        bits.append(f"live: {c.get('description') or ''} {c.get('viewers') or ''}".strip())
    elif c.get("completed"):
        bits.append("watched")
    elif c.get("progress"):
        bits.append(f"{int(c['progress'] * 100)}% watched")
    if c.get("duration"):
        bits.append(mmss(c["duration"]))
    return f"{kind} {c.get('id')} | {c.get('title', '')}" + (f" | {' · '.join(bits)}" if bits else "")


def lines(items, limit=15):
    items = list(items)[:limit]
    return "\n".join(line(c) for c in items) if items else "Nothing found."


def words(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def best_show(site, query):
    """The series that best matches the words of query."""
    found = [c for c in call(site, "search", q=query).get("items", []) if c.get("kind") in SHOW_KINDS]
    if not found:
        found = [c for c in call(site, "allSeries").get("items", []) if words(query) & words(c.get("title"))]
    found.sort(key=lambda c: -len(words(query) & words(c.get("title"))))
    return found[0] if found else None


def newest(site, show_id, n=3):
    """The show's newest episodes, newest first."""
    s = call(site, "collection", id=show_id)
    seasons = s.get("seasonList") or []
    if not seasons:
        return s, []
    seasons = sorted(seasons, key=lambda x: (x.get("number") or 0))
    pick = seasons[0] if str(seasons[0]["id"]).startswith(("channel|", "live|")) else seasons[-1]
    eps = call(site, "collectionItems", id=pick["id"]).get("items", [])
    if not str(pick["id"]).startswith("channel|"):  # seasons list oldest first
        eps = sorted(eps, key=lambda c: c.get("episode") or 0, reverse=True) if any(c.get("episode") for c in eps) else eps[::-1]
    return s, eps[:n]


def play(site, vid, raise_app):
    appctl.call(site, {"op": "open", "target": f"play:{vid}"})
    raise_app()
    return "Playing."


def run(tool, action, query=None, id=None, season=None, start=None, raise_app=None):
    site = SITES[tool][0]
    ensure(site, start)
    q = (query or "").strip()
    if tool == "twitch":
        return twitch(site, action, q, id, raise_app)
    if action == "continue":
        return lines(call(site, "watching").get("items", []))
    if action == "search":
        return lines(call(site, "search", q=q).get("items", []))
    if action == "shows":
        items = call(site, "allSeries").get("items", [])
        return lines([c for c in items if not q or words(q) & words(c.get("title"))], 40)
    if action == "mylist":
        return lines(call(site, "mylist").get("items", []))
    if action in ("latest", "episodes"):
        show = {"id": id} if id else best_show(site, q)
        if not show:
            return f"No show matching {q!r}."
        if action == "latest":
            s, eps = newest(site, show["id"])
            return f"{s.get('title')}, newest first:\n" + lines(eps)
        s = call(site, "collection", id=show["id"])
        seasons = s.get("seasonList") or []
        if not seasons:
            return f"{s.get('title')} has no episodes listed."
        pick = next((x for x in seasons if season and x.get("number") == int(season)), None) or seasons[-1]
        eps = call(site, "collectionItems", id=pick["id"]).get("items", [])
        other = ", ".join(x["name"] for x in seasons if x is not pick)
        return f"{s.get('title')} · {pick['name']}" + (f" (also: {other})" if other else "") + ":\n" + lines(eps, 40)
    if action == "resume":
        items = call(site, "watching").get("items", [])
        if q:
            items = [c for c in items if words(q) & (words(c.get("series")) | words(c.get("title")))]
        if not items:
            return "Nothing matching in Continue Watching."
        play(site, items[0]["id"], raise_app)
        return f"Playing {line(items[0]).split(' | ', 1)[1]}."
    if action == "play":
        if not id:
            return "play needs an id."
        return play(site, id, raise_app)
    if action == "open":
        appctl.call(site, {"op": "open", "target": f"series:{id}" if id else f"search:{q}" if q else "home"})
        raise_app()
        return "Opened."
    return f"Unknown action {action}."


def twitch(site, action, q, id, raise_app):
    if action == "live":
        items = call(site, "watching").get("items", [])
        return lines(items, 25) if items else "None of the channels you follow are live."
    if action == "search":
        return lines(call(site, "search", q=q).get("items", []))
    if action == "videos":
        login = id or q
        return lines(call(site, "collectionItems", id=f"ARCHIVE|{login}").get("items", []), 10)
    if action == "play":
        target = id or q
        if not target:
            return "play needs a channel or video id."
        if ":" not in target:  # a channel name: its live stream
            target = f"live:{target.lower().replace(' ', '')}"
        return play(site, target, raise_app)
    return f"Unknown action {action}."


def state_line(site, name):
    """What the app shows, for the screen note."""
    try:
        st = appctl.call(site, {"op": "state"}, timeout=3)
    except Exception:  # noqa: BLE001
        return f"{name} in front"
    page = st.get("page")
    if page == "player":
        what = " ".join(x for x in (st.get("series"), st.get("episode")) if x)
        what = f"{what} “{st.get('title')}”" if what else f"“{st.get('title')}”"
        if st.get("live"):
            return f"{name} in front, watching {what} live" + (" (paused)" if st.get("paused") else "")
        return f"{name} in front: {what} {'paused' if st.get('paused') else 'playing'} at {mmss(st.get('position'))} of {mmss(st.get('duration'))}"
    if page == "series":
        return f"{name} in front, on the page of {st.get('title') or 'a show'} (id {st.get('id')})"
    if page == "search":
        return f"{name} in front, searching “{st.get('query')}”"
    if page == "list":
        return f"{name} in front, on {st.get('title')}"
    if page == "sign-in":
        return f"{name} in front, asking to sign in"
    return f"{name} in front, on its {st.get('section') or 'home'} page"


def media(site, action, seconds=None):
    appctl.call(site, {"op": "media", "action": action, "seconds": seconds or 0}, timeout=5)
    time.sleep(0.4)
    st = appctl.call(site, {"op": "state"}, timeout=3)
    if st.get("page") != "player":
        return "Nothing is playing in the app."
    return f"“{st.get('title')}”: {'paused' if st.get('paused') else 'playing'} at {mmss(st.get('position'))} of {mmss(st.get('duration'))}"
