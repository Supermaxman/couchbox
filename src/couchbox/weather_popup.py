"""The weather pop-up's rules: when rain (or snow) is about to start, or the US National Weather
Service issues a warning for the town in Settings → Time, it pops up in the camera pop-up's
corner (couchbox-frigate-popup shows both; a camera always comes first). Each shower and each
warning pops once. No Qt and no network here, so tests can drive it.

Settings (Settings → Apps and media → Weather pop-ups; weather.popup.*):
  rain              on or off: rain or snow due in the next 20 minutes
  rain_quiet        quiet hours, "22:00-07:00" ("" none): nothing pops then
  warnings          on or off: official warnings (tornado, severe thunderstorm, flood ...)
  warnings_quiet    their quiet hours

Rain comes from Open-Meteo's 15-minute steps (minutely_15: the precipitation of the 15 minutes
up to each step's time). In North America they are NOAA's RRFS model, in Central Europe ICON-D2
and AROME; elsewhere Open-Meteo interpolates its hourly forecast, so the times are rougher.
Warnings come from api.weather.gov (weather.py's alerts), only where it covers.
"""

import re
from datetime import datetime

PREFIX = "weather.popup."
STEP = 15 * 60  # Open-Meteo's minutely_15 step
LEAD = 20 * 60  # rain due within this pops
WET = 0.1  # mm in a step: it's raining (Open-Meteo's smallest amount)
LEAST = 0.2  # mm over the whole shower: less is a blip in the model
GAP = 3600  # rain again within an hour of the last ending is the same rain
LATE = 15 * 60  # a rain pop-up still worth showing (after waiting for a camera) this long after it starts
FORGET = 2 * 86400  # a popped warning is remembered this long
RAIN_SECONDS = 30  # how long each kind shows
WARNING_SECONDS = 60


def prefs(values):
    """The pop-up's settings (short keys) from settings.load()'s values."""
    return {k[len(PREFIX) :]: v for k, v in values.items() if k.startswith(PREFIX)}


def quiet(window, dt):
    """Whether the local time dt falls in quiet hours "HH:MM-HH:MM" (across midnight when the end
    is earlier than the start; "" never)."""
    m = re.fullmatch(r"(\d\d):(\d\d)-(\d\d):(\d\d)", window or "")
    if not m:
        return False
    a, b = int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4])
    t = dt.hour * 60 + dt.minute
    return a <= t < b if a <= b else t >= a or t < b


# ---------------------------------------------------------------------- rain
def rain_ahead(m15, now):
    """Open-Meteo's minutely_15 ({"time", "precipitation", "rain"}, metric) -> the next shower:
    {"raining": True} while it rains already; else {"start", "end", "snow", "openEnded"} when one
    starts within LEAD (a dry step between two wet ones doesn't end it); else None."""
    times = m15.get("time") or []
    pr = [x or 0 for x in m15.get("precipitation") or []]
    rain = [x or 0 for x in m15.get("rain") or pr]
    steps = [(t, pr[i], rain[i] if i < len(rain) else pr[i]) for i, t in enumerate(times) if i < len(pr)]
    # a step covers the 15 minutes up to its time: the first that ends after now covers now
    i = next((k for k, s in enumerate(steps) if s[0] > now), None)
    if i is None:
        return None
    if steps[i][1] >= WET or (i > 0 and steps[i - 1][1] >= WET):
        return {"raining": True}
    j = next((k for k in range(i, len(steps)) if steps[k][1] >= WET), None)
    if j is None or steps[j][0] - STEP - now > LEAD:
        return None
    last = j
    for k in range(j + 1, len(steps)):
        if steps[k][1] >= WET:
            last = k
        elif k - last > 1:
            break
    run = steps[j : last + 1]
    total = sum(s[1] for s in run)
    if total < LEAST:
        return None
    return {
        "start": steps[j][0] - STEP,
        "end": steps[last][0],
        "snow": sum(s[2] for s in run) < total / 2,
        "openEnded": last == len(steps) - 1,
    }


def lasting(seconds, open_ended=False):
    """How long it rains, as people say it: "lasting half an hour", "lasting 2 hours"."""
    m = seconds / 60
    if open_ended and m >= 180:
        return "lasting several hours"
    if m <= 20:
        return "lasting 15 minutes"
    if m <= 37:
        return "lasting half an hour"
    if m <= 52:
        return "lasting 45 minutes"
    if m <= 75:
        return "lasting an hour"
    if m <= 105:
        return "lasting an hour and a half"
    return f"lasting {round(m / 60)} hours"


def rain_text(r, now):
    """The pop-up's words for a shower: ("Rain in about 15 minutes", "Lasting an hour")."""
    what = "Snow" if r.get("snow") else "Rain"
    lead = round((r["start"] - now) / 300) * 5
    head = f"{what} starting now" if lead <= 0 else f"{what} in a few minutes" if lead <= 5 else f"{what} in about {lead} minutes"
    dur = lasting(r["end"] - max(now, r["start"]), r.get("openEnded"))
    return head, dur[0].upper() + dur[1:]


# ---------------------------------------------------------------------- warnings
def is_warning(alert):
    """The alerts worth interrupting for: warnings and emergencies (not watches, advisories or
    statements), and anything the Weather Service calls extreme."""
    return alert.get("event", "").endswith(("Warning", "Emergency")) or alert.get("severity") == "Extreme"


def until_text(ends, now, tz, clock24=False):
    """ "Until 7:45 PM" (today), "Until Sat 7:45 PM"; "" when it has no end."""
    if not ends:
        return ""
    e, n = datetime.fromtimestamp(ends, tz), datetime.fromtimestamp(now, tz)
    t = e.strftime("%H:%M") if clock24 else e.strftime("%I:%M %p").lstrip("0")
    return f"Until {t}" if e.date() == n.date() else f"Until {e.strftime('%a')} {t}"


class Tracker:
    """What has popped: the shower going on (or popped) and until when, and the warnings."""

    def __init__(self):
        self.rain_until = 0.0  # no rain pops before this: the last shower's end + GAP
        self.warned = {}  # a warning's key (and its ids) -> when it was last listed

    # rain
    def next_rain(self, m15, now):
        """A shower to pop up, or None (none due, it rains already, or it's the one that popped)."""
        r = rain_ahead(m15, now)
        if r is None:
            return None
        if r.get("raining"):
            self.rain_until = max(self.rain_until, now + GAP)
            return None
        if r["start"] <= self.rain_until:
            self.rain_until = max(self.rain_until, r["end"] + GAP)
            return None
        return r

    def rained(self, r):
        """This shower has had its turn."""
        self.rain_until = max(self.rain_until, r["end"] + GAP)

    # warnings
    def next_warnings(self, alerts, now):
        """The warnings (weather.py's parse_alerts) not popped yet, worst first. An update of one
        that popped (the same VTEC event, or one that references it) doesn't pop again."""
        out = []
        for a in alerts:
            if not is_warning(a):
                continue
            names = [a.get("key"), a.get("id"), *a.get("references", [])]
            names = [n for n in names if n]
            if any(n in self.warned for n in names):
                for n in names:
                    self.warned[n] = now
                continue
            if a.get("cancelled") or (a.get("ends") and a["ends"] < now):
                continue
            out.append(a)
        self.warned = {k: t for k, t in self.warned.items() if now - t < FORGET}
        return out

    def warned_of(self, a, now):
        for n in (a.get("key"), a.get("id"), *a.get("references", [])):
            if n:
                self.warned[n] = now
