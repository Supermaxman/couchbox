"""The voice agent's tools: what it can do on the TV.

Apps are driven as text, not screenshots: YouTube through its own command router and
data model, Jellyfin through the web app's API client, other web apps through a numbered
list of the page's buttons and links. All of it over DevTools (cdp.py). Remote keys are
the fallback."""

import json
import os
import pwd
import re
import subprocess
import tempfile
import time

from evdev import UInput
from evdev import ecodes as e

from couchbox import appctl, secrets, settings
from couchbox import apps as registry
from couchbox.services import weather

from . import cdp, streaming

TV_USER = "tv"
APP_DIRS = [
    "~/.local/share/applications",
    "/var/lib/flatpak/exports/share/applications",
    "/usr/local/share/applications",
    "/usr/share/applications",
]


# ------------------------------------------------------------------ apps and windows


def tv_env():
    pw = pwd.getpwnam(TV_USER)
    return pw, {
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{pw.pw_uid}/bus",
        "XDG_RUNTIME_DIR": f"/run/user/{pw.pw_uid}",
        "PATH": "/usr/bin:/bin",
    }


def home_apps():
    """[(desktop id, name)] of the apps on the home row, in order (without Settings). Hidden
    apps are left out: the assistant doesn't offer what the household turned off."""
    return [(a.desktop, a.name) for a in registry.home_row(settings.load()) if a.hideable]


def visible_ids(st=None):
    return {a.id for a in registry.home_row(st or settings.load()) if a.hideable}


# ------------------------------------------------------------------ the app in front (KWin)
def active_window():
    """The window in front: {"class", "app", "caption", "shell"} (couchbox-active-window)."""
    pw, env = tv_env()
    try:
        r = subprocess.run(
            ["runuser", "-u", TV_USER, "--", "env"]
            + [f"{k}={v}" for k, v in env.items()]
            + ["/usr/lib/couchbox/bin/couchbox-active-window"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


def app_of_window(w, st=None):
    """The registry app a window belongs to, "home" for the home screen, or None."""
    if not w or w.get("shell") or (w.get("class") or "").lower() in ("plasmashell", "org.kde.plasmashell"):
        return "home"
    have = {(w.get("class") or "").lower(), (w.get("app") or "").lower().removesuffix(".desktop")}
    st = st or settings.load()
    for a in registry.all_apps(st):
        if have & {c.lower() for c in window_classes(a.desktop, a.name)}:
            return a
    return None


def web_urls():
    """{app name: url} of the Chromium web apps."""
    s = settings.load()
    return {a.name.lower(): a.url for a in registry.all_apps(s) if a.kind == "web" and a.url}


def desktop_file(app_id):
    home = pwd.getpwnam(TV_USER).pw_dir
    for d in APP_DIRS:
        p = os.path.join(d.replace("~", home), app_id)
        if os.path.isfile(p):
            return p
    return None


def app_exec(path):
    m = re.search(r"^Exec=(.*)$", open(path).read(), re.M)
    return re.sub(r"\s%[a-zA-Z]", "", m.group(1)) if m else None


def app_url(name):
    return web_urls().get(name.lower())


def kwin_script(js):
    """Run a KWin script in the TV session (raise windows etc.)."""
    pw, env = tv_env()
    fd, path = tempfile.mkstemp(suffix=".js", dir="/run/couchbox/voice")
    with os.fdopen(fd, "w") as f:
        f.write(js)
    os.chmod(path, 0o644)
    gd = (
        ["runuser", "-u", TV_USER, "--", "env"]
        + [f"{k}={v}" for k, v in env.items()]
        + ["gdbus", "call", "--session", "--dest", "org.kde.KWin"]
    )
    name = os.path.basename(path)
    try:
        out = subprocess.run(
            gd + ["--object-path", "/Scripting", "--method", "org.kde.kwin.Scripting.loadScript", path, name],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        sid = re.search(r"(\d+)", out)
        if sid:
            subprocess.run(
                gd + ["--object-path", f"/Scripting/Script{sid.group(1)}", "--method", "org.kde.kwin.Script.run"],
                capture_output=True,
                timeout=5,
            )
            time.sleep(0.3)
        subprocess.run(
            gd + ["--object-path", "/Scripting", "--method", "org.kde.kwin.Scripting.unloadScript", name], capture_output=True, timeout=5
        )
    finally:
        os.unlink(path)


def window_classes(app_id, name):
    """Window classes the app's window may have (KWin resourceClass or desktop file name)."""
    out = [app_id.removesuffix(".desktop")]
    url = app_url(name)
    if url:
        out.append("chrome-" + re.sub(r"^https?://", "", url).split("/")[0] + "__-Default")
    if name.lower() == "jellyfin":
        out += ["jellyfin-desktop", "org.jellyfin.JellyfinDesktop", "org.jellyfin.jellyfin-desktop"]
    return out


def raise_window(app_id, name):
    want = json.dumps(window_classes(app_id, name))
    kwin_script(
        f"const want = {want};\n"
        "for (const w of workspace.windowList()) if (w.normalWindow && (want.includes(w.resourceClass)"
        " || want.includes(w.desktopFileName))) { w.minimized = false; w.fullScreen = true; workspace.activeWindow = w; break; }"
    )


def app_page(name):
    """The DevTools page of a running app, or None."""
    if name.lower() == "youtube":
        p = cdp.pages(cdp.YOUTUBE_PORT)
        return p[0] if p else None
    if name.lower() == "jellyfin":
        p = [p for p in cdp.pages(cdp.JELLYFIN_PORT) if "/web/" in p["url"] or "jellyfin" in p["url"].lower()]
        if p:
            return p[0]
    url = app_url(name)
    host = re.sub(r"^https?://", "", url or "").split("/")[0]
    return next((p for p in cdp.pages(cdp.WEB_PORT) if host and host in p["url"]), None)


def open_app(name, wait=True):
    apps = {n.lower(): (i, n) for i, n in home_apps()}
    if name.lower() == "home":
        return press(["home"])
    if name.lower() not in apps:
        return f"No app called {name}. Apps: {', '.join(n for _, n in home_apps())}."
    app_id, name = apps[name.lower()]
    if app_page(name):
        raise_window(app_id, name)
        return f"{name} is in front."
    path = desktop_file(app_id)
    cmd = path and app_exec(path)
    if not cmd:
        return f"Can't find how to start {name}."
    subprocess.run(["systemd-run", "--user", "-M", f"{TV_USER}@", "--quiet", "--collect", "sh", "-c", cmd], capture_output=True, timeout=10)
    if name.lower() not in ("youtube", "jellyfin") and not app_url(name):
        return f"Opened {name}."  # no DevTools (our Qt apps): its launcher brings it up
    if wait:
        for _ in range(40):
            time.sleep(0.5)
            if app_page(name):
                time.sleep(1.5)
                raise_window(app_id, name)  # full screen and in front, as from the home screen
                return f"Opened {name}."
        return f"Started {name}, but it isn't answering yet."
    return f"Opened {name}."


def foreground(focused=False):
    """(app name, page) of the app in front, judged by which page has focus. With focused, only a
    page that has focus: a merely visible one may be behind another app."""
    names = {"youtube": "YouTube"}
    for name in [n for _, n in home_apps()]:
        names[name.lower()] = name
    best = None
    for port in (cdp.YOUTUBE_PORT, cdp.JELLYFIN_PORT, cdp.WEB_PORT):
        for p in cdp.pages(port):
            try:
                st = cdp.evaluate(p, "[document.hasFocus(), document.visibilityState]", timeout=3)
            except Exception:
                continue
            name = (
                "YouTube"
                if port == cdp.YOUTUBE_PORT
                else "Jellyfin"
                if port == cdp.JELLYFIN_PORT
                else next(
                    (n for n in names.values() if app_url(n) and re.sub(r"^https?://", "", app_url(n)).split("/")[0] in p["url"]),
                    p.get("title", "web page"),
                )
            )
            if st and st[0]:
                return name, p
            if st and st[1] == "visible" and not best and not focused:
                best = (name, p)
    return best or (None, None)


# ------------------------------------------------------------------ typing into the app in front
# Phone typing (couchbox-phone) and voice dictation (couchbox-voice) go here when a text box or a search
# screen is open: YouTube's search screen (a search runs), else the focused text box, else the
# box on another app's search screen (Jellyfin's).

TYPING_JS = r"""() => {
  const editable = el => !!el && (el.isContentEditable || el.tagName === "TEXTAREA" ||
      el.tagName === "INPUT" && /^(text|search|email|url|tel|password|)$/i.test(el.getAttribute("type") || ""));
  return {box: editable(document.activeElement), search: /^#!?\/search/.test(location.hash), yt: !!window._yttv};
}"""

ENTER_TEXT_JS = r"""() => {
  const editable = el => !!el && (el.isContentEditable || el.tagName === "TEXTAREA" ||
      el.tagName === "INPUT" && /^(text|search|email|url|tel|password|)$/i.test(el.getAttribute("type") || ""));
  let el = document.activeElement;
  if (!editable(el))
    el = [...document.querySelectorAll("input[type=search], input[type=text], input:not([type])")].find(e => e.offsetParent);
  if (!el) return false;
  el.focus();
  if (el.select) el.select(); else document.execCommand("selectAll");
  return true;
}"""


def typing_target():
    """(kind, page) for the app in front when it shows a text box or search screen: "youtube"
    (YouTube's search screen), "box" (a focused text box), "search" (a search page whose box
    isn't focused); else (None, None)."""
    _, page = foreground(focused=True)
    if not page:
        return None, None
    try:
        st = cdp.call(page, TYPING_JS, timeout=4)
    except Exception:
        return None, None
    if st.get("yt"):
        return ("youtube", page) if st.get("search") else (None, None)
    if st.get("box"):
        return "box", page
    if st.get("search"):
        return "search", page
    return None, None


def enter_text(text, submit=True, target=None):
    """Put text in the open text box or search screen of the app in front, replacing what's
    there, and submit it. Returns "searched", "typed", or None (nothing to type into)."""
    kind, page = target or typing_target()
    if kind == "youtube":
        youtube("search", query=text)
        return "searched"
    if kind in ("box", "search"):
        if not cdp.call(page, ENTER_TEXT_JS, timeout=4):
            return None
        cdp.send(page, "Input.insertText", {"text": text})
        if submit:
            for t in ("keyDown", "keyUp"):
                cdp.send(
                    page,
                    "Input.dispatchKeyEvent",
                    {"type": t, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if t == "keyDown" else {})},
                )
        return "typed"
    return None


# ------------------------------------------------------------------ YouTube (VacuumTube)

YT_JS = r"""
async (cmd, wait, limit) => {
  const resolve = c => { for (const k in window._yttv) { const i = window._yttv[k] && window._yttv[k].instance;
                          if (i && i.resolveCommand) return i.resolveCommand(c, {}); } throw "YouTube isn't ready"; };
  const txt = t => !t ? "" : typeof t === "string" ? t : t.content || t.simpleText || (t.runs || []).map(r => r.text).join("");
  const items = () => {
    const out = [], seen = new Set();
    const add = (kind, id, title, info) => { if (id && !seen.has(id)) { seen.add(id); out.push(`${kind} ${id} | ${title}${info ? " | " + info : ""}`); } };
    const walk = (o, d) => {
      if (!o || typeof o !== "object" || d > 45 || out.length >= (limit || 15)) return;
      if (o.tileRenderer) {
        const t = o.tileRenderer, md = (t.metadata || {}).tileMetadataRenderer || {}, s = JSON.stringify(t.onSelectCommand || {});
        const v = (s.match(/"videoId":"([\w-]{11})"/) || [])[1], b = (s.match(/"browseId":"([\w-]+)"/) || [])[1];
        const info = (md.lines || []).map(l => ((l.lineRenderer || {}).items || []).map(i => txt((i.lineItemRenderer || {}).text)).join("")).join(" · ");
        const over = JSON.stringify(t.header || {}).match(/"percentDurationWatched":(\d+)/);
        if (v) add("video", v, txt(md.title), info + (over ? ` · watched ${over[1]}%` : ""));
        else if (b) add(b.startsWith("UC") ? "channel" : "page", b, txt(md.title), info);
        return;
      }
      if (o.lockupViewModel) {
        const l = o.lockupViewModel, md = ((l.metadata || {}).lockupMetadataViewModel) || {};
        const rows = (((md.metadata || {}).contentMetadataViewModel || {}).metadataRows || []).map(r => (r.metadataParts || []).map(p => txt(p.text)).join(" · ")).join(" · ");
        const kind = (l.contentType || "").replace("LOCKUP_CONTENT_TYPE_", "").toLowerCase() || "item";
        add(kind, l.contentId, txt(md.title), rows);
        return;
      }
      for (const k in o) walk(o[k], d + 1);
    };
    for (const el of document.querySelectorAll("*")) {
      if (!el.tagName.startsWith("YTLR-") || !/RESPONSE-RENDERER$|SECTION-LIST-RENDERER$|SURFACE-CONTENT-RENDERER$|GRID-RENDERER$|-TAB-RENDERER$/.test(el.tagName)) continue;
      if (!el.getBoundingClientRect().width || !el.data) continue;
      walk(el.data, 0);
    }
    return out;
  };
  const old = cmd ? items().join("\n") : "";
  if (cmd) resolve(cmd);
  if (!wait) return {page: location.hash};
  // done when the list is non-empty and the same twice in a row, and differs from the list
  // before the command (or 3 s have passed: same page again)
  let last = "";
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 300));
    const got = items(), sig = got.join("\n");
    if (i >= 2 && got.length && sig === last && (sig !== old || i >= 10)) return {page: location.hash, items: got};
    last = sig;
  }
  return {page: location.hash, items: items()};
}
"""


CHANNELS_JS = r"""
(query) => {
  // Subscribed channels: the tabs of the Subscriptions page; each tab's params hold the
  // channel id (UC...) in a base64 protobuf.
  const nav = document.querySelector("ytlr-tv-secondary-nav-renderer");
  const tabs = (((nav && nav.data && nav.data.sections || [])[0] || {}).tvSecondaryNavSectionRenderer || {}).tabs || [];
  const all = [];
  for (const t of tabs) {
    const r = t.tabRenderer || {}, params = ((r.endpoint || {}).browseEndpoint || {}).params || "";
    let id = "";
    try { id = (atob(decodeURIComponent(params).replace(/-/g, "+").replace(/_/g, "/")).match(/UC[\w-]{22}/) || [""])[0]; } catch (e) {}
    if (id && !all.some(l => l.includes(id))) all.push(`channel ${id} | ${r.title}`);
  }
  if (!all.length) throw "the subscriptions list didn't load";
  const norm = s => s.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
  const q = norm(query || "");
  const hits = q ? all.filter(l => { const n = norm(l.split(" | ")[1]); return n && (n.includes(q) || (n.length >= 5 && q.includes(n))); }) : all;
  return hits.length ? hits : ["no subscribed channel matches; all of them:"].concat(all);
}
"""


TABS_JS = r"""
() => {
  // The Subscriptions page's channel tabs: [{title, id, endpoint}] (endpoint opens that
  // channel's own subscription feed, newest first)
  const nav = document.querySelector("ytlr-tv-secondary-nav-renderer");
  const tabs = (((nav && nav.data && nav.data.sections || [])[0] || {}).tvSecondaryNavSectionRenderer || {}).tabs || [];
  const out = [];
  for (const t of tabs) {
    const r = t.tabRenderer || {}, ep = r.endpoint || {}, params = (ep.browseEndpoint || {}).params || "";
    let id = "";
    try { id = (atob(decodeURIComponent(params).replace(/-/g, "+").replace(/_/g, "/")).match(/UC[\w-]{22}/) || [""])[0]; } catch (e) {}
    if (id && !out.some(o => o.id === id)) out.push({title: r.title, id, endpoint: ep});
  }
  return out;
}
"""


def yt_age(text):
    """Seconds since upload from YouTube's 'n units ago' (unknown: very old)."""
    m = re.search(r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s+ago", text)
    if not m:
        return 10**10
    unit = {"second": 1, "minute": 60, "hour": 3600, "day": 86400, "week": 604800, "month": 2592000, "year": 31536000}
    return int(m.group(1)) * unit[m.group(2)]


def youtube_latest(page, query):
    """New videos from one or more channels (comma-separated): each subscribed channel's own
    feed, newest first; the channel that posted most recently stays on screen."""
    norm = lambda s: re.sub(r"[\W_]+", "", (s or "").lower())
    names = [n.strip() for n in (query or "").split(",") if n.strip()]
    if not names:
        return "latest needs a channel name."
    cdp.call(page, YT_JS, {"browseEndpoint": {"browseId": "FEsubscriptions"}}, True, timeout=30)
    tabs = cdp.call(page, TABS_JS)
    found, missing = [], []
    for n in names:
        q = norm(n)
        tab = next((t for t in tabs if norm(t["title"]) == q), None) or next(
            (t for t in tabs if q in norm(t["title"]) or (len(norm(t["title"])) >= 5 and norm(t["title"]) in q)), None
        )
        (found if tab else missing).append(tab or n)
    feeds = []
    for tab in found:
        r = cdp.call(page, YT_JS, tab["endpoint"], True, 8, timeout=30)
        vids = [l for l in r.get("items") or [] if l.startswith("video ")]
        feeds.append((tab, vids, min([yt_age(v) for v in vids] or [10**10])))
    out = []
    if feeds:
        feeds.sort(key=lambda f: f[2])
        if len(feeds) > 1:  # leave the most recent channel's feed on screen
            cdp.call(page, YT_JS, feeds[0][0]["endpoint"], True, 8, timeout=30)
        for tab, vids, _ in feeds:
            out.append(f"{tab['title']} (newest first):\n" + ("\n".join(vids[:6]) or "no videos listed"))
        out[0] += "\n(on screen now)"
    for n in missing:
        out.append(f"{n}: not a subscribed channel; youtube search for it and open its channel id.")
    return "\n\n".join(out)


def youtube_resume(page, query):
    """Continue the most recent video in the history whose title or channel matches query
    (any video if no query); an unfinished one first. YouTube resumes at the saved spot."""
    r = cdp.call(page, YT_JS, {"browseEndpoint": {"browseId": "FEhistory"}}, True, 40, timeout=30)
    norm = lambda s: re.sub(r"[\W_]+", "", (s or "").lower())
    q = norm(query)
    videos = []
    for line in r.get("items") or []:
        kind, _, rest = line.partition(" ")
        vid, _, text = rest.partition(" | ")
        if kind == "video" and (not q or q in norm(text)):
            done = re.search(r"watched (\d+)%", text)
            videos.append((vid, text, int(done.group(1)) if done else 0))
    if not videos:
        return f"Nothing{' from ' + query if query else ''} in the recent YouTube history."
    vid, text, _ = next((v for v in videos if v[2] < 95), videos[0])
    cdp.call(page, YT_JS, {"watchEndpoint": {"videoId": vid}}, False, timeout=30)
    title, _, channel = text.partition(" | ")
    return f"Playing {title} ({channel.split(' · ')[0]})."


def youtube(action, query=None, id=None):
    if not app_page("YouTube"):
        open_app("YouTube")
        for _ in range(20):
            p = app_page("YouTube")
            if p and cdp.evaluate(p, "!!window._yttv", timeout=5):
                break
            time.sleep(1)
    page = app_page("YouTube")
    if not page:
        return "YouTube isn't running."
    raise_window("rocks.shy.VacuumTube.desktop", "YouTube")
    cmds = {
        "search": {"searchEndpoint": {"query": query or ""}},
        "history": {"browseEndpoint": {"browseId": "FEhistory"}},
        "subscriptions": {"browseEndpoint": {"browseId": "FEsubscriptions"}},
        "home": {"browseEndpoint": {"browseId": "FEwhat_to_watch"}},
        "open": {"browseEndpoint": {"browseId": id or ""}},
        "play": {"watchEndpoint": {"videoId": id or ""}},
        "list": None,
        "channels": {"browseEndpoint": {"browseId": "FEsubscriptions"}},
    }
    if action == "resume":
        return youtube_resume(page, query)
    if action == "latest":
        return youtube_latest(page, query)
    if action not in cmds:
        return f"Unknown action {action}."
    if action == "search" and not query or action in ("open", "play") and not id:
        return f"{action} needs {'query' if action == 'search' else 'id'}."
    r = cdp.call(page, YT_JS, cmds[action], action != "play", timeout=30)
    if action == "channels":
        return "\n".join(cdp.call(page, CHANNELS_JS, query or ""))
    if action == "play":
        return f"Playing video {id}."
    items = r.get("items") or []
    return "\n".join(items) if items else f"Nothing listed on {r.get('page')}."


# ------------------------------------------------------------------ Jellyfin (web app)

JF_JS = r"""
async (action, query, id) => {
  const a = window.ApiClient;
  if (!a || !a.getCurrentUserId()) throw "Jellyfin isn't signed in on the TV";
  const uid = a.getCurrentUserId();
  const get = (path, params) => a.getJSON(a.getUrl(path, params));
  const fmt = i => {
    const ud = i.UserData || {}, pos = ud.PlaybackPositionTicks ? ` · resume at ${Math.round(ud.PlaybackPositionTicks / 6e8)} min` : "";
    const ep = i.Type === "Episode" ? `${i.SeriesName} S${i.ParentIndexNumber}E${i.IndexNumber} ` : "";
    return `${i.Type.toLowerCase()} ${i.Id} | ${ep}${i.Name}${i.ProductionYear ? " (" + i.ProductionYear + ")" : ""}${ud.Played ? " · watched" : ""}${pos}`;
  };
  const F = "UserData,ProductionYear";
  if (action === "search") {
    const r = await get("Items", {userId: uid, searchTerm: query, recursive: true, limit: 10, fields: F,
                                  includeItemTypes: "Series,Movie,Episode,Video"});
    return r.Items.map(fmt);
  }
  if (action === "next_up") {
    const r = await get("Shows/NextUp", {userId: uid, seriesId: id || undefined, limit: id ? 1 : 10, fields: F, enableResumable: true});
    return r.Items.length ? r.Items.map(fmt) : ["nothing next (series finished or not started)"];
  }
  if (action === "continue") {
    let r;
    try { r = await get("UserItems/Resume", {userId: uid, limit: 10, fields: F, mediaTypes: "Video"}); }
    catch (e) { r = await get(`Users/${uid}/Items/Resume`, {limit: 10, fields: F, mediaTypes: "Video"}); }
    return r.Items.map(fmt);
  }
  if (action === "episodes") {
    const r = await get(`Shows/${id}/Episodes`, {userId: uid, fields: F});
    return r.Items.map(fmt);
  }
  const play = async item => {        // on this TV, from where it was left off
    if (item.Type === "Series") {
      const n = await get("Shows/NextUp", {userId: uid, seriesId: item.Id, limit: 1, fields: F, enableResumable: true});
      if (!n.Items.length) throw `${item.Name} has no next episode (finished?); pick an episode id`;
      item = n.Items[0];
    }
    const sessions = await a.getSessions({deviceId: a.deviceId()});
    if (!sessions.length) throw "the TV's Jellyfin session isn't connected";
    const start = (item.UserData && item.UserData.PlaybackPositionTicks) || 0;
    await a.sendPlayCommand(sessions[0].Id, {ItemIds: item.Id, PlayCommand: "PlayNow", StartPositionTicks: start});
    return ["playing " + fmt(item)];
  };
  if (action === "play") return play(await get(`Users/${uid}/Items/${id}`, {fields: F}));
  if (action === "resume") {
    // One step: something in progress whose show/movie name matches, else the best
    // matching series (its next episode) or movie.
    const norm = s => (s || "").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
    const q = norm(query);
    if (!q) throw "resume needs the show or movie name as query";
    const hit = i => { const n = norm(i.SeriesName || i.Name); return n && (n.includes(q) || q.includes(n)); };
    let inProgress;
    try { inProgress = await get("UserItems/Resume", {userId: uid, limit: 50, fields: F, mediaTypes: "Video"}); }
    catch (e) { inProgress = await get(`Users/${uid}/Items/Resume`, {limit: 50, fields: F, mediaTypes: "Video"}); }
    const started = inProgress.Items.find(hit);
    if (started) return play(started);
    const found = (await get("Items", {userId: uid, searchTerm: query, recursive: true, limit: 10, fields: F,
                                       includeItemTypes: "Series,Movie"})).Items;
    const best = found.find(i => norm(i.Name) === q) || found.find(i => i.Type === "Series") || found[0];
    if (!best) throw `nothing called "${query}" in Jellyfin (try seerr search to request it)`;
    return play(best);
  }
  throw "unknown action " + action;
}
"""


def jellyfin(action, query=None, id=None):
    page = app_page("Jellyfin")
    if not page:
        open_app("Jellyfin")
        for _ in range(20):
            page = app_page("Jellyfin")
            if page and cdp.evaluate(page, "!!(window.ApiClient && ApiClient.getCurrentUserId())", timeout=5):
                break
            time.sleep(1)
    if not page:
        return "Jellyfin isn't running."
    if action in ("play", "resume"):
        raise_window("couchbox-jellyfin.desktop", "Jellyfin")
    try:
        out = cdp.call(page, JF_JS, action, query, id, timeout=30)
    except cdp.CdpError as err:
        return f"Jellyfin: {err}"
    return "\n".join(out) or "No results."


# ------------------------------------------------------------------ Seerr (requests for Jellyfin)

SEERR_STATUS = {2: "requested, waiting", 3: "requested, downloading", 4: "partly in Jellyfin", 5: "in Jellyfin"}


def seerr_api(method, path, body=None):
    import requests

    base = settings.get("media.seerr.url")
    key = secrets.get("media.seerr.api_key")
    if not base:
        raise RuntimeError("Seerr isn't set up (Settings → Apps).")
    if not key:
        raise RuntimeError("Add Seerr's API key in Settings → Apps to use it from the TV.")
    url = base + "/api/v1" + path
    r = requests.request(method, url, json=body, timeout=20, headers={"X-Api-Key": key})
    if r.status_code >= 400:
        raise RuntimeError(f"Seerr said {r.status_code}: {r.text[:200]}")
    return r.json() if r.content else {}  # DELETE answers 204, no body


def seerr(action, query=None, id=None, type=None):
    """Search TMDB through Seerr (with what's already in Jellyfin / requested), or request."""
    from urllib.parse import quote

    if action == "search":
        r = seerr_api("GET", f"/search?query={quote(query or '')}&page=1")
        out = []
        for i in r.get("results", []):
            if i.get("mediaType") not in ("movie", "tv"):
                continue
            year = (i.get("releaseDate") or i.get("firstAirDate") or "")[:4]
            status = SEERR_STATUS.get((i.get("mediaInfo") or {}).get("status"), "not requested")
            out.append(f"{i['mediaType']} {i['id']} | {i.get('title') or i.get('name')}{f' ({year})' if year else ''} · {status}")
        return "\n".join(out[:10]) or "No matches."
    if action == "request":
        if type not in ("movie", "tv") or not id:
            return "request needs id and type (movie or tv) from a search."
        body = {"mediaType": type, "mediaId": int(id)}
        if type == "tv":
            body["seasons"] = "all"
        r = seerr_api("POST", "/request", body)
        st = {1: "waiting for approval", 2: "approved", 3: "declined"}.get(r.get("status"), "sent")
        return f"Requested {type} {id}: {st}. It shows up in Jellyfin once downloaded."
    return f"Unknown action {action}."


# ------------------------------------------------------------------ any app's page as text

PAGE_JS = r"""
(action, target, text, submit) => {
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 2 && r.height > 2 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth
           && s.visibility !== "hidden" && s.display !== "none" && s.opacity !== "0"; };
  const label = el => (el.getAttribute("aria-label") || el.innerText || el.value || el.placeholder || el.title
                       || el.getAttribute("alt") || "").replace(/\s+/g, " ").trim().slice(0, 90);
  const find = () => {
    let el = /^\d+$/.test(String(target)) ? document.querySelector(`[data-couchbox="${target}"]`) : null;
    if (!el && target) { const t = String(target).toLowerCase();
      el = [...document.querySelectorAll("[data-couchbox]")].find(x => label(x).toLowerCase().includes(t)); }
    if (!el) throw "no element " + target + " (read the page first)";
    return el;
  };
  if (action === "read") {
    document.querySelectorAll("[data-couchbox]").forEach(x => x.removeAttribute("data-couchbox"));
    const sel = 'a[href],button,input,textarea,select,[role=button],[role=link],[role=menuitem],[role=tab],[role=option],[tabindex]:not([tabindex="-1"])';
    const out = []; let n = 0;
    for (const el of document.querySelectorAll(sel)) {
      if (!vis(el) || el.closest("[data-couchbox]")) continue;
      const l = label(el), tag = el.tagName;
      if (!l && tag !== "INPUT") continue;
      el.setAttribute("data-couchbox", ++n);
      out.push(`${n} ${tag === "INPUT" || tag === "TEXTAREA" ? "input" : tag === "A" ? "link" : "button"}: ${l}`);
      if (n >= 60) break;
    }
    const v = document.querySelector("video");
    return {title: document.title, url: location.href, focused: label(document.activeElement || document.body).slice(0, 60),
            video: v && v.duration ? `${v.paused ? "paused" : "playing"} ${Math.round(v.currentTime)}s of ${Math.round(v.duration)}s` : null,
            items: out};
  }
  if (action === "click") { const el = find(); el.scrollIntoView({block: "center"}); el.focus(); el.click(); return "clicked " + label(el); }
  if (action === "type") {
    const el = target ? find() : document.activeElement;
    el.focus();
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    if (submit) {
      for (const t of ["keydown", "keypress", "keyup"]) el.dispatchEvent(new KeyboardEvent(t, {key: "Enter", code: "Enter", keyCode: 13, bubbles: true}));
      if (el.form) el.form.requestSubmit();
    }
    return "typed into " + label(el);
  }
  if (action === "navigate") { location.href = text; return "going to " + text; }
  if (action === "back") { history.back(); return "went back"; }
  throw "unknown action " + action;
}
"""


def page(action, target=None, text=None, submit=False):
    name, p = foreground()
    if not p:
        return "No app with a readable page is in front (the home screen?)."
    if name == "YouTube" and action == "read":
        return "This is YouTube: use the youtube tool (action list shows what's on screen)."
    r = cdp.call(p, PAGE_JS, action, target, text, submit)
    if action != "read":
        time.sleep(1.5)
        return f"{name}: {r}"
    head = f"{name}: {r['title']} ({r['url']})"
    if r.get("video"):
        head += f"\nvideo {r['video']}"
    return head + f"\nfocused: {r['focused']}\n" + "\n".join(r["items"])


# ------------------------------------------------------------------ media, keys, TV

MEDIA_JS = r"""
(action, seconds) => {
  const vids = [...document.querySelectorAll("video")].filter(v => v.duration);
  const v = vids.find(v => !v.paused) || vids[0];
  if (!v) throw "nothing is playing here";
  if (action === "play") v.play();
  else if (action === "pause") v.pause();
  else if (action === "toggle") v.paused ? v.play() : v.pause();
  else if (action === "forward") v.currentTime += seconds || 30;
  else if (action === "back") v.currentTime -= seconds || 10;
  else if (action === "seek") v.currentTime = seconds || 0;
  else if (action === "restart") v.currentTime = 0;
  const yt = document.querySelector(".html5-video-player");
  const t = document.querySelector(".osdTitle, .videoOsdTitle, .pageTitle");
  return {youtube: yt && yt.getVideoData ? yt.getVideoData().video_id : null,
          title: (t && t.innerText.split("\n")[0]) || document.title,
          paused: v.paused, time: v.currentTime, duration: v.duration};
}
"""
JF_MEDIA_JS = r"""
async (action, seconds) => {
  // Jellyfin Desktop plays in its own mpv player: control it through the TV's session
  const a = window.ApiClient;
  const s = a && (await a.getSessions({deviceId: a.deviceId()}))[0];
  if (!s || !s.NowPlayingItem) throw "nothing is playing in Jellyfin";
  const i = s.NowPlayingItem, ps = s.PlayState || {}, dur = (i.RunTimeTicks || 0) / 1e7;
  let t = (ps.PositionTicks || 0) / 1e7, paused = !!ps.IsPaused;
  const seek = to => { t = Math.max(0, Math.min(to, dur - 5)); return a.sendPlayStateCommand(s.Id, "Seek", {SeekPositionTicks: Math.round(t * 1e7)}); };
  if (action === "play") { await a.sendPlayStateCommand(s.Id, "Unpause", {}); paused = false; }
  else if (action === "pause") { await a.sendPlayStateCommand(s.Id, "Pause", {}); paused = true; }
  else if (action === "toggle") { await a.sendPlayStateCommand(s.Id, "PlayPause", {}); paused = !paused; }
  else if (action === "forward") await seek(t + (seconds || 30));
  else if (action === "back") await seek(t - (seconds || 10));
  else if (action === "seek") await seek(seconds || 0);
  else if (action === "restart") await seek(0);
  const title = (i.SeriesName ? `${i.SeriesName} S${i.ParentIndexNumber}E${i.IndexNumber} ` : "") + i.Name;
  return {youtube: null, title, paused, time: t, duration: dur};
}
"""
_yt_titles = {}


def yt_title(vid):
    """'"title" by channel' for a YouTube video id (YouTube's public oEmbed, cached)."""
    if vid not in _yt_titles:
        try:
            import requests

            j = requests.get(
                "https://www.youtube.com/oembed", timeout=4, params={"url": f"https://www.youtube.com/watch?v={vid}", "format": "json"}
            ).json()
            _yt_titles[vid] = f"“{j['title']}” by {j['author_name']}"
        except Exception:
            return f"YouTube video {vid}"
    return _yt_titles[vid]


def media_line(r, app):
    f = lambda s: time.strftime("%H:%M:%S" if s >= 3600 else "%M:%S", time.gmtime(max(0, s)))
    what = yt_title(r["youtube"]) + " on YouTube" if r.get("youtube") else f"“{r['title']}” in {app}"
    return f"{what}: {'paused' if r['paused'] else 'playing'} at {f(r['time'])} of {f(r['duration'])}"


def media(action, seconds=None):
    """The app in front first, then any app with something playing."""
    a = app_of_window(active_window())
    site = streaming.site_of_app(a.id) if a not in (None, "home") else None
    if site and appctl.running(site):
        return streaming.media(site, action, seconds)
    name, p = foreground()
    jf = [("Jellyfin", x, JF_MEDIA_JS) for x in cdp.pages(cdp.JELLYFIN_PORT)]
    candidates = (
        (jf if name == "Jellyfin" else [(name, p, MEDIA_JS)] if p else [])
        + [("YouTube", x, MEDIA_JS) for x in cdp.pages(cdp.YOUTUBE_PORT)]
        + jf
        + [("a web app", x, MEDIA_JS) for x in cdp.pages(cdp.WEB_PORT)]
    )
    last = "Nothing is playing."
    for app, pg, js in candidates:
        try:
            return media_line(cdp.call(pg, js, action, seconds), app)
        except Exception as err:
            last = str(err)
    return last


CAPTIONS_JS = r"""
(lang) => {
  // Once per video: if no captions are showing, turn on `lang` (a real track, else the
  // auto-generated one, else a translation). Turning them off by hand then sticks.
  const p = document.querySelector(".html5-video-player");
  if (!p || !p.getVideoData || !location.hash.startsWith("#/watch")) return null;
  const id = p.getVideoData().video_id;
  if (!id || window.__couchboxCaptioned === id) return null;
  p.loadModule("captions");
  const tracks = p.getOption("captions", "tracklist", {includeAsr: true}) || [];
  if (!tracks.length) return null;                     // not loaded yet: try again next time
  window.__couchboxCaptioned = id;
  const cur = p.getOption("captions", "track") || {};
  if (cur.languageCode) return null;
  const mine = tracks.filter(t => (t.languageCode || "").startsWith(lang));
  const pick = mine.find(t => t.kind !== "asr") || mine[0];
  if (pick) p.setOption("captions", "track", pick);
  else p.setOption("captions", "track", Object.assign({}, tracks[0], {translationLanguage: {languageCode: lang}}));
  return id;
}
"""


def keep_captions(lang):
    """Called every few seconds by the service: English captions on each new YouTube video."""
    for pg in cdp.pages(cdp.YOUTUBE_PORT):
        try:
            return cdp.call(pg, CAPTIONS_JS, lang, timeout=5)
        except Exception:
            return None


KEYS = {
    "up": e.KEY_UP,
    "down": e.KEY_DOWN,
    "left": e.KEY_LEFT,
    "right": e.KEY_RIGHT,
    "ok": e.KEY_ENTER,
    "back": e.KEY_ESC,
    "home": e.KEY_HOMEPAGE,
    "menu": e.KEY_MENU,
    "play_pause": e.KEY_PLAYPAUSE,
}
_ui = None


def media_key(action):
    """Play/Pause etc. through couchbox-mediakeys (the player in front, else what's playing);
    False if it had nothing to control or isn't running."""
    try:
        return bool(appctl.call("mediakeys", {"op": "key", "action": action}, timeout=2).get("player"))
    except (appctl.NotRunning, OSError, ValueError, RuntimeError):
        return False


def press(keys):
    global _ui
    if _ui is None:
        _ui = UInput({e.EV_KEY: list(KEYS.values())}, name="couchbox-voice-keys")
        time.sleep(0.5)
    done = []
    for k in keys:
        name, _, n = str(k).lower().partition("*")
        if name not in KEYS:
            return f"Unknown key {name}. Keys: {', '.join(KEYS)}."
        for _ in range(int(n or 1)):
            if name == "play_pause" and media_key("playpause"):  # whatever is playing, like the remote's key
                time.sleep(0.25)
                continue
            _ui.write(e.EV_KEY, KEYS[name], 1)
            _ui.syn()
            _ui.write(e.EV_KEY, KEYS[name], 0)
            _ui.syn()
            time.sleep(0.25)
        done.append(k)
    time.sleep(0.5)
    return "Pressed " + ", ".join(done) + "."


def tv(action, times=1):
    cmd = {"on": "on", "off": "off", "volume_up": "volume-up", "volume_down": "volume-down", "mute": "mute"}.get(action)
    if not cmd:
        return f"Unknown action {action}."
    for _ in range(max(1, min(int(times or 1), 20)) if cmd.startswith("volume") else 1):
        subprocess.run(["/usr/lib/couchbox/bin/couchbox-tv", cmd], capture_output=True, timeout=15)
    return f"TV {action.replace('_', ' ')}" + (f" x{times}" if cmd.startswith("volume") and times > 1 else "") + "."


# ------------------------------------------------------------------ schemas
# Tools follow the home row: a hidden app's tool is left out (and Jellyfin and Seerr also need
# their servers set). Descriptions stay short: the model reads them on every request.

STREAMING_ACTIONS = ["continue", "search", "shows", "latest", "episodes", "resume", "play", "open", "mylist"]
TOOL_APP = {
    "youtube": "youtube",
    "jellyfin": "jellyfin",
    "seerr": "seerr",
    "frigate": "frigate",
    "weather": "weather",
    "search": "search",
    "spotify": "spotify",
    "maps": "maps",
    "movies": "movies",
    **{t: a for t, (_, a) in streaming.SITES.items()},
}


def schemas():
    """The tools the model gets now."""
    st = settings.load()
    off = disabled_tools(st)
    return [t for t in _schemas(st) if t["function"]["name"] not in off]


def disabled_tools(st):
    vis = visible_ids(st)
    off = {tool for tool, app in TOOL_APP.items() if app not in vis}
    if not st["media.jellyfin.url"]:
        off.add("jellyfin")
    if not (st["media.seerr.url"] and secrets.is_set("media.seerr.api_key")):
        off.add("seerr")
    if not st["media.frigate.url"]:
        off.add("frigate")
    if not weather.place_from_settings(st):
        off.add("weather")
    if not ((st["media.seerr.url"] and secrets.is_set("media.seerr.api_key")) or secrets.is_set("media.tmdb.token")):
        off.add("movies")
    if not any(a.kind == "web" for a in registry.home_row(st) if a.hideable):
        off.add("page")
    return off


def _schemas(st=None):
    st = st or settings.load()
    names = [a.name for a in registry.home_row(st) if a.hideable]
    s = lambda **kw: {"type": "object", "properties": kw, "required": [k for k, v in kw.items() if v.pop("req", False)]}
    act = lambda enum, desc: {"type": "string", "enum": enum, "description": desc, "req": True}
    q = {"type": "string"}
    fn = lambda name, desc, params: {"type": "function", "function": {"name": name, "description": desc, "parameters": params}}
    out = [
        fn("open_app", "Open an app or go Home.", s(name={"type": "string", "enum": names + ["Home"], "req": True})),
        fn(
            "youtube",
            "YouTube (signed in). Lists: 'video <id> | title | channel · info'.",
            s(
                action=act(
                    ["resume", "latest", "search", "history", "home", "subscriptions", "channels", "open", "play", "list"],
                    "resume: continue the latest video matching query (channel or title), one step · latest: new videos of the "
                    "channel(s) in query, comma-separated; shows them, doesn't play · home: recommended · channels: subscribed "
                    "(query filters) · open: channel/playlist id · play: video id · list: what's on screen",
                ),
                query=q,
                id=q,
            ),
        ),
        fn(
            "jellyfin",
            "The household's own shows and movies.",
            s(
                action=act(
                    ["resume", "search", "next_up", "continue", "episodes", "play"],
                    "resume: continue the show or movie in query, one step · next_up (id: series, optional) · continue: in progress "
                    "· episodes (id: series) · play (id; a series plays its next episode)",
                ),
                query=q,
                id=q,
            ),
        ),
        fn(
            "seerr",
            "Request movies and shows: they download into Jellyfin. Results show if it's already there.",
            s(
                action=act(["search", "request"], "search (query) · request (id, type)"),
                query=q,
                id=q,
                type={"type": "string", "enum": ["movie", "tv"]},
            ),
        ),
        fn(
            "spotify",
            "Spotify music, played on this TV (keeps playing in the background).",
            s(
                action=act(
                    ["play", "now", "like", "unlike", "add_to_playlist", "make_playlist", "pause", "resume", "next", "previous"],
                    "play: query (a song, artist, album, or one of the user's playlists: 'my Discover Weekly', 'liked songs'); "
                    "kind narrows it · now: what's playing · like/unlike/add_to_playlist (name): the song playing · "
                    "make_playlist: a new playlist called name from songs you pick, 'Artist - Title', 15-30 of them",
                ),
                query=q,
                kind={"type": "string", "enum": ["track", "artist", "album", "playlist"]},
                name=q,
                songs={"type": "array", "items": {"type": "string"}},
            ),
        ),
        fn(
            "frigate",
            "Home security cameras (Frigate): show one live, all of them, the alerts, or the last day's timeline.",
            s(
                action=act(
                    ["camera", "all", "alerts", "detections", "timeline"],
                    "camera: show the camera named in query full screen, live · timeline: the last day (of the camera in query, if any)",
                ),
                query=q,
            ),
        ),
        fn(
            "weather",
            "The forecast where this TV is (14 days), air quality and pollen. Answer from what it returns; show: also put it on the TV.",
            s(
                action=act(
                    ["now", "day", "week", "radar", "air", "pollen"],
                    "now: now and the rest of today · day: the day(s) in day · week: a line a day · radar: put the rain radar on the TV"
                    " · air: air quality now and the next days · pollen: tree, grass and weed pollen (today, or day)",
                ),
                day={"type": "string", "description": "today, tomorrow, a weekday, this/next weekend, or YYYY-MM-DD"},
                show={"type": "boolean"},
            ),
        ),
        fn(
            "search",
            "Google on the TV (the Search app): results, pages, and the page in front as text.",
            s(
                action=act(
                    ["search", "read", "open"],
                    "search: Google's results for query · read: the page in front (to summarize or answer) · open: address in query",
                ),
                query=q,
            ),
        ),
        fn(
            "maps",
            "Maps: drive times, directions, when to leave. query: a saved place (work...), a place or address; origin: Home if unset.",
            s(
                action=act(
                    ["eta", "directions", "leave_by", "search", "places"],
                    "eta: how long to get to query now · directions: show the route (mode) · leave_by: when to leave to "
                    "be at query by time · search: places matching query · places: the saved places and their drive times",
                ),
                query=q,
                mode={"type": "string", "enum": ["drive", "transit", "walk", "bike"]},
                time={"type": "string", "description": "leave_by: arrival time, 24-hour HH:MM"},
                origin=q,
            ),
        ),
        fn(
            "movies",
            "Facts on movies, shows and people: who made or starred, IMDb/RT ratings, filmographies. Never answer from memory.",
            s(
                action=act(
                    ["title", "person", "search", "top"],
                    "title: the movie or show in query · person: an actor, director or writer and their work, e.g. 'X's movies' "
                    "(role filters it; jellyfin only to play) · search · top: the best rated (type). Shows it on the TV",
                ),
                query=q,
                type={"type": "string", "enum": ["movie", "tv"]},
                role={"type": "string", "enum": ["acting", "directing", "writing", "producing"]},
            ),
        ),
    ]
    for tool, (site, app_id) in streaming.SITES.items():
        a = registry.get(app_id, st)
        name = a.name if a else tool
        if tool == "twitch":
            out.append(
                fn(
                    tool,
                    "Twitch. Lists: 'live|series|video <id> | title | details'.",
                    s(
                        action=act(
                            ["live", "search", "videos", "play"],
                            "live: followed channels live now · videos: a channel's past broadcasts (query) "
                            "· play: a channel name (its live stream) or an id from a list",
                        ),
                        query=q,
                        id=q,
                    ),
                )
            )
            continue
        out.append(
            fn(
                tool,
                f"{name}. Lists: 'video|series <id> | title | details'.",
                s(
                    action=act(
                        STREAMING_ACTIONS,
                        "continue: Continue Watching · resume: continue the show in query, one step · latest: newest episodes of the show named in query, one step "
                        "· episodes (query or id, season) · shows: all (query filters) · play: video id · open: series id "
                        "(or query: a search) · mylist",
                    ),
                    query=q,
                    id=q,
                    season={"type": "integer"},
                ),
            )
        )
    out += [
        fn("say", "Show a short message now, while you keep working.", s(text={"type": "string", "req": True})),
        fn(
            "page",
            "The web app in front, as text.",
            s(
                action=act(
                    ["read", "click", "type", "navigate", "back"],
                    "read: numbered controls · click target · type text (submit: Enter) · navigate url",
                ),
                target=q,
                text=q,
                submit={"type": "boolean"},
            ),
        ),
        fn(
            "media",
            "What's playing (the app in front first).",
            s(
                action=act(
                    ["status", "play", "pause", "toggle", "forward", "back", "seek", "restart"], "forward/back by seconds; seek to seconds"
                ),
                seconds={"type": "number"},
            ),
        ),
        fn(
            "remote",
            "Press remote keys (last resort): up down left right ok back home menu play_pause; 'down*3' repeats.",
            s(keys={"type": "array", "items": {"type": "string"}, "req": True}),
        ),
        fn(
            "tv",
            "The TV itself.",
            s(action=act(["on", "off", "volume_up", "volume_down", "mute"], "volume: times = steps"), times={"type": "integer"}),
        ),
    ]
    return out


def status_text(name, args):
    """Short line for the on-screen indicator."""
    a = args
    if name in streaming.SITES:
        app = registry.get(streaming.SITES[name][1])
        what = {
            "search": f"Searching for “{a.get('query')}”",
            "latest": f"Newest {a.get('query') or 'episodes'}",
            "resume": f"Resuming {a.get('query') or ''}".strip(),
            "continue": "Checking Continue Watching",
            "live": "Who's live",
            "play": "Starting it",
            "episodes": "Looking at episodes",
        }.get(a.get("action"), "Looking")
        return f"{app.name if app else name}: {what}"
    return {
        "open_app": lambda: f"Opening {a.get('name')}",
        "youtube": lambda: {
            "search": f"Searching YouTube for “{a.get('query')}”",
            "history": "Checking your YouTube history",
            "subscriptions": "Checking your subscriptions",
            "play": "Starting the video",
            "channels": "Looking through your channels",
            "home": "Checking recommendations",
            "resume": f"Picking up {a.get('query') or 'your last video'}",
            "latest": f"New videos from {a.get('query')}",
            "open": "Opening the channel",
        }.get(a.get("action"), "Looking at YouTube"),
        "jellyfin": lambda: {
            "search": f"Searching Jellyfin for “{a.get('query')}”",
            "play": "Starting playback",
            "resume": f"Resuming {a.get('query')}",
            "next_up": "Finding the next episode",
            "continue": "Checking what you were watching",
        }.get(a.get("action"), "Looking in Jellyfin"),
        "page": lambda: {"read": "Reading the screen", "click": f"Selecting {a.get('target')}", "type": f"Typing “{a.get('text')}”"}.get(
            a.get("action"), "Navigating"
        ),
        "media": lambda: {"status": "Checking what's playing"}.get(a.get("action"), a.get("action", "").capitalize()),
        "remote": lambda: "Pressing " + ", ".join(a.get("keys") or []),
        "tv": lambda: "TV " + str(a.get("action", "")).replace("_", " "),
        "seerr": lambda: f"Searching Seerr for “{a.get('query')}”" if a.get("action") == "search" else "Requesting it",
        "frigate": lambda: f"Showing the {a.get('query')} camera" if a.get("action") == "camera" else "Showing the cameras",
        "weather": lambda: {"radar": "Showing the radar", "air": "Checking the air quality", "pollen": "Checking the pollen"}.get(
            a.get("action"), "Checking the forecast" + (f" for {a.get('day')}" if a.get("day") else "")
        ),
        "search": lambda: {"search": f"Googling “{a.get('query')}”", "read": "Reading the page"}.get(a.get("action"), "Opening the page"),
        "spotify": lambda: {
            "play": f"Finding “{a.get('query')}” on Spotify" if a.get("query") else "Playing",
            "now": "Checking what's playing",
            "like": "Liking this song",
            "add_to_playlist": f"Adding it to {a.get('name') or a.get('query')}",
            "make_playlist": f"Making “{a.get('name') or a.get('query')}”",
        }.get(a.get("action"), "Spotify"),
        "maps": lambda: {
            "eta": f"Checking the drive to {a.get('query')}",
            "directions": f"Directions to {a.get('query')}",
            "leave_by": f"When to leave for {a.get('query')}",
            "search": f"Looking for {a.get('query')}",
        }.get(a.get("action"), "Checking your places"),
        "movies": lambda: f"Looking up {a.get('query')}" if a.get("query") else "Opening Movies & TV",
        "say": lambda: str(a.get("text", "")),
    }.get(name, lambda: name)()


def run_streaming(tool, args):
    a = registry.get(streaming.SITES[tool][1])
    return streaming.run(
        tool,
        args["action"],
        args.get("query"),
        args.get("id"),
        args.get("season"),
        start=lambda: open_app(a.name, wait=False),
        raise_app=lambda: raise_window(a.desktop, a.name),
    )


def match_camera(query, cams):
    """The camera a spoken name means ("front door", "the backyard cam"), or None."""
    q = re.sub(r"\b(the|camera|cam)\b", " ", (query or "").lower().replace("_", " "))
    q = " ".join(q.split())
    if not q:
        return None
    for c in cams:  # exact first, then contained either way
        if q in (c["name"].replace("_", " "), c["label"].lower()):
            return c
    hits = [c for c in cams if q in c["label"].lower() or c["label"].lower() in q]
    return min(hits, key=lambda c: len(c["label"])) if hits else None


def frigate_tool(action, query=None):
    a = registry.get("frigate")
    streaming.ensure("frigate", start=lambda: open_app(a.name, wait=False))
    if action == "camera" or (action == "timeline" and query):
        cams = appctl.call("frigate", {"op": "call", "fn": "config"}, timeout=30)["cameras"]
        cam = match_camera(query, cams)
        if not cam:
            return f"No camera called {query!r}. Cameras: " + ", ".join(c["label"] for c in cams)
        if action == "timeline":
            target, said = f"timeline:{cam['name']}", f"Showing the last day of {cam['label']}."
        else:
            target, said = f"camera:{cam['name']}", f"Showing {cam['label']}, live."
    else:
        target = {"all": "live", "alerts": "alerts", "detections": "detections", "timeline": "timeline"}.get(action, "live")
        said = {
            "live": "Showing all cameras.",
            "alerts": "Showing the alerts.",
            "detections": "Showing the detections.",
            "timeline": "Showing the last day.",
        }[target]
    appctl.call("frigate", {"op": "open", "target": target})
    raise_window(a.desktop, a.name)
    return said


_weather = None


def weather_tool(action, day=None, show=False):
    """The forecast as text for the model to answer from; show=True also opens the Weather app
    there (today, the fortnight, or the day asked about); action "radar" opens its radar loop."""
    global _weather
    place = weather.place_from_settings()
    if not place:
        return "No town is set (Settings → Time), so there's no forecast."
    _weather = _weather or weather.Weather(key_source=lambda: secrets.get("apps.maps.google_api_key"))
    data = _weather.get(place, clock24=place["clock24"])
    if action == "day" and not day:
        action = "now"
    radar = action == "radar"
    out = weather.voice_report(data, "now" if radar else action, day)
    if show or radar:
        target = {"now": "today", "week": "week", "radar": "radar"}.get(action, "today")
        if action == "day":
            picked = weather.pick_days(data["days"], day)
            target = f"day:{picked[0]['date']}" if len(picked) == 1 else "week" if picked else "today"
        a = registry.get("weather")
        streaming.ensure("weather", start=lambda: open_app(a.name, wait=False))
        appctl.call("weather", {"op": "open", "target": target})
        raise_window(a.desktop, a.name)
        out += "\n(The rain radar is on the TV.)" if radar else "\n(Shown on the TV.)"
    return out


def search_tool(action, query=None):
    a = registry.get("search")
    streaming.ensure("search", start=lambda: open_app(a.name, wait=False))
    if action == "read":
        r = appctl.call("search", {"op": "read"}, timeout=30)
        if r.get("error"):
            return r["error"]
        return f"Page: {r['title']} ({r['url']})\n{r['text']}"
    if not (query or "").strip():
        return "Missing query."
    target = ("url:" if action == "open" else "search:") + query.strip()
    appctl.call("search", {"op": "open", "target": target})
    raise_window(a.desktop, a.name)
    return f"Showing Google's results for {query.strip()!r}." if action == "search" else f"Opening {query.strip()}."


def spotify_tool(args):
    """Through the Spotify background service (couchbox-spotify --connect, the TV user's): it
    has the sign-in and plays here. Spotify's data isn't passed to the model beyond the reply."""
    req = {
        "op": "voice",
        "action": args["action"],
        "query": args.get("query") or "",
        "kind": args.get("kind") or "",
        "name": args.get("name") or "",
        "songs": [str(x) for x in args.get("songs") or []][:60],
    }
    try:
        return appctl.call("spotify-connect", req, timeout=90).get("result", "Done.")
    except appctl.NotRunning:
        return "Spotify isn't set up on this TV yet: open Spotify and follow Setup."


def arrival_time(hhmm, now=None):
    """'17:00' (or '5:00 pm') -> the next time it's that o'clock, as epoch seconds."""
    m = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?m?\.?\s*$", (hhmm or "").lower())
    if not m:
        raise ValueError(f"Not a time: {hhmm!r}")
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "p" and h < 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    now = now or time.time()
    lt = time.localtime(now)
    t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, mi, 0, 0, 0, -1))
    return t + 86400 if t < now - 60 else t


def clock_text(t):
    if settings.derived()["clock24"]:
        return time.strftime("%H:%M", time.localtime(t))
    return time.strftime("%I:%M %p", time.localtime(t)).lstrip("0")


def maps_tool(action, query=None, mode=None, when=None, origin=None):
    a = registry.get("maps")
    streaming.ensure("maps", start=lambda: open_app(a.name, wait=False))
    call = lambda fn, **args: appctl.call("maps", {"op": "call", "fn": fn, "args": args}, timeout=45)

    def check(r):
        if isinstance(r, dict) and r.get("error"):
            raise RuntimeError(r["error"])
        return r

    def show(target):
        appctl.call("maps", {"op": "open", "target": target})
        raise_window(a.desktop, a.name)

    mode = mode or "drive"
    if action == "places":
        places = check(call("places"))["places"]
        etas = {e["id"]: e for e in check(call("etas"))["etas"]}
        show("places")
        lines = [
            p["name"] + (f": {etas[p['id']]['duration_text']} by car now" if etas.get(p["id"], {}).get("duration_text") else "")
            for p in places
        ]
        return "Saved places: " + "; ".join(lines) + "."
    if action == "search":
        hits = check(call("search", query=query))["results"][:5]
        show("search:" + (query or ""))
        if not hits:
            return f"Nothing found for {query!r}."
        return "Found: " + "; ".join(
            f"{h['name']} ({h.get('address') or ''}{', ' + h['distance_text'] if h.get('distance_text') else ''})" for h in hits
        )
    if not query:
        return "Where to?"
    to = check(call("resolve", query=query))
    frm = check(call("resolve", query=origin)) if origin else None
    if action == "leave_by":
        arrive = arrival_time(when)
        r = check(call("leave_by", to=to, arrive=arrive, mode=mode, **({"from": frm} if frm else {})))
        show("leave:" + json.dumps({"place": to, "arrive": arrive, "mode": mode}))
        rt = r["route"]
        how = {"drive": "drive", "transit": "trip by transit", "walk": "walk", "bike": "ride"}[mode] + (
            " with expected traffic" if r.get("traffic") else ""
        )
        if r.get("late"):
            return f"Leave now: the {rt['duration_text']} {how} gets you to {to['name']} at {clock_text(rt['arrive'])}, after {clock_text(arrive)}."
        return f"Leave by {clock_text(r['leave'])} to reach {to['name']} by {clock_text(arrive)} ({rt['duration_text']} {how})."
    r = check(call("directions", to=to, mode=mode, **({"from": frm} if frm else {})))
    show("to:" + json.dumps({"place": to, "mode": mode}))
    if not r["routes"]:
        return f"No route to {to['name']}."
    rt = r["routes"][0]
    traffic = {"heavy": " in heavy traffic", "moderate": " with some traffic", "light": " in light traffic"}.get(rt.get("traffic"), "")
    via = f" via {rt['summary']}" if rt.get("summary") else ""
    word = {"drive": "by car", "transit": "by transit", "walk": "on foot", "bike": "by bike"}[mode]
    return (
        f"{to['name']}: {rt['duration_text']} {word}{traffic} right now{via}, {rt['distance_text']}, arriving {clock_text(rt['arrive'])}."
    )


# ------------------------------------------------------------------ Movies & TV (facts about titles and people)
MOVIES_ROLE = {"acting": "Acting", "directing": "Directing", "writing": "Writing", "producing": "Production"}


def _names(people, n=3):
    return ", ".join(p["name"] for p in people[:n])


def movie_summary(t):
    """A title as a few sentences for the model: what, who made it, who's in it, the ratings."""
    tv = t["type"] == "tv"
    what = [("TV series " + t["year"] + "–" + t["end_year"]) if tv else t["year"] + " movie"]
    what += [x for x in (t["certification"], f"{t['seasons_count']} seasons" if tv and t["seasons_count"] else "") if x]
    if not tv and t["runtime"]:
        what.append(f"{t['runtime']} min")
    if t["networks"]:
        what.append("on " + ", ".join(t["networks"]))
    out = [f"{t['title']} ({', '.join(what)}; {', '.join(t['genres'][:3])})."]
    if t["directors"]:
        out.append(f"Directed by {_names(t['directors'])}.")
    if t["creators"]:
        out.append(f"Created by {_names(t['creators'])}.")
    if t["writers"]:
        out.append(f"Written by {_names(t['writers'])}.")
    if t["cast"]:
        out.append("Starring " + ", ".join(f"{c['name']} ({c['role']})" if c["role"] else c["name"] for c in t["cast"][:5]) + ".")
    r = t["ratings"]
    scores = []
    if r.get("imdb"):
        scores.append(f"IMDb {r['imdb']['rating']}/10 ({r['imdb']['votes']:,} votes)")
    if r.get("rt"):
        scores.append(
            f"Rotten Tomatoes {r['rt']['critics']}% critics" + (f", {r['rt']['audience']}% audience" if r["rt"].get("audience") else "")
        )
    if r.get("tmdb"):
        scores.append(f"TMDB {r['tmdb']['score']}/10")
    if scores:
        out.append("; ".join(scores) + ".")
    if t["available"]:
        out.append(
            {"available": "It's in Jellyfin.", "partial": "Some of it is in Jellyfin.", "requested": "It's been requested in Seerr."}[
                t["available"]
            ]
        )
    if t["overview"]:
        out.append("Story: " + t["overview"])
    return " ".join(out)


def person_summary(p, dept=""):
    job = {"Acting": "actor", "Directing": "director", "Writing": "writer", "Production": "producer"}.get(p["dept"], p["dept"].lower())
    out = [p["name"] + (f", {job}" if job else "")]
    if p["born"]:
        out[0] += f", born {p['born']}" + (f" in {p['place']}" if p["place"] else "") + (f", died {p['died']}" if p["died"] else "")
    out[0] += "."
    if p["known_for"]:
        out.append("Known for: " + ", ".join(f"{c['title']} ({c['year'] or 'upcoming'})" for c in p["known_for"][:8]) + ".")
    for d in [dept] if dept else list(p["credits"])[:3]:
        work = [c for c in p["credits"].get(d) or [] if not c["talk"]]
        if not work:
            continue
        lines = [
            f"{c['title']} ({c['year'] or 'upcoming'}" + (f", {c['role']}" if c["role"] else "") + ")" for c in work[: 25 if dept else 6]
        ]
        out.append(f"{d} ({len(work)}, newest first): " + "; ".join(lines) + ".")
    return " ".join(out)


def open_movies(target):
    a = registry.get("movies")
    try:
        streaming.ensure("movies", start=lambda: open_app(a.name, wait=False))
        appctl.call("movies", {"op": "open", "target": target})
        raise_window(a.desktop, a.name)
    except Exception:  # the answer still stands without the app
        pass


def movies_tool(action, query=None, type=None, role=None):
    from couchbox.services import movies as mv

    m = mv.Movies.for_root()
    if action == "top":
        kind = type if type in ("movie", "tv") else "movie"
        items = m.top(kind, pages=1)["items"][:10]
        open_movies(f"top:{kind}")
        return (
            "Top rated "
            + ("shows" if kind == "tv" else "movies")
            + ": "
            + "; ".join(f"{c['rank']}. {c['title']} ({c['year']}, {c['score']})" for c in items)
            + "."
        )
    if not query:
        return "Say which movie, show or person."
    if action == "search":
        r = m.search(query)
        open_movies("search:" + query)
        parts = [
            f"{k}: " + ", ".join(c["title"] + (f" ({c['year']})" if c.get("year") else "") for c in r[key][:4])
            for k, key in (("People", "people"), ("Movies", "movies"), ("Shows", "tv"))
            if r[key]
        ]
        return ("Found " + " · ".join(parts) + ".") if parts else f"Nothing found for {query!r}."
    hit = m.find(query, "person" if action == "person" else type)
    if not hit:
        return f"Nothing called {query!r} found."
    if hit["type"] == "person":
        dept = MOVIES_ROLE.get(role or "", "")
        p = m.person(hit["id"])
        open_movies(f"person:{p['id']}" + (f":{dept}" if dept else ""))
        return person_summary(p, dept)
    t = m.title(hit["type"], hit["id"])
    open_movies(f"{t['type']}:{t['id']}")
    return movie_summary(t)


def run_tool(name, args):
    if name in disabled_tools(settings.load()):
        return f"{name} isn't available on this box."
    fn = {
        "open_app": lambda: open_app(args["name"]),
        "youtube": lambda: youtube(args["action"], args.get("query"), args.get("id")),
        "jellyfin": lambda: jellyfin(args["action"], args.get("query"), args.get("id")),
        "page": lambda: page(args["action"], args.get("target"), args.get("text"), bool(args.get("submit"))),
        "media": lambda: media(args["action"], args.get("seconds")),
        "remote": lambda: press(args.get("keys") or []),
        "tv": lambda: tv(args["action"], args.get("times") or 1),
        "seerr": lambda: seerr(args["action"], args.get("query"), args.get("id"), args.get("type")),
        "frigate": lambda: frigate_tool(args["action"], args.get("query")),
        "weather": lambda: weather_tool(args["action"], args.get("day"), bool(args.get("show"))),
        "search": lambda: search_tool(args["action"], args.get("query")),
        "spotify": lambda: spotify_tool(args),
        "maps": lambda: maps_tool(args["action"], args.get("query"), args.get("mode"), args.get("time"), args.get("origin")),
        "movies": lambda: movies_tool(args["action"], args.get("query"), args.get("type"), args.get("role")),
        "say": lambda: "Shown.",
        **{t: (lambda t=t: run_streaming(t, args)) for t in streaming.SITES},
    }.get(name)
    if not fn:
        return f"Unknown tool {name}."
    try:
        return str(fn())
    except KeyError as err:
        return f"Missing argument {err}."
    except Exception as err:  # report to the model, which can try something else
        return f"Error: {err}"


def screen_summary():
    """One line about what's in front (any app, from KWin) and what it's playing, given to the
    model with each request: "play the newest one" means the app in front."""
    a = app_of_window(active_window())
    if a == "home":
        return "Screen: the home screen."
    if a is not None:
        site = streaming.site_of_app(a.id)
        if site:
            return "Screen: " + streaming.state_line(site, a.name) + "."
        if a.kind != "web" and a.id not in ("youtube", "jellyfin"):
            return f"Screen: {a.name} in front."
        name, p = a.name, app_page(a.name)
    else:
        name, p = foreground()
    if not p:
        return f"Screen: {name} in front." if name else "Screen: the home screen (or an app without a page)."
    try:
        js = JF_MEDIA_JS if name == "Jellyfin" else MEDIA_JS
        playing = media_line(cdp.call(p, js, "status", None, timeout=4), name)
    except Exception:
        playing = "nothing playing"
    return f"Screen: {name} in front; {playing}."
