"""Maps for the couchbox TV app: saved places, search, directions, ETAs and when to leave.

  providers  google  Google Maps Platform, when Settings → Apps → Maps has an API key (couchboxd
                     hands it to the TV user's app: maps.google_key). Places API (New) text search,
                     Routes API computeRoutes (traffic-aware ETAs, alternatives, transit, arrival
                     times) and Map Tiles API 2D roadmap tiles in a dark style
             free    no key: Photon (photon.komoot.io) for search; the FOSSGIS OSRM servers
                     (routing.openstreetmap.de) for car, bike and foot routes (no traffic, no
                     transit); OpenStreetMap's standard tiles. Light use only: an identifying
                     User-Agent, nothing fetched ahead, tiles cached on the box for a week
  places     ~/.local/share/couchbox-maps/places.json: saved places (Home, Work, ...) and the
             recent destinations. Home starts at Settings → Time → Location (a city) until the
             real address is set
  relay      127.0.0.1:<port>/<secret>/tile/<z>/<x>/<y>: map tiles for the QML, from the cache or
             the provider (it adds the key or the User-Agent, so the QML handles neither)

Demo mode (tests, screenshots) answers with made-up places and routes, drawn tiles and no network.
"""

import http.server
import json
import math
import os
import re
import secrets
import socketserver
import struct
import threading
import time
import zlib
from pathlib import Path

import requests

from couchbox import __version__

TIMEOUT = (6, 20)
UA = f"Couchbox-Maps/{__version__} (+https://github.com/Supermaxman/couchbox)"
PHOTON = "https://photon.komoot.io"
OSRM = "https://routing.openstreetmap.de"
OSM_TILES = "https://tile.openstreetmap.org"
PLACES_API = "https://places.googleapis.com/v1"
ROUTES_API = "https://routes.googleapis.com/directions/v2:computeRoutes"
TILE_API = "https://tile.googleapis.com"
MODES = ("drive", "transit", "walk", "bike")
OSRM_PROFILE = {"drive": "routed-car", "bike": "routed-bike", "walk": "routed-foot"}
GOOGLE_MODE = {"drive": "DRIVE", "transit": "TRANSIT", "walk": "WALK", "bike": "BICYCLE"}
TILE_DAYS = 7
TILE_CACHE_MB = 150
ETA_TTL = 240  # the places board's drive times, seconds
RECENT = 12

# Google's map in the dark, close to its own night look (Map Tiles API "styles")
DARK_STYLE = [
    {"stylers": [{"saturation": -20}]},
    {"elementType": "geometry", "stylers": [{"color": "#1f2430"}]},
    {"elementType": "labels.text.fill", "stylers": [{"color": "#9aa3b5"}]},
    {"elementType": "labels.text.stroke", "stylers": [{"color": "#151821"}]},
    {"featureType": "poi", "elementType": "geometry", "stylers": [{"color": "#252b38"}]},
    {"featureType": "poi.park", "elementType": "geometry", "stylers": [{"color": "#1d3328"}]},
    {"featureType": "road", "elementType": "geometry", "stylers": [{"color": "#3a4152"}]},
    {"featureType": "road.highway", "elementType": "geometry", "stylers": [{"color": "#5a5f73"}]},
    {"featureType": "road", "elementType": "labels.text.fill", "stylers": [{"color": "#b8bfcc"}]},
    {"featureType": "transit", "elementType": "geometry", "stylers": [{"color": "#2b3242"}]},
    {"featureType": "water", "elementType": "geometry", "stylers": [{"color": "#0f2236"}]},
    {"featureType": "water", "elementType": "labels.text.fill", "stylers": [{"color": "#4f6b8a"}]},
]


class MapsError(Exception):
    """Something to show the user as is."""


# ------------------------------------------------------------------ geometry and text
def decode_polyline(s, precision=5):
    """Google's (and OSRM's) encoded polyline -> [[lat, lon], ...]."""
    out, i, lat, lon, f = [], 0, 0, 0, 10.0**precision
    while i < len(s):
        vals = []
        for _ in range(2):
            shift = result = 0
            while True:
                b = ord(s[i]) - 63
                i += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            vals.append(~(result >> 1) if result & 1 else result >> 1)
        lat += vals[0]
        lon += vals[1]
        out.append([lat / f, lon / f])
    return out


def thin(points, keep=400):
    """At most `keep` points for drawing (first and last kept)."""
    if len(points) <= keep:
        return points
    step = (len(points) - 1) / (keep - 1)
    return [points[round(i * step)] for i in range(keep)]


def distance_m(a, b):
    """Great-circle metres between (lat, lon) pairs."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def bbox(points):
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return {"south": min(lats), "west": min(lons), "north": max(lats), "east": max(lons)}


def dist_text(m, units):
    if units == "imperial":
        mi = m / 1609.344
        if mi < 0.2:
            return f"{round(m * 3.28084 / 50) * 50:.0f} ft"
        return f"{mi:.1f} mi" if mi < 10 else f"{mi:.0f} mi"
    return f"{m:.0f} m" if m < 1000 else (f"{m / 1000:.1f} km" if m < 10000 else f"{m / 1000:.0f} km")


def dur_text(s):
    m = max(1, round(s / 60))
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60} min" if m % 60 else f"{m // 60} h"


def parse_seconds(v):
    """Google's "1234s" -> 1234."""
    if isinstance(v, (int, float)):
        return int(v)
    return int(float(str(v or "0").rstrip("s") or 0))


def rfc3339(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def from_rfc3339(s):
    """'2026-10-26T17:05:00Z' (or with fractions/offset) -> epoch seconds."""
    m = re.match(r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(?:\.\d+)?(Z|[+-]\d\d:\d\d)?", s or "")
    if not m:
        return 0
    y, mo, d, h, mi, se, tz = m.groups()
    t = time.mktime((int(y), int(mo), int(d), int(h), int(mi), int(se), 0, 0, 0)) - time.timezone
    if tz and tz != "Z":
        sign = 1 if tz[0] == "+" else -1
        t -= sign * (int(tz[1:3]) * 3600 + int(tz[4:6]) * 60)
    return int(t)


# OSRM steps as words ("Turn left onto Main Street") and an icon (ui/maps/icons/turn-*.svg)
def osrm_step(st):
    m = st.get("maneuver") or {}
    kind, mod = m.get("type", ""), (m.get("modifier") or "").replace(" ", "-")
    name = st.get("name") or st.get("ref") or ""
    onto = f" onto {name}" if name else ""
    side = {
        "left": "left",
        "right": "right",
        "slight-left": "slight left",
        "slight-right": "slight right",
        "sharp-left": "sharp left",
        "sharp-right": "sharp right",
        "uturn": "U-turn",
        "straight": "straight",
    }.get(mod, mod)
    if kind == "depart":
        text, icon = f"Head out{(' on ' + name) if name else ''}", "depart"
    elif kind == "arrive":
        text, icon = "Arrive" + (" (on the left)" if mod == "left" else " (on the right)" if mod == "right" else ""), "arrive"
    elif kind in ("roundabout", "rotary", "roundabout turn"):
        n = m.get("exit")
        text, icon = f"At the roundabout, take the {ordinal(n)} exit{onto}" if n else f"Go through the roundabout{onto}", "roundabout"
    elif kind == "merge":
        text, icon = f"Merge{onto}", "merge"
    elif kind in ("on ramp", "off ramp"):
        text = f"Take the ramp{' on the left' if 'left' in mod else ' on the right' if 'right' in mod else ''}{onto}"
        icon = "turn-" + ("left" if "left" in mod else "right" if "right" in mod else "straight")
    elif kind == "fork":
        text, icon = (
            f"Keep {('left' if 'left' in mod else 'right' if 'right' in mod else 'straight')} at the fork{onto}",
            ("turn-slight-left" if "left" in mod else "turn-slight-right" if "right" in mod else "turn-straight"),
        )
    elif mod == "uturn":
        text, icon = f"Make a U-turn{onto}", "uturn"
    elif kind in ("continue", "new name") or mod == "straight":
        text, icon = f"Continue{onto}" if name else "Continue straight", "turn-straight"
    elif kind == "end of road":
        text, icon = f"At the end of the road, turn {side}{onto}", "turn-" + ("left" if "left" in mod else "right")
    else:
        text, icon = (
            f"Turn {side}{onto}",
            "turn-" + (mod if mod in ("left", "right", "slight-left", "slight-right", "sharp-left", "sharp-right") else "straight"),
        )
    return text, icon.replace("sharp-", "")


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


GOOGLE_ICON = {
    "TURN_LEFT": "turn-left",
    "TURN_SHARP_LEFT": "turn-left",
    "TURN_SLIGHT_LEFT": "turn-slight-left",
    "TURN_RIGHT": "turn-right",
    "TURN_SHARP_RIGHT": "turn-right",
    "TURN_SLIGHT_RIGHT": "turn-slight-right",
    "UTURN_LEFT": "uturn",
    "UTURN_RIGHT": "uturn",
    "STRAIGHT": "turn-straight",
    "NAME_CHANGE": "turn-straight",
    "RAMP_LEFT": "turn-slight-left",
    "RAMP_RIGHT": "turn-slight-right",
    "FORK_LEFT": "turn-slight-left",
    "FORK_RIGHT": "turn-slight-right",
    "MERGE": "merge",
    "ROUNDABOUT_LEFT": "roundabout",
    "ROUNDABOUT_RIGHT": "roundabout",
    "ROUNDABOUT_CLOCKWISE": "roundabout",
    "ROUNDABOUT_COUNTERCLOCKWISE": "roundabout",
    "DEPART": "depart",
    "FERRY": "ferry",
    "FERRY_TRAIN": "ferry",
}


def traffic_level(duration, static):
    """How much traffic adds: none/light/moderate/heavy (the ETA's colour)."""
    if not static or duration <= 0:
        return ""
    extra = (duration - static) / static
    return "light" if extra < 0.1 else "moderate" if extra < 0.3 else "heavy"


# ------------------------------------------------------------------ the app's own data
def data_dir():
    return Path(os.environ.get("COUCHBOX_MAPS_DIR") or Path.home() / ".local/share/couchbox-maps")


def cache_dir():
    return Path(os.environ.get("COUCHBOX_MAPS_CACHE") or Path.home() / ".cache/couchbox-maps")


class Places:
    """Saved places and recent destinations (places.json)."""

    def __init__(self, home_default=None):
        self.file = data_dir() / "places.json"
        self.home_default = home_default or {}
        self.lock = threading.Lock()

    def _read(self):
        try:
            return json.loads(self.file.read_text())
        except (OSError, ValueError):
            return {}

    def _write(self, d):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1))
        tmp.replace(self.file)

    def all(self):
        """{"places": [...], "recent": [...]}; Home first (from Settings until it's set here)."""
        d = self._read()
        places = d.get("places") or []
        if not any(p.get("kind") == "home" for p in places) and self.home_default.get("lat"):
            h = self.home_default
            places = [
                {
                    "id": "home",
                    "kind": "home",
                    "name": "Home",
                    "address": h.get("name", ""),
                    "lat": h["lat"],
                    "lon": h["lon"],
                    "approx": True,
                }
            ] + places
        order = {"home": 0, "work": 1}
        places = sorted(places, key=lambda p: order.get(p.get("kind"), 2))
        return {"places": places, "recent": d.get("recent") or []}

    def save(self, place, kind="place", name=""):
        """Add or replace a saved place (Home and Work are one each). Returns the list."""
        with self.lock:
            d = self._read()
            places = [p for p in d.get("places") or []]
            p = {
                "name": name or place.get("name") or "Place",
                "address": place.get("address", ""),
                "lat": float(place["lat"]),
                "lon": float(place["lon"]),
                "kind": kind,
            }
            if kind in ("home", "work"):
                places = [x for x in places if x.get("kind") != kind]
                p["id"] = kind
                p["name"] = name or kind.capitalize()
            else:
                p["id"] = place.get("id") if place.get("kind") == "place" and place.get("id") else "p" + secrets.token_hex(4)
                places = [x for x in places if x.get("id") != p["id"]]
            places.append(p)
            d["places"] = places
            self._write(d)
        return self.all()

    def rename(self, pid, name):
        with self.lock:
            d = self._read()
            for p in d.get("places") or []:
                if p.get("id") == pid:
                    p["name"] = name.strip()[:40] or p["name"]
            self._write(d)
        return self.all()

    def remove(self, pid):
        with self.lock:
            d = self._read()
            d["places"] = [p for p in d.get("places") or [] if p.get("id") != pid]
            self._write(d)
        return self.all()

    def remember(self, place):
        """A destination goes to the top of Recent."""
        with self.lock:
            d = self._read()
            r = [
                x
                for x in d.get("recent") or []
                if (round(x["lat"], 5), round(x["lon"], 5)) != (round(place["lat"], 5), round(place["lon"], 5))
            ]
            r.insert(0, {k: place[k] for k in ("name", "address", "lat", "lon") if k in place})
            d["recent"] = r[:RECENT]
            self._write(d)

    def clear_recent(self):
        with self.lock:
            d = self._read()
            d["recent"] = []
            self._write(d)
        return self.all()

    def find(self, name):
        """A saved place by what it's called ("work", "the gym"), or None."""
        q = " ".join(re.sub(r"\b(the|my|our)\b", " ", (name or "").lower()).split())
        if not q:
            return None
        ps = self.all()["places"]
        for p in ps:
            if q in (p["name"].lower(), p.get("kind")):
                return p
        hits = [p for p in ps if q in p["name"].lower() or p["name"].lower() in q]
        return min(hits, key=lambda p: len(p["name"])) if hits else None


# ------------------------------------------------------------------ providers
class Free:
    """No key: Photon, FOSSGIS OSRM, OpenStreetMap tiles."""

    name = "OpenStreetMap"
    traffic = False
    modes = ("drive", "walk", "bike")
    attribution = "© OpenStreetMap contributors · routes: OSRM (FOSSGIS)"
    tile_px = 256

    def __init__(self, http):
        self.http = http

    def search(self, query, near, limit=10):
        params = {"q": query, "limit": limit, "lang": "en"}
        if near:
            params.update(lat=near[0], lon=near[1])
        r = self.http.get(f"{PHOTON}/api/", params=params, timeout=TIMEOUT)
        r.raise_for_status()
        out = []
        for f in r.json().get("features") or []:
            p = f.get("properties") or {}
            lon, lat = f["geometry"]["coordinates"][:2]
            street = " ".join(x for x in (p.get("housenumber"), p.get("street")) if x)
            name = p.get("name") or street or p.get("city") or query
            addr = ", ".join(x for x in (street if street != name else "", p.get("city") or p.get("county"), p.get("state")) if x)
            kind = (p.get("osm_value") or "").replace("_", " ").capitalize()
            out.append({"name": name, "address": addr, "lat": lat, "lon": lon, "type": kind if kind not in ("Yes", "House") else ""})
        return out

    def routes(self, a, b, mode, depart=None, arrive=None, alternatives=True):
        if mode not in OSRM_PROFILE:
            raise MapsError("Transit directions need a Google Maps key (Settings → Apps → Maps).")
        coords = f"{a['lon']:.6f},{a['lat']:.6f};{b['lon']:.6f},{b['lat']:.6f}"
        r = self.http.get(
            f"{OSRM}/{OSRM_PROFILE[mode]}/route/v1/driving/{coords}",
            params={"overview": "full", "geometries": "polyline", "steps": "true", "alternatives": "true" if alternatives else "false"},
            timeout=TIMEOUT,
        )
        if r.status_code == 400:
            raise MapsError("No route between those places.")
        r.raise_for_status()
        d = r.json()
        if d.get("code") != "Ok":
            raise MapsError(
                "No route between those places." if d.get("code") in ("NoRoute", "NoSegment") else d.get("message") or "No route."
            )
        start = depart or time.time()
        out = []
        for rt in d.get("routes") or []:
            steps = []
            for leg in rt.get("legs") or []:
                for st in leg.get("steps") or []:
                    text, icon = osrm_step(st)
                    steps.append({"text": text, "icon": icon, "distance": st.get("distance", 0), "duration": st.get("duration", 0)})
            dur = int(rt["duration"])
            out.append(
                {
                    "summary": ", ".join(x for x in (leg.get("summary") for leg in rt.get("legs") or []) if x) or "",
                    "duration": dur,
                    "static": dur,
                    "distance": int(rt["distance"]),
                    "depart": int((arrive - dur) if arrive else start),
                    "arrive": int(arrive or start + dur),
                    "points": decode_polyline(rt.get("geometry") or ""),
                    "steps": steps,
                    "transit": [],
                    "traffic": "",
                }
            )
        return out

    def tile_url(self, z, x, y):
        return f"{OSM_TILES}/{z}/{x}/{y}.png", {}


class Google:
    """Google Maps Platform with the user's key."""

    name = "Google Maps"
    traffic = True
    modes = MODES
    attribution = "Map data © Google"
    tile_px = 512

    def __init__(self, http, key):
        self.http = http
        self.key = key
        self.session = None  # Map Tiles API session: (token, expiry)
        self.lock = threading.Lock()

    def _post(self, url, body, fields):
        r = self.http.post(
            url,
            json=body,
            timeout=TIMEOUT,
            headers={"X-Goog-Api-Key": self.key, "X-Goog-FieldMask": fields, "Content-Type": "application/json"},
        )
        if r.status_code in (400, 403, 404):
            try:
                msg = r.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                msg = r.text[:200]
            if r.status_code == 403 or "API key" in msg:
                raise MapsError(f"Google refused the key: {msg}")
            raise MapsError(msg)
        r.raise_for_status()
        return r.json()

    def search(self, query, near, limit=10):
        body = {"textQuery": query, "pageSize": limit}
        if near:
            body["locationBias"] = {"circle": {"center": {"latitude": near[0], "longitude": near[1]}, "radius": 50000.0}}
        d = self._post(
            f"{PLACES_API}/places:searchText",
            body,
            "places.id,places.displayName,places.formattedAddress,places.location,places.primaryTypeDisplayName",
        )
        out = []
        for p in d.get("places") or []:
            loc = p.get("location") or {}
            out.append(
                {
                    "name": (p.get("displayName") or {}).get("text") or query,
                    "address": p.get("formattedAddress", ""),
                    "lat": loc.get("latitude"),
                    "lon": loc.get("longitude"),
                    "type": (p.get("primaryTypeDisplayName") or {}).get("text", ""),
                    "google_id": p.get("id", ""),
                }
            )
        return [p for p in out if p["lat"] is not None]

    def routes(self, a, b, mode, depart=None, arrive=None, alternatives=True):
        body = {
            "origin": {"location": {"latLng": {"latitude": a["lat"], "longitude": a["lon"]}}},
            "destination": {"location": {"latLng": {"latitude": b["lat"], "longitude": b["lon"]}}},
            "travelMode": GOOGLE_MODE[mode],
            "computeAlternativeRoutes": bool(alternatives) and mode != "transit",
            "languageCode": "en-US",
            "units": "IMPERIAL",
        }
        if mode == "drive":
            body["routingPreference"] = "TRAFFIC_AWARE"
        if arrive and mode == "transit":
            body["arrivalTime"] = rfc3339(arrive)
        elif depart and depart > time.time() + 60:
            body["departureTime"] = rfc3339(depart)
        if mode == "transit":
            body["computeAlternativeRoutes"] = True
        fields = ",".join(
            "routes." + f
            for f in (
                "duration",
                "staticDuration",
                "distanceMeters",
                "polyline.encodedPolyline",
                "description",
                "routeLabels",
                "travelAdvisory.speedReadingIntervals",
                "localizedValues",
                "legs.steps.navigationInstruction",
                "legs.steps.distanceMeters",
                "legs.steps.staticDuration",
                "legs.steps.travelMode",
                "legs.steps.transitDetails",
            )
        )
        d = self._post(ROUTES_API, body, fields)
        if not d.get("routes"):
            raise MapsError("Google found no route between those places.")
        now = depart or time.time()
        out = []
        for rt in d["routes"]:
            dur = parse_seconds(rt.get("duration"))
            static = parse_seconds(rt.get("staticDuration")) or dur
            steps, transit = [], []
            for leg in rt.get("legs") or []:
                for st in leg.get("steps") or []:
                    td = st.get("transitDetails")
                    if td:
                        line = td.get("transitLine") or {}
                        sd = td.get("stopDetails") or {}
                        lt = td.get("localizedValues") or {}
                        leg_t = {
                            "line": line.get("nameShort") or line.get("name") or "",
                            "name": line.get("name") or "",
                            "vehicle": ((line.get("vehicle") or {}).get("type") or "BUS").lower(),
                            "color": line.get("color") or "",
                            "headsign": td.get("headsign", ""),
                            "from": (sd.get("departureStop") or {}).get("name", ""),
                            "to": (sd.get("arrivalStop") or {}).get("name", ""),
                            "departure": from_rfc3339(sd.get("departureTime")),
                            "arrival": from_rfc3339(sd.get("arrivalTime")),
                            "stops": td.get("stopCount", 0),
                            "departure_text": ((lt.get("departureTime") or {}).get("time") or {}).get("text", ""),
                        }
                        transit.append(leg_t)
                        text = f"{leg_t['vehicle'].capitalize()} {leg_t['line']} toward {leg_t['headsign']}".strip()
                        text += f" · {leg_t['stops']} stops to {leg_t['to']}" if leg_t["to"] else ""
                        steps.append(
                            {
                                "text": text,
                                "icon": "transit",
                                "distance": st.get("distanceMeters", 0),
                                "duration": parse_seconds(st.get("staticDuration")),
                                "transit": leg_t,
                            }
                        )
                        continue
                    ni = st.get("navigationInstruction") or {}
                    text = (ni.get("instructions") or "").replace("\n", " · ")
                    if not text:
                        continue
                    icon = (
                        "walk"
                        if st.get("travelMode") == "WALK" and mode == "transit"
                        else GOOGLE_ICON.get(ni.get("maneuver", ""), "turn-straight")
                    )
                    steps.append(
                        {
                            "text": text,
                            "icon": icon,
                            "distance": st.get("distanceMeters", 0),
                            "duration": parse_seconds(st.get("staticDuration")),
                        }
                    )
            if transit:
                dep = transit[0]["departure"]
                walk_before = sum(s["duration"] for s in steps[: next(i for i, s in enumerate(steps) if s.get("transit"))])
                start = dep - walk_before if dep else now
                end = start + dur
            elif arrive:
                start, end = arrive - dur, arrive
            else:
                start, end = now, now + dur
            out.append(
                {
                    "summary": rt.get("description", ""),
                    "labels": rt.get("routeLabels") or [],
                    "duration": dur,
                    "static": static,
                    "distance": rt.get("distanceMeters", 0),
                    "depart": int(start),
                    "arrive": int(end),
                    "points": decode_polyline((rt.get("polyline") or {}).get("encodedPolyline", "")),
                    "steps": steps,
                    "transit": transit,
                    "traffic": traffic_level(dur, static) if mode == "drive" else "",
                }
            )
        return out

    def _session(self):
        with self.lock:
            if self.session and self.session[1] > time.time() + 3600:
                return self.session[0]
            r = self.http.post(
                f"{TILE_API}/v1/createSession",
                params={"key": self.key},
                timeout=TIMEOUT,
                json={
                    "mapType": "roadmap",
                    "language": "en-US",
                    "region": "US",
                    "scale": "scaleFactor2x",
                    "highDpi": True,
                    "styles": DARK_STYLE,
                },
            )
            if r.status_code >= 400:
                raise MapsError("Google map tiles: " + r.text[:160])
            d = r.json()
            self.session = (d["session"], int(d.get("expiry") or time.time() + 86400))
            return self.session[0]

    def tile_url(self, z, x, y):
        return f"{TILE_API}/v1/2dtiles/{z}/{x}/{y}", {"session": self._session(), "key": self.key}


# ------------------------------------------------------------------ the app's back end
class Maps:
    def __init__(self, home=None, units="metric", key_source=None, demo=False):
        """home: Settings' location {name, lat, lon}; key_source(): the Google key or ""."""
        self.demo = demo
        self.units = units
        if demo:  # made-up places in a scratch directory
            import tempfile

            os.environ["COUCHBOX_MAPS_DIR"] = tempfile.mkdtemp(prefix="couchbox-maps-demo-")
            home = DEMO_HOME
            Path(os.environ["COUCHBOX_MAPS_DIR"], "places.json").write_text(
                json.dumps(
                    {
                        "places": [dict(DEMO_HOME, id="home", kind="home", name="Home", address="Van Ness Avenue, San Francisco")]
                        + DEMO_PLACES,
                        "recent": [
                            {"name": "Pier 39", "address": "Beach Street, San Francisco", "lat": 37.8087, "lon": -122.4098},
                            {"name": "Oracle Park", "address": "24 Willie Mays Plaza, San Francisco", "lat": 37.7786, "lon": -122.3893},
                        ],
                    }
                )
            )
        self.home_default = home or {}
        self.places = Places(self.home_default)
        self.key_source = key_source or (lambda: "")
        self.http = requests.Session()
        self.http.headers["User-Agent"] = UA
        self._provider = None
        self._key = None
        self.eta_cache = {}
        self.relay = None
        self.lock = threading.Lock()

    # provider: Google when there's a key
    def provider(self):
        if self.demo:
            if self._provider is None:
                self._provider = DemoProvider()
            return self._provider
        key = self.key_source() or ""
        with self.lock:
            if self._provider is None or key != self._key:
                self._key = key
                self._provider = Google(self.http, key) if key else Free(self.http)
                self.eta_cache = {}
            return self._provider

    def status(self):
        p = self.provider()
        return {
            "provider": p.name,
            "google": p.name == "Google Maps",
            "traffic": p.traffic,
            "modes": list(p.modes),
            "attribution": p.attribution,
            "units": self.units,
            "tile_px": p.tile_px,
            "tiles": self.tile_base(),
            "home": self.home(),
        }

    def home(self):
        return next((p for p in self.places.all()["places"] if p.get("kind") == "home"), None)

    def near(self):
        h = self.home() or {}
        return (h["lat"], h["lon"]) if h.get("lat") else None

    def decorate(self, items):
        n = self.near()
        for it in items:
            if n and it.get("lat") is not None:
                d = distance_m(n, (it["lat"], it["lon"]))
                it["distance_m"] = int(d)
                it["distance_text"] = dist_text(d, self.units)
        return items

    def search(self, query, limit=10):
        query = (query or "").strip()
        if not query:
            return {"query": "", "results": []}
        saved = [dict(p, saved=True) for p in self.places.all()["places"] if query.lower() in p["name"].lower()]
        try:
            found = self.provider().search(query, self.near(), limit)
        except requests.RequestException as err:
            raise MapsError(f"Search isn't answering ({err.__class__.__name__}).") from None
        out = []
        for it in saved + found:  # one result per place (OpenStreetMap often has a few for one)
            if any(o["name"] == it["name"] and distance_m((o["lat"], o["lon"]), (it["lat"], it["lon"])) < 250 for o in out):
                continue
            out.append(it)
        return {"query": query, "results": self.decorate(out)}

    def route_out(self, rt):
        rt = dict(rt)
        rt["distance_text"] = dist_text(rt["distance"], self.units)
        rt["duration_text"] = dur_text(rt["duration"])
        rt["delay"] = max(0, rt["duration"] - rt.get("static", rt["duration"])) if rt.get("traffic") else 0
        rt["delay_text"] = dur_text(rt["delay"]) if rt["delay"] >= 60 else ""
        pts = rt.pop("points")
        rt["bbox"] = bbox(pts) if pts else None
        rt["points"] = thin(pts)
        for s in rt.get("steps") or []:
            s["distance_text"] = dist_text(s["distance"], self.units) if s.get("distance") else ""
        return rt

    def directions(self, to, origin=None, mode="drive", depart=None, arrive=None, remember=True):
        """Routes (best first) from origin (default Home) to `to`."""
        origin = origin or self.home()
        if not origin:
            raise MapsError("Set Home first: Settings → Time → Location, or Home in Maps.")
        p = self.provider()
        if mode not in p.modes:
            raise MapsError(
                "Transit directions need a Google Maps key (Settings → Apps → Maps)." if mode == "transit" else f"No {mode} directions."
            )
        try:
            routes = p.routes(origin, to, mode, depart=depart, arrive=arrive)
        except requests.RequestException as err:
            raise MapsError(f"Directions aren't answering ({err.__class__.__name__}).") from None
        if remember and to.get("kind") not in ("home", "work", "place"):
            self.places.remember(to)
        return {
            "from": origin,
            "to": to,
            "mode": mode,
            "provider": p.name,
            "traffic": p.traffic and mode == "drive",
            "routes": [self.route_out(r) for r in routes],
        }

    def leave_by(self, to, arrive, origin=None, mode="drive"):
        """When to leave to arrive by `arrive` (epoch). Driving with Google: the traffic-aware
        drive time for the departure it suggests, refined a few times (Google only takes
        arrival times for transit)."""
        origin = origin or self.home()
        if not origin:
            raise MapsError("Set Home first: Settings → Time → Location, or Home in Maps.")
        p = self.provider()
        now = time.time()
        if mode == "transit" or not p.traffic:
            rt = p.routes(origin, to, mode, arrive=arrive, alternatives=False)[0]
            depart = rt["depart"] if mode == "transit" else arrive - rt["duration"]
        else:
            depart, rt = max(now, arrive - 3600), None
            for _ in range(4):
                rt = p.routes(origin, to, mode, depart=depart, alternatives=False)[0]
                want = arrive - rt["duration"]
                if abs(want - depart) < 120 or want <= now:
                    depart = want
                    break
                depart = max(now, want)
        depart = max(now, depart)  # too late to be on time: leave now
        if mode == "transit" and depart <= rt["depart"]:
            arrival = rt["arrive"]  # the timetable's own arrival
        else:
            arrival = depart + rt["duration"]
        rt["depart"], rt["arrive"] = int(depart), int(arrival)
        late = rt["arrive"] > arrive + 60
        out = self.route_out(rt)
        return {
            "from": origin,
            "to": to,
            "mode": mode,
            "arrive_by": int(arrive),
            "leave": out["depart"],
            "late": late,
            "late_by": max(0, out["arrive"] - int(arrive)) if late else 0,
            "route": out,
            "provider": p.name,
            "traffic": p.traffic and mode == "drive",
        }

    def etas(self):
        """The drive time now from Home to each saved place (cached a few minutes)."""
        home = self.home()
        out = []
        for pl in self.places.all()["places"]:
            if pl.get("kind") == "home" or not home:
                continue
            k = (round(pl["lat"], 5), round(pl["lon"], 5), round(home["lat"], 5), round(home["lon"], 5))
            hit = self.eta_cache.get(k)
            if not hit or hit[0] < time.time() - ETA_TTL:
                try:
                    rt = self.provider().routes(home, pl, "drive", alternatives=False)[0]
                    hit = (
                        time.time(),
                        {
                            "duration": rt["duration"],
                            "static": rt.get("static", rt["duration"]),
                            "distance": rt["distance"],
                            "summary": rt.get("summary", ""),
                            "traffic": rt.get("traffic", ""),
                        },
                    )
                except (MapsError, requests.RequestException) as err:
                    hit = (time.time() - ETA_TTL + 60, {"error": str(err) or err.__class__.__name__})
                self.eta_cache[k] = hit
            e = dict(hit[1], id=pl["id"])
            if "duration" in e:
                e.update(
                    duration_text=dur_text(e["duration"]),
                    distance_text=dist_text(e["distance"], self.units),
                    arrive=int(time.time() + e["duration"]),
                    delay_text=dur_text(e["duration"] - e["static"]) if e["duration"] - e["static"] >= 60 else "",
                )
            out.append(e)
        return {"etas": out, "at": int(time.time())}

    def resolve(self, query):
        """A spoken destination: a saved place by name, else the best search hit near Home."""
        p = self.places.find(query)
        if p:
            return p
        hits = self.search(query, limit=3)["results"]
        if not hits:
            raise MapsError(f"Couldn't find {query!r}.")
        return hits[0]

    # ------------------------------------------------------------------ tiles
    def tile_base(self):
        if self.relay is None:
            self.relay = Relay(self)
        return f"{self.relay.base}/tile"

    def tile(self, z, x, y):
        """PNG/JPEG bytes and content type for one tile, from the cache if it's fresh."""
        p = self.provider()
        if self.demo:
            return demo_tile(z, x, y), "image/png"
        n = 2**z
        if not (0 <= z <= 20 and 0 <= y < n):
            raise MapsError("no such tile")
        x %= n
        sub = "google" if isinstance(p, Google) else "osm"
        f = cache_dir() / "tiles" / sub / str(z) / str(x) / str(y)
        if f.exists() and f.stat().st_mtime > time.time() - TILE_DAYS * 86400:
            data = f.read_bytes()
            return data, "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
        url, params = p.tile_url(z, x, y)
        r = self.http.get(url, params=params, timeout=TIMEOUT)
        if r.status_code >= 400:
            raise MapsError(f"tile {r.status_code}")
        try:  # two requests for one tile can race: each writes its own temporary file
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_name(f"{f.name}.{secrets.token_hex(4)}.tmp")
            tmp.write_bytes(r.content)
            tmp.replace(f)
        except OSError as err:
            print(f"maps tile cache: {err}", flush=True)
        if secrets.randbelow(200) == 0:
            threading.Thread(target=prune_tiles, daemon=True).start()
        return r.content, r.headers.get("Content-Type", "image/png")


def prune_tiles(limit_mb=TILE_CACHE_MB):
    """Keep the tile cache under limit_mb: oldest first, and nothing past a week."""
    root = cache_dir() / "tiles"
    files = []
    for dirpath, _, names in os.walk(root):
        for n in names:
            fp = os.path.join(dirpath, n)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            files.append((st.st_mtime, st.st_size, fp))
    files.sort()
    total = sum(f[1] for f in files)
    old = time.time() - TILE_DAYS * 86400
    for mtime, size, fp in files:
        if total <= limit_mb * 1024 * 1024 and mtime > old:
            break
        try:
            os.unlink(fp)
            total -= size
        except OSError:
            pass


class _Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        import sys

        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


class Relay:
    """127.0.0.1:<port>/<secret>/tile/z/x/y -> the provider's tile (see the module docstring)."""

    def __init__(self, maps):
        self.secret = secrets.token_urlsafe(16)
        relay = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_GET(self):
                m = re.fullmatch(rf"/{re.escape(relay.secret)}/tile/(\d+)/(-?\d+)/(\d+)(?:\?.*)?", self.path)
                if not m:
                    return self._send(404, b"", "text/plain")
                try:
                    data, ctype = maps.tile(*map(int, m.groups()))
                    self._send(200, data, ctype)
                except (MapsError, requests.RequestException) as err:
                    print(f"maps tile {m.group(1)}/{m.group(2)}/{m.group(3)}: {err}", flush=True)
                    self._send(502, b"", "text/plain")

            def _send(self, code, data, ctype):
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass

        self.server = _Server(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}/{self.secret}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


# ------------------------------------------------------------------ demo (tests, screenshots)
DEMO_HOME = {"name": "San Francisco, California", "lat": 37.7793, "lon": -122.4193}
DEMO_PLACES = [
    {"id": "work", "kind": "work", "name": "Work", "address": "Ferry Building, San Francisco", "lat": 37.7955, "lon": -122.3937},
    {"id": "p1", "kind": "place", "name": "Airport", "address": "San Francisco International Airport", "lat": 37.6213, "lon": -122.3790},
    {
        "id": "p2",
        "kind": "place",
        "name": "Golden Gate Park",
        "address": "Golden Gate Park, San Francisco",
        "lat": 37.7694,
        "lon": -122.4862,
    },
    {"id": "p3", "kind": "place", "name": "Grocery", "address": "Market Street, San Francisco", "lat": 37.7840, "lon": -122.4075},
]


class DemoProvider:
    """Made-up search results and routes; COUCHBOX_MAPS_DEMO_GOOGLE=1 plays the Google provider
    (traffic, transit)."""

    tile_px = 256

    def __init__(self):
        self.traffic = os.environ.get("COUCHBOX_MAPS_DEMO_GOOGLE") == "1"
        self.name = "Google Maps" if self.traffic else "OpenStreetMap"
        self.modes = MODES if self.traffic else ("drive", "walk", "bike")
        self.attribution = "Demo map data"

    def search(self, query, near, limit=10):
        base = [
            ("Ferry Building", "1 Ferry Building, San Francisco, CA", 37.7955, -122.3937, "Market"),
            ("Ferry Building Farmers Market", "Ferry Plaza, San Francisco, CA", 37.7950, -122.3930, "Farmers' market"),
            ("Pier 39", "Beach Street & The Embarcadero, San Francisco, CA", 37.8087, -122.4098, "Tourist attraction"),
            ("Oracle Park", "24 Willie Mays Plaza, San Francisco, CA", 37.7786, -122.3893, "Stadium"),
            ("Coit Tower", "1 Telegraph Hill Blvd, San Francisco, CA", 37.8024, -122.4058, "Historical landmark"),
        ]
        return [{"name": n, "address": a, "lat": la, "lon": lo, "type": t} for n, a, la, lo, t in base][:limit]

    def routes(self, a, b, mode, depart=None, arrive=None, alternatives=True):
        d = distance_m((a["lat"], a["lon"]), (b["lat"], b["lon"]))
        speed = {"drive": 11.0, "transit": 7.0, "walk": 1.4, "bike": 4.5}[mode]
        out = []
        for i, (bend, extra, label) in enumerate(((0.3, 1.0, "Fastest"), (-0.4, 1.18, ""), (0.8, 1.3, ""))):
            if i and (not alternatives or mode == "walk"):
                break
            pts = []
            for k in range(41):
                f = k / 40
                lat = a["lat"] + (b["lat"] - a["lat"]) * f
                lon = a["lon"] + (b["lon"] - a["lon"]) * f
                off = math.sin(f * math.pi) * bend * 0.01 * (1 + d / 20000)
                pts.append([lat + off * 0.3, lon + off])
            dur = int(d * 1.35 * extra / speed) + 120
            static = int(dur / (1.22 if self.traffic and mode == "drive" and i == 0 else 1.05))
            start = arrive - dur if arrive else (depart or time.time())
            steps = [
                {"text": "Head north on Van Ness Avenue", "icon": "depart", "distance": 450, "duration": 70},
                {"text": "Turn right onto Market Street", "icon": "turn-right", "distance": 1900, "duration": 330},
                {
                    "text": "Keep left to merge onto the freeway",
                    "icon": "turn-slight-left",
                    "distance": int(d * 0.6),
                    "duration": int(dur * 0.5),
                },
                {"text": "Take the exit toward the Embarcadero", "icon": "turn-slight-right", "distance": 800, "duration": 90},
                {"text": "Turn left onto The Embarcadero", "icon": "turn-left", "distance": 600, "duration": 110},
                {"text": "Arrive (on the right)", "icon": "arrive", "distance": 0, "duration": 0},
            ]
            transit = []
            if mode == "transit":
                t0 = int(start + 360)
                transit = [
                    {
                        "line": "N",
                        "name": "N Judah",
                        "vehicle": "light_rail",
                        "color": "#005b95",
                        "headsign": "Caltrain",
                        "from": "Van Ness Station",
                        "to": "Embarcadero Station",
                        "departure": t0,
                        "arrival": t0 + dur - 600,
                        "stops": 6,
                    }
                ]
                steps = [
                    {"text": "Walk to Van Ness Station", "icon": "walk", "distance": 300, "duration": 300},
                    {
                        "text": "Light rail N toward Caltrain · 6 stops to Embarcadero Station",
                        "icon": "transit",
                        "distance": int(d),
                        "duration": dur - 600,
                        "transit": transit[0],
                    },
                    {"text": "Walk to the destination", "icon": "walk", "distance": 250, "duration": 240},
                ]
            out.append(
                {
                    "summary": ["US-101 N and The Embarcadero", "Market Street", "I-280 N"][i],
                    "labels": [label] if label else [],
                    "duration": dur,
                    "static": static,
                    "distance": int(d * 1.35 * extra),
                    "depart": int(start),
                    "arrive": int(start + dur),
                    "points": pts,
                    "steps": steps,
                    "transit": transit,
                    "traffic": traffic_level(dur, static) if self.traffic and mode == "drive" else "",
                }
            )
        return out


def png(width, height, rows):
    """A PNG from rows of RGB bytes."""
    raw = b"".join(b"\x00" + r for r in rows)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def demo_tile(z, x, y, size=256):
    """A made-up street map tile: blocks, streets every so often, a river."""
    land, street, big, water, park = b"\x23\x27\x31", b"\x3a\x41\x52", b"\x5a\x5f\x73", b"\x10\x22\x36", b"\x1d\x33\x28"
    rows = []
    for py in range(size):
        gy = y * size + py
        row = bytearray()
        for px in range(size):
            gx = x * size + px
            c = land
            if (gx // 300 + gy // 300) % 7 == 3:
                c = park
            if abs(((gx * 0.6 + gy) % 2400) - 1200) < 60:
                c = water
            elif gx % 96 < 4 or gy % 96 < 4:
                c = street
            if gx % 480 < 9 or (gy + gx // 3) % 640 < 9:
                c = big
            row += c
        rows.append(bytes(row))
    return png(size, size, rows)
