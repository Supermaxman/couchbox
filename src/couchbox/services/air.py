"""Air quality and pollen for the Weather app and the voice assistant's weather tool.

  google      with a Google Maps Platform key (Settings → Apps → Maps; couchboxd hands it to the
              TV user's app as weather.google_key, the voice assistant reads it itself): the Air
              Quality API (currentConditions and a 96-hour forecast: the local index, e.g. the US
              EPA AQI, its main pollutant and Google's advice) and the Pollen API (forecast:lookup,
              5 days: tree, grass and weed, and the plants in season)
  open-meteo  without a key, or when Google says no: Open-Meteo's air-quality API (free, no key):
              US AQI (imperial) or European AQI (metric) with the main pollutant from its
              sub-indices, 4 days ahead; pollen only in Europe (CAMS: alder, birch, olive, grass,
              mugwort, ragweed in grains/m³). Elsewhere there's no pollen and the app hides it

Answers are cached: air quality for 30 minutes, pollen for 6 hours. Days are local dates
(YYYY-MM-DD) in the forecast's time zone, so they line up with weather.py's days.
"""

import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

OPEN_METEO = "https://air-quality-api.open-meteo.com/v1/air-quality"
GOOGLE_AQ = "https://airquality.googleapis.com/v1"
GOOGLE_POLLEN = "https://pollen.googleapis.com/v1/forecast:lookup"
TIMEOUT = (6, 20)
AIR_TTL = 30 * 60
POLLEN_TTL = 6 * 3600
FORECAST_HOURS = 96
POLLEN_DAYS = 5

POLLUTANT = {"pm25": "PM2.5", "pm10": "PM10", "o3": "Ozone", "no2": "NO₂", "so2": "SO₂", "co": "CO"}
# Open-Meteo's sub-indices -> Google's pollutant codes
SUB = {"pm2_5": "pm25", "pm10": "pm10", "ozone": "o3", "nitrogen_dioxide": "no2", "sulphur_dioxide": "so2", "carbon_monoxide": "co"}
TYPES = (("TREE", "Tree"), ("GRASS", "Grass"), ("WEED", "Weed"))
# Google's plant codes that aren't trees
PLANT_TYPE = {"GRAMINALES": "GRASS", "RAGWEED": "WEED", "MUGWORT": "WEED"}
LEVELS = ["None", "Very low", "Low", "Moderate", "High", "Very high"]  # Google's Universal Pollen Index 0-5
LEVEL_COLOR = ["#71717a", "#22c55e", "#84cc16", "#eab308", "#f97316", "#ef4444"]
# Open-Meteo's pollen (grains/m³) -> (type, plant); and where Low, Moderate, High, Very high start
OM_POLLEN = {
    "alder_pollen": ("TREE", "Alder"),
    "birch_pollen": ("TREE", "Birch"),
    "olive_pollen": ("TREE", "Olive"),
    "grass_pollen": ("GRASS", "Grasses"),
    "mugwort_pollen": ("WEED", "Mugwort"),
    "ragweed_pollen": ("WEED", "Ragweed"),
}
GRAINS = {"TREE": (1, 15, 90, 1500), "GRASS": (1, 5, 20, 200), "WEED": (1, 10, 50, 500)}


def aqi_label(value, scale):
    """(words, colour) for an AQI value on the US or European scale."""
    if value is None:
        return "", ""
    if scale == "us":
        bands = [
            (50, "Good", "#22c55e"),
            (100, "Moderate", "#eab308"),
            (150, "Unhealthy for some", "#f97316"),
            (200, "Unhealthy", "#ef4444"),
            (300, "Very unhealthy", "#a855f7"),
        ]
        worst = ("Hazardous", "#7f1d1d")
    else:
        bands = [
            (20, "Good", "#22c55e"),
            (40, "Fair", "#84cc16"),
            (60, "Moderate", "#eab308"),
            (80, "Poor", "#f97316"),
            (100, "Very poor", "#ef4444"),
        ]
        worst = ("Extremely poor", "#a855f7")
    for top, words, colour in bands:
        if value <= top:
            return words, colour
    return worst


def hex_color(c):
    """Google's {red, green, blue} (0-1, missing = 0) -> #rrggbb."""
    c = c or {}
    return "#" + "".join(f"{round(255 * float(c.get(k) or 0)):02x}" for k in ("red", "green", "blue"))


def local_date(ts, tz):
    return datetime.fromtimestamp(ts, tz).date().isoformat()


def worst_by_day(points, tz):
    """[(unix time, reading)] -> {date: the day's highest reading} (readings are dicts with "value")."""
    days = {}
    for ts, r in points:
        d = local_date(ts, tz)
        if r and (d not in days or r["value"] > days[d]["value"]):
            days[d] = r
    return days


def plants_text(t):
    return ", ".join(t["plants"][:3])


# ---------------------------------------------------------------------- Open-Meteo
def om_reading(values, scale):
    """One hour of Open-Meteo: {us_aqi, us_aqi_pm2_5, ...} -> a reading, or None."""
    pre = "us_aqi" if scale == "us" else "european_aqi"
    v = values.get(pre)
    if v is None:
        return None
    subs = {SUB[k[len(pre) + 1 :]]: x for k, x in values.items() if k.startswith(pre + "_") and k[len(pre) + 1 :] in SUB and x is not None}
    main = max(subs, key=subs.get) if subs else ""
    words, colour = aqi_label(v, scale)
    return {"value": round(v), "label": words, "color": colour, "pollutant": POLLUTANT.get(main, "")}


def om_pollen_level(kind, grains):
    if grains is None or grains < GRAINS[kind][0]:
        return 0
    return 2 + sum(grains >= g for g in GRAINS[kind][1:])


def om_pollen_day(values):
    """{alder_pollen: grains, ...} (a day's highest) -> the pollen list, or None when there's no
    pollen data for the place (Open-Meteo has it for Europe only)."""
    if all(values.get(k) is None for k in OM_POLLEN):
        return None
    out = []
    for code, name in TYPES:
        plants = sorted(
            (
                (values.get(k) or 0, plant)
                for k, (kind, plant) in OM_POLLEN.items()
                if kind == code and (values.get(k) or 0) >= GRAINS[kind][0]
            ),
            reverse=True,
        )
        level = max([om_pollen_level(code, g) for g, _ in plants] or [0])
        out.append(pollen_entry(code, name, level, bool(plants), [p for _, p in plants]))
    return out


def parse_open_meteo(raw, units, tz):
    """Open-Meteo's answer -> ({"now", "days", "source", "scale"} or None, {date: pollen} or None)."""
    scale = "us" if units == "imperial" else "eu"
    pre = "us_aqi" if scale == "us" else "european_aqi"
    now = om_reading((raw or {}).get("current") or {}, scale)
    if now is None:
        return None, None
    c = raw["current"]
    now["pm25"] = round(c["pm2_5"], 1) if c.get("pm2_5") is not None else None
    h = raw.get("hourly") or {}
    times = h.get("time") or []
    points = []
    for i, ts in enumerate(times):
        vals = {k: (h.get(k) or [None] * len(times))[i] for k in h if k.startswith(pre)}
        points.append((ts, om_reading(vals, scale)))
    air = {
        "now": now,
        "days": worst_by_day(points, tz),
        "scale": "US AQI" if scale == "us" else "European AQI",
        "source": "Open-Meteo",
    }
    pollen = {}
    for i, ts in enumerate(times):
        d = local_date(ts, tz)
        day = pollen.setdefault(d, {})
        for k in OM_POLLEN:
            v = (h.get(k) or [None] * len(times))[i]
            if v is not None:
                day[k] = max(day.get(k, 0), v)
    pollen = {d: p for d, p in ((d, om_pollen_day(v)) for d, v in pollen.items()) if p}
    return air, pollen or None


# ---------------------------------------------------------------------- Google
def g_reading(indexes, prefer_local=True):
    """Google's indexes -> a reading on the place's own index (e.g. the US EPA AQI), else the
    Universal AQI, with (scale name, reading)."""
    if not indexes:
        return "", None
    local = [x for x in indexes if x.get("code") != "uaqi"]
    x = local[0] if local and prefer_local else indexes[0]
    v = x.get("aqi")
    if v is None:
        return "", None
    main = x.get("dominantPollutant", "")
    if x.get("code") == "usa_epa":
        words, colour = aqi_label(v, "us")
        scale = "US AQI"
    else:  # another country's index, or the Universal AQI (where higher is cleaner): its own words
        words = (x.get("category") or "").replace(" air quality", "").strip().capitalize()
        colour = hex_color(x.get("color"))
        scale = x.get("displayName") or "AQI"
    return scale, {"value": round(v), "label": words, "color": colour, "pollutant": POLLUTANT.get(main, main.upper())}


def parse_google_air(current, forecast, tz):
    scale, now = g_reading((current or {}).get("indexes"))
    if now is None:
        return None
    now["advice"] = ((current.get("healthRecommendations") or {}).get("generalPopulation") or "").strip()
    pm = next((p for p in current.get("pollutants") or [] if p.get("code") == "pm25"), None)
    now["pm25"] = round(pm["concentration"]["value"], 1) if pm and pm.get("concentration") else None
    points = []
    for h in (forecast or {}).get("hourlyForecasts") or []:
        try:
            ts = datetime.strptime(h["dateTime"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC).timestamp()
        except (KeyError, ValueError):
            continue
        points.append((ts, g_reading(h.get("indexes"))[1]))
    return {"now": now, "days": worst_by_day(points, tz), "scale": scale, "source": "Google"}


def pollen_entry(code, name, level, in_season, plants):
    return {
        "code": code,
        "type": name,
        "value": level,
        "level": LEVELS[level],
        "color": LEVEL_COLOR[level],
        "inSeason": in_season,
        "plants": plants,
    }


def parse_google_pollen(raw):
    """Google's daily pollen -> {date: [tree, grass, weed]} (types the place has), or None."""
    out = {}
    for d in (raw or {}).get("dailyInfo") or []:
        try:
            date = f"{d['date']['year']:04d}-{d['date']['month']:02d}-{d['date']['day']:02d}"
        except (KeyError, TypeError):
            continue
        types = {t.get("code"): t for t in d.get("pollenTypeInfo") or []}
        plants = {}
        for p in d.get("plantInfo") or []:
            v = (p.get("indexInfo") or {}).get("value") or 0
            if v > 0:
                plants.setdefault(PLANT_TYPE.get(p.get("code"), "TREE"), []).append((v, p.get("displayName") or ""))
        day = []
        for code, name in TYPES:
            t = types.get(code)
            if t is None:
                continue
            level = max(0, min(5, int((t.get("indexInfo") or {}).get("value") or 0)))
            names = [n for _, n in sorted(plants.get(code, []), key=lambda x: -x[0]) if n]
            day.append(pollen_entry(code, t.get("displayName") or name, level, bool(t.get("inSeason")), names))
        if day:
            out[date] = day
    return out or None


# ---------------------------------------------------------------------- fetching, with caches
class Air:
    def __init__(self, session=None, key_source=None):
        self.http = session or requests.Session()
        self.key_source = key_source or (lambda: "")
        self.cache = {}  # (what, lat, lon, units, keyed) -> (time, value)
        self.warned = set()

    def _cached(self, name, ttl, fn):
        hit = self.cache.get(name)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        value = fn()
        self.cache[name] = (time.time(), value)
        return value

    def _say(self, what, err):
        if what not in self.warned:  # once: a key without the API on is worth a line in the log
            self.warned.add(what)
            print(f"weather {what}: {err}", flush=True)

    def get(self, place, tz_name="UTC"):
        """(air, pollen) for place {lat, lon, units}: either can be None."""
        try:
            tz = ZoneInfo(tz_name or "UTC")
        except (KeyError, ValueError):
            tz = ZoneInfo("UTC")
        key = self.key_source() or ""
        spot = (round(place["lat"], 3), round(place["lon"], 3), place.get("units"), bool(key))
        free = lambda: self._cached(("om",) + spot, AIR_TTL, lambda: self.open_meteo(place, tz))  # noqa: E731
        air = pollen = None
        if key:
            air = self._cached(("gair",) + spot, AIR_TTL, lambda: self.google_air(place, tz, key))
            pollen = self._cached(("gpollen",) + spot, POLLEN_TTL, lambda: self.google_pollen(place, key))
        if air is None:
            air = free()[0]
        if pollen is None:
            pollen = free()[1]
        return air, pollen

    def open_meteo(self, place, tz):
        pre = "us_aqi" if place.get("units") == "imperial" else "european_aqi"
        subs = ",".join(f"{pre}_{k}" for k in SUB if pre == "us_aqi" or k != "carbon_monoxide")  # no European CO index
        try:
            r = self.http.get(
                OPEN_METEO,
                params={
                    "latitude": place["lat"],
                    "longitude": place["lon"],
                    "current": f"{pre},{subs},pm2_5",
                    "hourly": f"{pre},{subs}," + ",".join(OM_POLLEN),
                    "forecast_days": 5,
                    "timeformat": "unixtime",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return parse_open_meteo(r.json(), place.get("units"), tz)
        except (requests.RequestException, ValueError, KeyError, TypeError) as err:
            self._say("air quality (Open-Meteo)", err)
            return None, None

    def google_air(self, place, tz, key):
        loc = {"latitude": place["lat"], "longitude": place["lon"]}
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
        try:
            cur = self.http.post(
                f"{GOOGLE_AQ}/currentConditions:lookup",
                params={"key": key},
                json={
                    "location": loc,
                    "extraComputations": ["LOCAL_AQI", "HEALTH_RECOMMENDATIONS", "DOMINANT_POLLUTANT_CONCENTRATION"],
                    "languageCode": "en",
                },
                timeout=TIMEOUT,
            )
            cur.raise_for_status()
            fc = self.http.post(
                f"{GOOGLE_AQ}/forecast:lookup",
                params={"key": key},
                json={
                    "location": loc,
                    "period": {"startTime": fmt(now + timedelta(hours=1)), "endTime": fmt(now + timedelta(hours=FORECAST_HOURS))},
                    "extraComputations": ["LOCAL_AQI"],
                    "pageSize": FORECAST_HOURS,
                    "languageCode": "en",
                },
                timeout=TIMEOUT,
            )
            forecast = fc.json() if fc.status_code < 400 else None  # the forecast is a nicety
            return parse_google_air(cur.json(), forecast, tz)
        except (requests.RequestException, ValueError, KeyError, TypeError) as err:
            self._say("air quality (Google)", _plain(err))
            return None

    def google_pollen(self, place, key):
        try:
            r = self.http.get(
                GOOGLE_POLLEN,
                params={
                    "key": key,
                    "location.latitude": place["lat"],
                    "location.longitude": place["lon"],
                    "days": POLLEN_DAYS,
                    "plantsDescription": "false",
                    "languageCode": "en",
                },
                timeout=TIMEOUT,
            )
            r.raise_for_status()
            return parse_google_pollen(r.json())
        except (requests.RequestException, ValueError, KeyError, TypeError) as err:
            self._say("pollen (Google)", _plain(err))  # a 400 here can mean "not covered"
            return None


def _plain(err):
    """An error without the URL (it has the key in it)."""
    r = getattr(err, "response", None)
    return f"HTTP {r.status_code}" if r is not None else err.__class__.__name__


# ---------------------------------------------------------------------- what the voice assistant reads
def air_report(air, days):
    """Air quality now and the next days, for the model to answer from."""
    if not air:
        return "No air-quality reading for this place."
    n = air["now"]
    s = (
        f"Air quality now: {air['scale']} {n['value']}, {n['label'].lower()}"
        + (f" (mostly {n['pollutant']})" if n.get("pollutant") else "")
        + "."
    )
    if n.get("advice"):
        s += " " + n["advice"]
    ahead = [
        f"{d['name']} up to {air['days'][d['date']]['value']} ({air['days'][d['date']]['label'].lower()})"
        for d in days[1:5]
        if d["date"] in air["days"]
    ]
    if ahead:
        s += " Coming days: " + "; ".join(ahead) + "."
    return s + f" (Source: {air['source']}.)"


def pollen_report(pollen, days):
    """Pollen for the picked days, for the model to answer from."""
    if not pollen:
        return "No pollen information for this place."
    out = []
    for d in days:
        p = pollen.get(d["date"])
        if not p:
            continue
        parts = [
            f"{t['type'].lower()} "
            + (t["level"].lower() if t["value"] or t["inSeason"] else "out of season")
            + (f" ({plants_text(t)})" if t["plants"] and t["value"] else "")
            for t in p
        ]
        out.append(f"{d['name']} ({d['date']}) pollen: " + ", ".join(parts) + ".")
    return "\n".join(out) if out else "No pollen forecast for that day (pollen is forecast 5 days ahead at most)."
