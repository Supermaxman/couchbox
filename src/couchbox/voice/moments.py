"""Playing Moments (couchbox.moments is the list): teaching one from what plays now, starting
it, keeping it going, and putting the TV back as it was when it stops. Runs in the voice service
(root): the assistant's moments tool, the phone page and the home screen's tiles (through
couchboxd) all start them here.

    capture()           what plays now, as a Moment's app, target, title and picture
    teach(name, ...)    capture() saved under a name (taught again: replaced)
    start(id)           open it in its app, set its volume, black the picture if asked
    stop()              pause it; the volume and the picture go back as they were
    wake()              the picture back (any key on the remote, while it's dark)
    watch(log)          the service's thread: repeats, and notices when it's over

What plays now is couchbox.moments' state file (moments.json, "active"): the watcher reads it
every few seconds, so a Moment started from anywhere is looked after the same way.

Volume: the TV's own volume can't be read or set to a number (its remote keys go over HDMI-CEC or
infrared, and the TV doesn't answer CEC's volume question), so a Moment's volume is the box's own
sound level (the TV session's output, normally 100%: the TV's volume sits on top of it).
Repeat: Jellyfin's player loops the file itself (mpv's loop-file); YouTube and the streaming apps
are taken back to the start a few seconds before the end. Dark: a black layer over everything
(couchbox-voice-overlay draws it while /state says dark); the HDMI signal stays, so the TV stays
on its input, and the app keeps playing, so the box doesn't count as idle: couchbox-memory doesn't
close an app that plays, and the updater doesn't install while something plays.
"""

import os
import re
import subprocess
import threading
import time

from couchbox import appctl, moments, settings
from couchbox import apps as registry

from . import cdp, streaming, tools, ytnative

DARK_FLAG = "/run/couchbox/voice/moment-dark"  # couchbox-input: a key press brings the picture back
POLL = 2  # seconds between looks at what plays
GRACE = 60  # seconds an app has to start playing it (after a start, or starting it again)
GONE = 6  # seconds it may be missing (a page loading) before it's over
END_MARGIN = {"youtube": 4, "streaming": 12, "jellyfin": 15}  # repeat: back to the start this close to the end
_lock = threading.RLock()
_seen = {}  # the Moment playing, as last seen (not written down: a restart starts its grace again)
_dark = [False]  # the picture is black now (read by /state many times a second: not from the file)


class MomentFailed(RuntimeError):
    """The Moment couldn't be taught or started; the message is for the screen."""


# ------------------------------------------------------------------ the box's sound level
def _as_tv(cmd, timeout=5):
    pw, env = tools.tv_env()
    pre = [] if os.geteuid() == pw.pw_uid else ["runuser", "-u", tools.TV_USER, "--"]
    return subprocess.run(pre + ["env"] + [f"{k}={v}" for k, v in env.items()] + cmd, capture_output=True, text=True, timeout=timeout)


def get_volume():
    """The TV session's output level (1.0 = 100%), or None."""
    try:
        m = re.search(r"Volume:\s*([\d.]+)", _as_tv(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]).stdout)
    except (OSError, subprocess.SubprocessError, KeyError):
        return None
    return float(m.group(1)) if m else None


def set_volume(level):
    try:
        _as_tv(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{max(0.0, min(1.0, level)):.2f}"])
    except (OSError, subprocess.SubprocessError, KeyError):
        pass


# ------------------------------------------------------------------ the apps
JF_NOW_JS = r"""
async () => {
  const a = window.ApiClient;
  const s = a && (await a.getSessions({deviceId: a.deviceId()}))[0];
  if (!s || !s.NowPlayingItem) return null;
  const i = s.NowPlayingItem, ps = s.PlayState || {};
  const title = (i.SeriesName ? `${i.SeriesName} S${i.ParentIndexNumber}E${i.IndexNumber} ` : "") + i.Name;
  return {id: i.Id, title, position: (ps.PositionTicks || 0) / 1e7, duration: (i.RunTimeTicks || 0) / 1e7,
          paused: !!ps.IsPaused, live: false, item: i};
}
"""


def on_row(app_id):
    """The app's home row entry, or MomentFailed: a hidden app's Moment can't start."""
    a = next((a for a in registry.home_row(settings.load()) if a.id == app_id), None)
    if not a:
        known = registry.get(app_id)
        raise MomentFailed(f"{known.name if known else app_id} isn't on the home screen, so this Moment can't start.")
    return a


def kind(app_id):
    return "youtube" if app_id == "youtube" else "jellyfin" if app_id == "jellyfin" else "streaming"


def _jellyfin_page():
    return next(iter(cdp.pages(cdp.JELLYFIN_PORT)), None) or tools.app_page("Jellyfin")


def _youtube_page():
    return next(iter(cdp.pages(cdp.YOUTUBE_PORT)), None)


def now_playing(app_id):
    """What the app plays now: {id, title, position, duration, paused, live} or None."""
    try:
        if app_id == "youtube":
            if tools.yt_native():
                st = ytnative.state()
                if st.get("page") != "player" or not st.get("videoId"):
                    return None
                return {
                    "id": st["videoId"],
                    "title": st.get("title") or "",
                    "position": st.get("position") or 0,
                    "duration": st.get("duration") or 0,
                    "paused": bool(st.get("paused")),
                    "live": bool(st.get("live")),
                }
            p = _youtube_page()
            r = p and cdp.call(p, tools.MEDIA_JS, "status", None, timeout=4)
            if not r or not r.get("youtube"):
                return None
            return {
                "id": r["youtube"],
                "title": re.sub(r"\s+-\s+YouTube$", "", r.get("title") or ""),
                "position": r["time"] or 0,
                "duration": r["duration"] or 0,
                "paused": bool(r["paused"]),
                "live": False,
            }
        if app_id == "jellyfin":
            if not settings.get("media.jellyfin.url"):
                return None
            p = _jellyfin_page()
            return p and cdp.call(p, JF_NOW_JS, timeout=6)
        site = streaming.site_of_app(app_id)
        if not site or not appctl.running(site):
            return None
        st = appctl.call(site, {"op": "state"}, timeout=3)
        if st.get("page") != "player" or not st.get("id"):
            return None
        title = " ".join(x for x in (st.get("series"), st.get("episode")) if x)
        title = (
            f"{title}: {st.get('title')}"
            if title and st.get("title") and st.get("title") != st.get("series")
            else title or st.get("title") or ""
        )
        return {
            "id": str(st["id"]),
            "title": title,
            "position": st.get("position") or 0,
            "duration": st.get("duration") or 0,
            "paused": bool(st.get("paused")),
            "live": bool(st.get("live")),
        }
    except Exception:  # noqa: BLE001 - an app that's starting or gone plays nothing
        return None


def target_of(app_id, playing):
    if app_id == "youtube":
        return f"video:{playing['id']}"
    if app_id == "jellyfin":
        return playing["id"]
    return f"play:{playing['id']}"


def plays(m, playing):
    """Whether what plays is this Moment."""
    if not playing:
        return False
    if m["app"] == "jellyfin":
        return playing["id"].replace("-", "").lower() == m["target"].replace("-", "").lower()
    return target_of(m["app"], playing) == m["target"]


def _youtube_title(vid):
    """A YouTube video's title (YouTube's public oEmbed), "" if it can't be had: the app has none
    for a video opened by its id."""
    m = re.match(r"“(.*)” by ", tools.yt_title(vid))
    return m.group(1) if m else ""


def art_of(app_id, playing):
    if app_id == "youtube":
        return f"https://i.ytimg.com/vi/{playing['id']}/hqdefault.jpg"
    if app_id == "jellyfin" and playing.get("item"):
        from couchbox import ontv

        return ontv.jellyfin_art(playing["item"], settings.get("media.jellyfin.url"), width=800)[0]
    return ""


def media(app_id, action):
    """pause / restart in the Moment's app (whether or not it's in front)."""
    try:
        if app_id == "youtube":
            if tools.yt_native():
                appctl.call(ytnative.SITE, {"op": "media", "action": action, "seconds": 0}, timeout=5)
            elif _youtube_page():
                cdp.call(_youtube_page(), tools.MEDIA_JS, action, 0, timeout=5)
        elif app_id == "jellyfin":
            p = _jellyfin_page()
            if p:
                cdp.call(p, tools.JF_MEDIA_JS, action, 0, timeout=8)
        else:
            appctl.call(streaming.site_of_app(app_id), {"op": "media", "action": action, "seconds": 0}, timeout=5)
    except Exception:  # noqa: BLE001 - it's gone: nothing to pause
        pass


def _mpv(*cmd):
    """A command to Jellyfin Desktop's player (its socket), or None when it isn't there."""
    from couchbox import playback

    try:
        sock = f"/run/user/{tools.tv_env()[0].pw_uid}/mpv-jellyfin.sock"
        if not os.path.exists(sock):
            return None
        m = playback.MpvSocket(sock, timeout=2)
    except (KeyError, OSError):
        return None
    try:
        r = m.command(*cmd)
        return True if r is None and cmd[0] == "set_property" else r
    except (OSError, ValueError):
        return None
    finally:
        try:
            m.sock.close()
        except OSError:
            pass


def open_in_app(m):
    """Open the Moment's target in its app, starting the app if it isn't running."""
    a = on_row(m["app"])
    if m["app"] == "youtube":
        vid = m["target"].split(":", 1)[1]
        if tools.yt_native():
            if not ytnative.show(m["target"], tools.raise_youtube):
                raise MomentFailed("YouTube didn't start.")
        else:
            out = tools.youtube("play", id=vid)
            if "rror" in out or "isn't" in out:
                raise MomentFailed(out)
        return
    if m["app"] == "jellyfin":
        out = tools.jellyfin("play", id=m["target"])
        if not out.startswith("playing "):
            raise MomentFailed(out)
        return
    site = streaming.site_of_app(m["app"])
    streaming.ensure(site, start=lambda: tools.open_app(a.name, wait=False))
    appctl.call(site, {"op": "open", "target": m["target"]})
    tools.raise_window(a.desktop, a.name)


# ------------------------------------------------------------------ teaching
def capture():
    """What plays now, the app in front first: {app, target, title, art}. MomentFailed if
    nothing plays that a Moment can keep."""
    front = tools.app_of_window(tools.active_window())
    first = [front.id] if getattr(front, "id", None) in moments.APPS else []
    shown = {a.id for a in registry.home_row(settings.load())}
    for app_id in first + [a for a in moments.APPS if a not in first]:
        if app_id not in shown:
            continue
        p = now_playing(app_id)
        if p and p.get("id"):
            title = p.get("title") or (_youtube_title(p["id"]) if app_id == "youtube" else "")
            return {"app": app_id, "target": target_of(app_id, p), "title": title, "art": art_of(app_id, p)}
    raise MomentFailed(
        "Nothing is playing that a Moment can remember: play something in YouTube, Jellyfin, Twitch, Nebula, Dropout or 2nd Try first."
    )


def save(ms):
    """The new list, through couchboxd (so the home screen follows), else straight to the file."""
    from couchbox import ipc

    try:
        ipc.call("settings.set", changes={moments.KEY: ms})
    except ipc.IpcError:
        settings.update({moments.KEY: ms})
        try:
            from couchbox import home

            home.build()
        except Exception:  # noqa: BLE001 - the tile shows after the next rebuild
            pass


def teach(name, volume=None, repeat=None, dark=None, leaving=None):
    """Remember what plays now as name (the options as said; taught again, a Moment keeps the
    options it had unless they're said)."""
    name = re.sub(r"\s+", " ", str(name or "")).strip().strip(".!?\"'“”").strip()
    if not name:
        raise MomentFailed("What should it be called?")
    if len(name) > 40:
        raise MomentFailed("That name is too long: up to 40 letters.")
    got = capture()
    old = next((x for x in moments.all() if moments.words(x["name"]) == moments.words(name)), None)
    m = dict(old or {}, **got, name=old["name"] if old else name[0].upper() + name[1:])
    if not old:
        m["id"] = moments.slug(name)
        lvl = get_volume()  # the box's own level (100% unless the household turns the box's sound down)
        m["volume"] = round(lvl * 100) if lvl is not None and lvl < 0.995 else 100
    for k, v in (("volume", volume), ("repeat", repeat), ("dark", dark), ("leaving", leaving)):
        if v is not None:
            m[k] = int(v) if k == "volume" else bool(v)
    try:
        ms = moments.with_moment(moments.all(), m)
    except moments.MomentError as e:
        raise MomentFailed(str(e)) from None
    save(ms)
    saved = next(x for x in ms if moments.words(x["name"]) == moments.words(m["name"]))
    return saved, bool(old)


def forget(mid):
    ms = [m for m in moments.all() if m["id"] != mid]
    if moments.active_id() == mid:
        stop()
    save(ms)


# ------------------------------------------------------------------ starting and stopping
def _dark_flag(on):
    _dark[0] = bool(on)
    try:
        if on:
            os.makedirs(os.path.dirname(DARK_FLAG), exist_ok=True)
            open(DARK_FLAG, "w").close()
        elif os.path.exists(DARK_FLAG):
            os.unlink(DARK_FLAG)
    except OSError:
        pass


def dark():
    """Whether the picture is black now (couchbox-voice-overlay draws it)."""
    return _dark[0]


def start(mid):
    """Start a Moment. Returns what happened, for the screen; MomentFailed if it couldn't."""
    m = moments.get(mid)
    if not m:
        raise MomentFailed("There's no such Moment any more.")
    with _lock:
        st = moments.read_state()
        a = st.get("active")
        if a and a.get("id") == m["id"] and plays(m, now_playing(m["app"])):
            open_in_app(m)  # (in front again)
            return f"{m['name']} is already playing."
        if a:
            _end(st, "another Moment started")
        before = get_volume()
        open_in_app(m)
        if m["volume"] < 100 and before is not None:
            set_volume(m["volume"] / 100)
        st["active"] = {
            "id": m["id"],
            "name": m["name"],
            "app": m["app"],
            "target": m["target"],
            "repeat": m["repeat"],
            "since": time.time(),
            "volume_before": before if m["volume"] < 100 else None,
            "dark_on": m["dark"],
        }
        _seen.clear()
        moments.note_started(st, m)
        moments.write_state(st)
        _dark_flag(m["dark"])
    return f"Playing {m['name']}: {moments.describe(m)}."


def _end(st, why, log=None):
    """The Moment is over: the sound level and the picture back as they were."""
    a = st.get("active")
    if not a:
        return
    if a.get("volume_before") is not None:
        set_volume(a["volume_before"])
    if a.get("app") == "jellyfin" and a.get("repeat"):
        _mpv("set_property", "loop-file", "no")
    _dark_flag(False)
    st["active"] = None
    moments.write_state(st)
    if log:
        log(f"moment {a.get('name')!r} over: {why}")


def stop():
    """Stop the Moment playing: pause it, and put the sound and the picture back."""
    with _lock:
        st = moments.read_state()
        a = st.get("active")
        if not a:
            return "No Moment is playing."
        media(a["app"], "pause")
        _end(st, "stopped")
    return f"Stopped {a['name']}. The sound and the picture are back as they were."


def wake():
    """A key was pressed while it's dark: the picture comes back (the Moment plays on). True if
    it was dark."""
    with _lock:
        st = moments.read_state()
        a = st.get("active")
        _dark_flag(False)
        if not (a and a.get("dark_on")):
            return False
        a["dark_on"] = False
        moments.write_state(st)
        return True


def status():
    a = moments.read_state().get("active")
    return {"active": a.get("id") if a else None, "name": a.get("name") if a else None, "dark": bool(a and a.get("dark_on"))}


# ------------------------------------------------------------------ keeping it going
def tick(log, now=None):
    """One look at the Moment playing: back to the start near its end (repeat), started again if
    it ended anyway, over (sound and picture back) if something else plays instead."""
    now = time.time() if now is None else now
    with _lock:
        st = moments.read_state()
        a = st.get("active")
        _dark_flag(a and a.get("dark_on"))
        if not a:
            _seen.clear()
            return
        if _seen.get("id") != a["id"]:
            _seen.clear()
            _seen["id"] = a["id"]
        m = moments.get(a["id"]) or a
        p = now_playing(a["app"])
        k = kind(a["app"])
        if plays(m, p):
            _seen.update(seen=now, position=p["position"], duration=p["duration"])
            if a.get("repeat") and not p.get("live") and p["duration"] > 30:
                looping = k == "jellyfin" and _mpv("get_property", "loop-file") in ("inf", True)
                if k == "jellyfin" and not looping and _mpv("set_property", "loop-file", "inf"):
                    log(f"moment {a['name']!r}: Jellyfin's player loops it")
                elif not looping and p["duration"] - p["position"] <= END_MARGIN[k]:
                    log(f"moment {a['name']!r}: back to the start")
                    media(a["app"], "restart")
                    _seen["position"] = 0
            return
        seen = _seen.get("seen", 0)
        if (not seen and now - a.get("since", 0) < GRACE) or now - seen < GONE:
            return  # (still starting, or a moment's gap: a page loading)
        near_end = _seen.get("duration") and _seen["duration"] - _seen.get("position", 0) <= END_MARGIN[k] + 2 * POLL + 10
        if a.get("repeat") and near_end and now - seen < 60:
            log(f"moment {a['name']!r}: it ended, starting it again")
            try:
                open_in_app(m)
            except Exception as err:  # noqa: BLE001
                log(f"moment {a['name']!r}: couldn't start it again: {err}")
            a["since"] = now
            _seen.clear()
            moments.write_state(st)
            return
        _end(st, "something else is playing" if seen else "it didn't start", log)


def watch(log):
    """The voice service's thread: tick() every POLL seconds. A Moment that was playing when the
    service stopped (an update, a restart) is picked up again, or put back if it's over."""
    with _lock:
        st = moments.read_state()
        if st.get("active"):
            st["active"]["since"] = time.time()
            moments.write_state(st)
    while True:
        try:
            tick(log)
        except Exception as err:  # noqa: BLE001 - tried again next time
            log(f"moments: {err}")
        time.sleep(POLL)
