"""Weather for the TV app (bin/couchbox-weather) and the voice assistant's weather tool.

  forecast   Open-Meteo (https://open-meteo.com, free, no key): now, 48 hours, 14 days with
             their hours, in the box's units (Settings → Time: location.*)
  air        air quality and pollen (services/air.py): Google's Air Quality and Pollen APIs with
             a Google Maps Platform key, else Open-Meteo's air-quality API (US AQI or European
             AQI; pollen in Europe only)
  alerts     the US National Weather Service (api.weather.gov, free) for places it covers;
             elsewhere there are none
  summaries  plain sentences made from the numbers ("Rain, mostly in the afternoon (80%) …"),
             for the day details, the voice assistant and the model's "today at a glance"

Times come back as Unix times (timeformat=unixtime) and are shown in the forecast's own time
zone, so a day across a DST change still lines up. Demo mode (tests, screenshots) makes up a
plausible fortnight with no network.
"""

import math
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from couchbox.services import air

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = air.OPEN_METEO
NWS_URL = "https://api.weather.gov/alerts/active"
UA = "couchbox-weather (https://github.com/Supermaxman/couchbox)"
TIMEOUT = (6, 20)
TTL = 10 * 60  # a forecast is good for this long
DAYS = 14

CURRENT = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,wind_speed_10m,"
    "wind_direction_10m,wind_gusts_10m,precipitation,uv_index,pressure_msl,visibility,cloud_cover"
)
HOURLY = (
    "temperature_2m,apparent_temperature,precipitation_probability,precipitation,weather_code,is_day,"
    "wind_speed_10m,wind_gusts_10m,wind_direction_10m,relative_humidity_2m,uv_index"
)
DAILY = (
    "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,"
    "sunrise,sunset,daylight_duration,precipitation_sum,precipitation_probability_max,snowfall_sum,"
    "wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,uv_index_max"
)

# WMO weather codes (Open-Meteo's weather_code) -> (what it is, icon). Icons with a day and a
# night look end in "-day"/"-night" (ui/weather/icons).
WMO = {
    0: ("Clear", "clear"),
    1: ("Mostly clear", "partly"),
    2: ("Partly cloudy", "partly"),
    3: ("Cloudy", "cloudy"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "sleet"),
    57: ("Freezing drizzle", "sleet"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "heavy-rain"),
    66: ("Freezing rain", "sleet"),
    67: ("Freezing rain", "sleet"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Showers", "showers"),
    81: ("Showers", "showers"),
    82: ("Heavy showers", "heavy-rain"),
    85: ("Snow showers", "snow-showers"),
    86: ("Heavy snow showers", "snow-showers"),
    95: ("Thunderstorms", "thunder"),
    96: ("Thunderstorms with hail", "hail"),
    99: ("Thunderstorms with hail", "hail"),
}
DAY_NIGHT = {"clear", "partly", "showers", "snow-showers"}
CARDINALS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


class WeatherError(Exception):
    pass


def condition(code):
    return WMO.get(int(code), ("Unknown", "cloudy"))[0]


def icon(code, day=True):
    base = WMO.get(int(code), ("", "cloudy"))[1]
    return f"{base}-{'day' if day else 'night'}" if base in DAY_NIGHT else base


def cardinal(deg):
    return CARDINALS[round((deg or 0) % 360 / 45) % 8]


def units_of(units):
    """Display units: temperature, wind, rain amounts."""
    if units == "imperial":
        return {"system": "imperial", "temp": "°F", "wind": "mph", "precip": "in", "windy": 25, "rainy": 0.02}
    return {"system": "metric", "temp": "°C", "wind": "km/h", "precip": "mm", "windy": 40, "rainy": 0.5}


aqi_label = air.aqi_label


def uv_label(uv):
    uv = uv or 0
    return "Low" if uv < 3 else "Moderate" if uv < 6 else "High" if uv < 8 else "Very high" if uv < 11 else "Extreme"


def in_nws_area(lat, lon):
    """Roughly the places the US National Weather Service issues alerts for."""
    return (
        (24 <= lat <= 50 and -125 <= lon <= -66)  # the lower 48
        or (51 <= lat <= 72 and (lon <= -129 or lon >= 172))  # Alaska
        or (18 <= lat <= 23 and -161 <= lon <= -154)  # Hawaii
        or (17 <= lat <= 19 and -68 <= lon <= -64)  # Puerto Rico, US Virgin Islands
        or (13 <= lat <= 21 and 144 <= lon <= 146)  # Guam, Northern Marianas
    )


# ---------------------------------------------------------------------- formatting
def clock(dt, clock24):
    return dt.strftime("%H:%M") if clock24 else dt.strftime("%I:%M %p").lstrip("0")


def hour_label(dt, clock24):
    return dt.strftime("%H:00") if clock24 else dt.strftime("%I %p").lstrip("0")


def day_name(d, today):
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return d.strftime("%A")


def rnd(x, places=0):
    if x is None:
        return None
    return round(x) if places == 0 else round(x, places)


def amount(x, u):
    """A rain amount as people say it: 0.3 in, 4 mm."""
    if u["system"] == "imperial":
        return f"{x:.2f}".rstrip("0").rstrip(".") + " in" if x < 1 else f"{x:.1f} in"
    return f"{x:.0f} mm" if x >= 1 else f"{x:.1f} mm"


def part_of_day(hour):
    return "overnight" if hour < 6 else "in the morning" if hour < 12 else "in the afternoon" if hour < 18 else "in the evening"


def wet_word(code):
    c = int(code)
    if c in (71, 73, 75, 77, 85, 86):
        return "snow"
    if c in (56, 57, 66, 67):
        return "freezing rain"
    if c >= 95:
        return "thunderstorms"
    return "rain"


def day_summary(d, u):
    """A few plain sentences about one day (its numbers and hours)."""
    t = u["temp"][0]
    out = [f"{d['cond']}. High {d['hi']}{t}, low {d['lo']}{t}."]
    wet = [h for h in d["hours"] if (h["rain"] or 0) >= 40]
    if d["rain"] >= 20 or d["precip"] >= u["rainy"]:
        what = "snow" if d["snow"] > 0 else wet_word(d["code"])
        # far-off days: the chance (from fewer models) can read low while the amount doesn't
        s = f"{d['rain']}% chance of {what}" if d["rain"] >= 20 else f"Some {what} at times"
        if wet and len(wet) <= 12:
            parts = []
            for h in wet:
                p = part_of_day(h["h"])
                if p not in parts:
                    parts.append(p)
            s += ", mostly " + " and ".join(parts[:2])
        elif len(wet) > 12:
            s += " through much of the day"
        if d["precip"] >= u["rainy"]:
            s += f", about {amount(d['snow'] if what == 'snow' and d['snow'] else d['precip'], u)}"
            if what == "snow" and d["snow"] and u["system"] == "metric":
                s = s.replace(" mm", " cm")
        out.append(s + ".")
    elif d["rain"] > 0:
        out.append(f"Dry, {d['rain']}% chance of a shower.")
    else:
        out.append("Dry.")
    if d["gust"] >= u["windy"]:
        out.append(f"Windy: {d['windDir']} wind up to {d['wind']} {u['wind']}, gusts to {d['gust']}.")
    elif d["wind"] >= u["windy"] * 0.6:
        out.append(f"Breezy, {d['windDir']} wind up to {d['wind']} {u['wind']}.")
    if d["uv"] >= 6:
        out.append(f"UV {uv_label(d['uv']).lower()} ({d['uv']}) around midday.")
    return " ".join(out)


def now_summary(data):
    """The weather now and the rest of today, in a sentence or two."""
    n, u, today = data["now"], data["units"], data["days"][0]
    t = u["temp"][0]
    s = f"Now {n['temp']}{t} and {n['cond'].lower()} in {data['place']['name'] or 'your area'}"
    if abs(n["feels"] - n["temp"]) >= 3:
        s += f", feels like {n['feels']}{t}"
    s += ". Today: " + day_summary(today, u)
    rest = [h for h in data["hours"][:12] if (h["rain"] or 0) >= 50]
    if rest and today["rain"] < 50:
        s += f" Rain likely from about {rest[0]['hour']}."
    return s


# ---------------------------------------------------------------------- parsing
def parse(raw, place, clock24=False, air=None, alerts=None, now=None, pollen=None):
    """Open-Meteo's answer (unixtime) -> what the app shows. air and pollen: air.py's (each day
    gets its own reading and pollen; "aqi" is the reading now)."""
    u = units_of(place.get("units", "metric"))
    tz = ZoneInfo(raw.get("timezone") or "UTC")
    now = now or time.time()
    local = lambda ts: datetime.fromtimestamp(ts, tz)  # noqa: E731
    today = local(now).date()

    hr = raw["hourly"]
    hours = []
    for i, ts in enumerate(hr["time"]):
        dt = local(ts)
        g = lambda k: (hr.get(k) or [None] * len(hr["time"]))[i]  # noqa: E731
        code = g("weather_code") or 0
        hours.append(
            {
                "t": ts,
                "date": dt.date().isoformat(),
                "h": dt.hour,
                "hour": hour_label(dt, clock24),
                "temp": rnd(g("temperature_2m")),
                "feels": rnd(g("apparent_temperature")),
                "code": code,
                "icon": icon(code, bool(g("is_day"))),
                "cond": condition(code),
                "rain": rnd(g("precipitation_probability")) or 0,
                "precip": round(g("precipitation") or 0, 2),
                "wind": rnd(g("wind_speed_10m")) or 0,
                "gust": rnd(g("wind_gusts_10m")) or 0,
                "windDir": cardinal(g("wind_direction_10m")),
                "humidity": rnd(g("relative_humidity_2m")),
                "uv": rnd(g("uv_index"), 1) or 0,
            }
        )

    dl = raw["daily"]
    days = []
    for i, ts in enumerate(dl["time"]):
        d = local(ts + 12 * 3600).date()  # noon: clear of DST shifts at midnight
        g = lambda k: (dl.get(k) or [None] * len(dl["time"]))[i]  # noqa: E731
        code = g("weather_code") or 0
        rise, sets = g("sunrise"), g("sunset")
        day = {
            "date": d.isoformat(),
            "name": day_name(d, today),
            "short": "Today" if d == today else d.strftime("%a"),
            "label": d.strftime("%b %-d"),
            "long": d.strftime("%A, %B %-d"),
            "code": code,
            "icon": icon(code, True),
            "cond": condition(code),
            "hi": rnd(g("temperature_2m_max")),
            "lo": rnd(g("temperature_2m_min")),
            "feelsHi": rnd(g("apparent_temperature_max")),
            "feelsLo": rnd(g("apparent_temperature_min")),
            "rain": rnd(g("precipitation_probability_max")) or 0,
            "precip": round(g("precipitation_sum") or 0, 2),
            "snow": round(g("snowfall_sum") or 0, 2),
            "wind": rnd(g("wind_speed_10m_max")) or 0,
            "gust": rnd(g("wind_gusts_10m_max")) or 0,
            "windDir": cardinal(g("wind_direction_10m_dominant")),
            "uv": rnd(g("uv_index_max"), 1) or 0,
            "sunrise": clock(local(rise), clock24) if rise else "",
            "sunset": clock(local(sets), clock24) if sets else "",
            "daylight": round((g("daylight_duration") or 0) / 3600, 1),
            "hours": [h for h in hours if h["date"] == d.isoformat()],
        }
        day["summary"] = day_summary(day, u)
        days.append(day)
    days = [d for d in days if d["date"] >= today.isoformat()] or days

    c = raw.get("current") or {}
    code = c.get("weather_code") or 0
    vis = c.get("visibility")
    data = {
        "place": {"name": place.get("name", ""), "lat": place.get("lat"), "lon": place.get("lon")},
        "units": u,
        "updated": now,
        "updatedText": clock(local(now), clock24),
        "now": {
            "temp": rnd(c.get("temperature_2m")),
            "feels": rnd(c.get("apparent_temperature")),
            "code": code,
            "icon": icon(code, bool(c.get("is_day", 1))),
            "cond": condition(code),
            "day": bool(c.get("is_day", 1)),
            "humidity": rnd(c.get("relative_humidity_2m")),
            "wind": rnd(c.get("wind_speed_10m")) or 0,
            "gust": rnd(c.get("wind_gusts_10m")) or 0,
            "windDir": cardinal(c.get("wind_direction_10m")),
            "precip": round(c.get("precipitation") or 0, 2),
            "uv": rnd(c.get("uv_index"), 1) or 0,
            "uvLabel": uv_label(c.get("uv_index")),
            "pressure": rnd(c.get("pressure_msl")),
            "cloud": rnd(c.get("cloud_cover")),
            # visibility comes in feet (imperial) or metres
            "visibility": (rnd(vis / 5280, 1) if u["system"] == "imperial" else rnd(vis / 1000, 1)) if vis is not None else None,
            "visUnit": "mi" if u["system"] == "imperial" else "km",
        },
        "hours": [dict(h) for h in hours if h["t"] > now - 3600][:48],  # copies: the first says "Now"
        "days": days[:DAYS],
        "aqi": dict(air["now"], scale=air["scale"], source=air["source"]) if air else None,
        "air": air or None,
        "pollen": pollen or None,
        "alerts": alerts or [],
    }
    for d in data["days"]:
        d["aqi"] = (air or {}).get("days", {}).get(d["date"])
        d["pollen"] = (pollen or {}).get(d["date"])
    if data["hours"]:
        data["hours"][0]["hour"] = "Now"
    return data


def parse_alerts(raw, clock24=False):
    out = []
    order = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}
    for f in (raw or {}).get("features") or []:
        p = f.get("properties") or {}
        if p.get("status") not in (None, "Actual") or p.get("messageType") == "Cancel":
            continue
        ends = p.get("ends") or p.get("expires") or ""
        until = ""
        if ends:
            try:
                e = datetime.fromisoformat(ends)
                until = e.strftime("%a ") + clock(e, clock24)
            except ValueError:
                pass
        out.append(
            {
                "event": p.get("event", "Weather alert"),
                "severity": p.get("severity", ""),
                "headline": p.get("headline", ""),
                "description": re.sub(r"(?<!\n)\n(?!\n)", " ", (p.get("description") or "").strip()),
                "instruction": re.sub(r"(?<!\n)\n(?!\n)", " ", (p.get("instruction") or "").strip()),
                "until": until,
                "sender": p.get("senderName", ""),
                "color": "#ef4444" if p.get("severity") in ("Extreme", "Severe") else "#f59e0b",
            }
        )
    out.sort(key=lambda a: order.get(a["severity"], 9))
    return out


# ---------------------------------------------------------------------- the service
class Weather:
    def __init__(self, demo=False, session=None, key_source=None):
        """key_source(): the Google Maps Platform key or "" (air quality and pollen)."""
        self.demo = demo
        self.http = session or requests.Session()
        self.http.headers["User-Agent"] = UA
        self.airs = air.Air(self.http, key_source)
        self.cache = {}  # (lat, lon, units, clock24) -> (time, data)

    def get(self, place, clock24=False, force=False):
        """The forecast for place {name, lat, lon, units}: cached for TTL."""
        if not place or place.get("lat") is None:
            raise WeatherError("Set your town in Settings → Time first.")
        key = (round(place["lat"], 3), round(place["lon"], 3), place.get("units"), clock24)
        hit = self.cache.get(key)
        if hit and not force and time.time() - hit[0] < TTL:
            return hit[1]
        data = demo_forecast(place, clock24) if self.demo else self.fetch(place, clock24)
        data["place"]["name"] = place.get("name", "")
        self.cache[key] = (time.time(), data)
        return data

    def fetch(self, place, clock24=False):
        units = place.get("units", "metric")
        params = {
            "latitude": place["lat"],
            "longitude": place["lon"],
            "current": CURRENT,
            "hourly": HOURLY,
            "daily": DAILY,
            "timezone": "auto",
            "timeformat": "unixtime",
            "forecast_days": DAYS,
        }
        if units == "imperial":
            params.update(temperature_unit="fahrenheit", wind_speed_unit="mph", precipitation_unit="inch")
        try:
            r = self.http.get(FORECAST_URL, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            raw = r.json()
        except (requests.RequestException, ValueError) as err:
            raise WeatherError("The forecast service isn't answering. Check the connection.") from err
        aq, pollen = self.airs.get(place, raw.get("timezone"))
        return parse(raw, place, clock24, air=aq, pollen=pollen, alerts=self.alerts(place, clock24))

    def alerts(self, place, clock24=False):
        if not in_nws_area(place["lat"], place["lon"]):
            return []
        try:
            r = self.http.get(
                NWS_URL,
                params={"point": f"{place['lat']:.4f},{place['lon']:.4f}"},
                headers={"Accept": "application/geo+json"},
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return parse_alerts(r.json(), clock24)
        except (requests.RequestException, ValueError):
            return []


def place_from_settings(s=None):
    """{name, lat, lon, units} from Settings → Time, or None when no town is set."""
    from couchbox import settings

    s = s or settings.load()
    if not s["location.name"] and not (s["location.lat"] or s["location.lon"]):
        return None
    d = settings.derived(s)
    return {"name": s["location.name"], "lat": s["location.lat"], "lon": s["location.lon"], "units": d["units"], "clock24": d["clock24"]}


# ---------------------------------------------------------------------- the voice assistant
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def pick_days(days, spec):
    """The forecast days a spoken day means: today, tonight, tomorrow, a weekday, the weekend,
    the week, or a date (2026-10-31)."""
    s = (spec or "today").strip().lower()
    if s in ("today", "tonight", "now", ""):
        return days[:1]
    if s == "tomorrow":
        return days[1:2]
    if "weekend" in s:
        groups = []  # Saturday + Sunday pairs (just Sunday if that's today)
        for d in days:
            if date.fromisoformat(d["date"]).weekday() < 5:
                continue
            if groups and (date.fromisoformat(d["date"]) - date.fromisoformat(groups[-1][-1]["date"])).days == 1:
                groups[-1].append(d)
            else:
                groups.append([d])
        pick = 1 if "next" in s and len(groups) > 1 else 0
        return groups[pick] if groups else []
    if s in ("week", "this week", "next 7 days", "7 days"):
        return days[:7]
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        return [d for d in days if d["date"] == m.group(0)]
    for i, name in enumerate(WEEKDAYS):
        if name in s or s == name[:3]:
            hits = [d for d in days if date.fromisoformat(d["date"]).weekday() == i]
            if "next" in s and len(hits) > 1 and hits[0]["name"] in ("Today", "Tomorrow"):
                return hits[1:2]
            return hits[:1]
    return []


def voice_report(data, action, day=None):
    """What the model answers from (it does the talking)."""
    u = data["units"]
    t = u["temp"][0]
    head = f"Weather for {data['place']['name'] or 'this TV'} (units: {u['temp']}, {u['wind']}, {u['precip']})."
    alerts = "".join(f" ALERT: {a['event']}" + (f" until {a['until']}" if a["until"] else "") + "." for a in data["alerts"])
    if action == "air":
        return head + alerts + " " + air.air_report(data.get("air"), data["days"])
    if action == "pollen":
        picked = pick_days(data["days"], day) if day else data["days"][:1]
        return head + " " + air.pollen_report(data.get("pollen"), picked)
    if action == "week":
        lines = [
            f"{d['name']} {d['date']}: {d['cond']}, {d['hi']}{t}/{d['lo']}{t}, rain {d['rain']}%"
            + (f" ({amount(d['precip'], u)})" if d["precip"] >= u["rainy"] else "")
            for d in data["days"]
        ]
        return head + alerts + "\n" + "\n".join(lines)
    if action == "now" or not day:
        return head + alerts + " " + now_summary(data)
    picked = pick_days(data["days"], day)
    if not picked:
        last = data["days"][-1]
        return head + f" No forecast for {day!r}: the forecast runs to {last['name']} {last['date']}."
    out = [head + alerts]
    for d in picked:
        wet = ", ".join(f"{h['hour']} {h['rain']}%" for h in d["hours"] if h["rain"] >= 30)
        out.append(f"{d['name']} ({d['date']}): {d['summary']}" + (f" Rain chances by hour: {wet}." if wet else ""))
    return "\n".join(out)


def glance_facts(data):
    """What the model's "today at a glance" line is made from (also its cache key, so it's
    rounded to change only when the forecast does)."""
    u, d = data["units"], data["days"][0]
    t = u["temp"][0]
    hours = ", ".join(
        f"{h['hour']} {h['temp']}{t} {h['cond'].lower()}" + (f" rain {h['rain']}%" if h["rain"] >= 20 else "")
        for h in data["hours"][1:13:2]
    )
    alerts = "; ".join(a["event"] + (f" until {a['until']}" if a["until"] else "") for a in data["alerts"])
    return (
        f"Place: {data['place']['name']}. Units: {u['temp']}, {u['wind']}. Now: {data['now']['temp']}{t}, {data['now']['cond'].lower()}, "
        f"feels like {data['now']['feels']}{t}. Today: {d['summary']} Coming hours: {hours}."
        + (f" Alerts: {alerts}." if alerts else "")
        + (f" Tomorrow: {data['days'][1]['summary']}" if len(data["days"]) > 1 else "")
        + (f" Air: {data['aqi']['scale']} {data['aqi']['value']} ({data['aqi']['label'].lower()})." if data.get("aqi") else "")
        + (
            " Pollen today: " + ", ".join(f"{t['type'].lower()} {t['level'].lower()}" for t in d["pollen"]) + "."
            if d.get("pollen") and any(t["value"] >= 3 for t in d["pollen"])
            else ""
        )
    )


# ---------------------------------------------------------------------- demo
def demo_forecast(place, clock24=False):
    """A made-up fortnight in the raw API's shape (so parse() is exercised too)."""
    imperial = place.get("units") == "imperial"
    tz = ZoneInfo("America/Los_Angeles")
    now = time.time()
    start = datetime.fromtimestamp(now, tz).replace(hour=0, minute=0, second=0, microsecond=0)
    codes = [3, 61, 80, 2, 0, 1, 63, 95, 3, 71, 2, 45, 0, 81]
    hourly = {
        k: []
        for k in (
            "time",
            "temperature_2m",
            "apparent_temperature",
            "precipitation_probability",
            "precipitation",
            "weather_code",
            "is_day",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "relative_humidity_2m",
            "uv_index",
        )
    }
    daily = {k: [] for k in DAILY.split(",")}
    daily["time"] = []
    for d in range(DAYS):
        base = 12 + 4 * math.sin(d / 2.3) - (6 if codes[d] == 71 else 0)
        rainy = codes[d] >= 51
        temps, probs, amts = [], [], []
        for h in range(24):
            ts = (start + timedelta(days=d, hours=h)).timestamp()
            temp = base + 5 * math.sin((h - 9) / 24 * 2 * math.pi)
            prob = (70 + 25 * math.sin(h / 4)) if rainy and 10 <= h <= 20 else (15 if rainy else 0)
            amt = 0.8 if prob > 60 else 0.0
            code = codes[d] if 9 <= h <= 21 else (codes[d] if rainy else 1)
            temps.append(temp)
            probs.append(prob)
            amts.append(amt)
            for k, v in (
                ("time", int(ts)),
                ("temperature_2m", temp),
                ("apparent_temperature", temp - 2),
                ("precipitation_probability", round(max(0, prob))),
                ("precipitation", amt),
                ("weather_code", code),
                ("is_day", 1 if 7 <= h <= 18 else 0),
                ("wind_speed_10m", 8 + 6 * math.sin(h / 5 + d)),
                ("wind_gusts_10m", 18 + 12 * math.sin(h / 5 + d)),
                ("wind_direction_10m", 200 + 10 * d),
                ("relative_humidity_2m", 70 + (20 if rainy else 0)),
                ("uv_index", max(0, 4 * math.sin((h - 7) / 11 * math.pi))),
            ):
                hourly[k].append(v)
        day0 = start + timedelta(days=d)
        for k, v in (
            ("time", int(day0.timestamp())),
            ("weather_code", codes[d]),
            ("temperature_2m_max", max(temps)),
            ("temperature_2m_min", min(temps)),
            ("apparent_temperature_max", max(temps) - 1),
            ("apparent_temperature_min", min(temps) - 3),
            ("sunrise", int((day0 + timedelta(hours=7, minutes=38)).timestamp())),
            ("sunset", int((day0 + timedelta(hours=18, minutes=4)).timestamp())),
            ("daylight_duration", 37560),
            ("precipitation_sum", sum(amts)),
            ("precipitation_probability_max", round(max(probs))),
            ("snowfall_sum", 2.1 if codes[d] == 71 else 0),
            ("wind_speed_10m_max", 14 + 3 * (d % 4)),
            ("wind_gusts_10m_max", 28 + 8 * (d % 3)),
            ("wind_direction_10m_dominant", 210),
            ("uv_index_max", 3.2),
        ):
            daily[k].append(v)
    if imperial:
        f = lambda c: c * 9 / 5 + 32  # noqa: E731
        for k in ("temperature_2m", "apparent_temperature"):
            hourly[k] = [f(x) for x in hourly[k]]
        for k in ("temperature_2m_max", "temperature_2m_min", "apparent_temperature_max", "apparent_temperature_min"):
            daily[k] = [f(x) for x in daily[k]]
        for k in ("wind_speed_10m", "wind_gusts_10m"):
            hourly[k] = [x * 0.621 for x in hourly[k]]
        for k in ("wind_speed_10m_max", "wind_gusts_10m_max"):
            daily[k] = [x * 0.621 for x in daily[k]]
        hourly["precipitation"] = [x / 25.4 for x in hourly["precipitation"]]
        daily["precipitation_sum"] = [x / 25.4 for x in daily["precipitation_sum"]]
    i = min(range(len(hourly["time"])), key=lambda j: abs(hourly["time"][j] - now))
    raw = {
        "timezone": "America/Los_Angeles",
        "current": {
            "temperature_2m": hourly["temperature_2m"][i],
            "apparent_temperature": hourly["apparent_temperature"][i],
            "relative_humidity_2m": 78,
            "weather_code": 3,
            "is_day": hourly["is_day"][i],
            "wind_speed_10m": 9,
            "wind_direction_10m": 210,
            "wind_gusts_10m": 21,
            "precipitation": 0,
            "uv_index": 1.4,
            "pressure_msl": 1016,
            "visibility": 50000 if imperial else 16000,
            "cloud_cover": 90,
        },
        "hourly": hourly,
        "daily": daily,
    }
    dates = [(start + timedelta(days=i)).date().isoformat() for i in range(5)]
    reading = lambda v, p: dict(zip(("label", "color"), air.aqi_label(v, "us"), strict=False), value=v, pollutant=p)  # noqa: E731
    aq = {
        "now": dict(reading(38, "PM2.5"), pm25=4.1, advice="With this level of air quality, you have no limitations. Enjoy the outdoors!"),
        "days": dict(
            zip(
                dates,
                [reading(44, "PM2.5"), reading(57, "Ozone"), reading(71, "Ozone"), reading(35, "PM2.5"), reading(29, "PM2.5")],
                strict=False,
            )
        ),
        "scale": "US AQI" if imperial else "European AQI",
        "source": "Google",
    }
    levels = [(4, 1, 0), (3, 2, 0), (2, 2, 1), (4, 3, 1), (1, 0, 0)]  # tree, grass, weed a day
    pollen = {
        d: [
            air.pollen_entry(code, name, lv, lv > 0, plants if lv else [])
            for (code, name), lv, plants in zip(air.TYPES, lvs, (["Birch", "Oak", "Alder"], ["Grasses"], ["Ragweed"]), strict=True)
        ]
        for d, lvs in zip(dates, levels, strict=True)
    }
    alerts = [
        {
            "event": "Wind Advisory",
            "severity": "Moderate",
            "headline": "Wind Advisory until Tuesday 4 PM",
            "description": "South winds 25 to 35 mph with gusts up to 50 mph expected. Gusty winds will blow around "
            "unsecured objects and could bring down tree limbs.",
            "instruction": "Use extra caution when driving, especially if operating a high profile vehicle.",
            "until": "Tue 4 PM",
            "sender": "National Weather Service",
            "color": "#f59e0b",
        }
    ]
    return parse(raw, place, clock24, air=aq, pollen=pollen, alerts=alerts, now=now)
