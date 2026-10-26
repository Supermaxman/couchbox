"""Maps: OpenStreetMap services without a key, Google Maps Platform with one (both against fake
servers), saved places, leave-by, the ETA board, the tile relay and its cache."""

import json
import time
import urllib.request

import pytest

from couchbox.services import maps


class Resp:
    def __init__(self, status, body=None, content=b"", ctype="application/json"):
        self.status_code = status
        self.body = body
        self.content = content or (json.dumps(body).encode() if body is not None else b"")
        self.text = self.content.decode(errors="replace")
        self.headers = {"Content-Type": ctype}

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise maps.requests.HTTPError(str(self.status_code))


# an OSRM answer: two routes, steps with a turn and the arrival
OSRM_ROUTE = {
    "code": "Ok",
    "routes": [
        {
            "duration": 600.4,
            "distance": 5200.0,
            "geometry": "_p~iF~ps|U_ulLnnqC",
            "legs": [
                {
                    "summary": "Main Street",
                    "steps": [
                        {"name": "Main Street", "distance": 1000, "duration": 120, "maneuver": {"type": "depart"}},
                        {"name": "Oak Avenue", "distance": 4200, "duration": 480, "maneuver": {"type": "turn", "modifier": "left"}},
                        {"name": "", "distance": 0, "duration": 0, "maneuver": {"type": "arrive", "modifier": "right"}},
                    ],
                }
            ],
        },
        {"duration": 720, "distance": 6100, "geometry": "_p~iF~ps|U", "legs": [{"summary": "Elm Street", "steps": []}]},
    ],
}
PHOTON = {
    "features": [
        {
            "properties": {
                "name": "Central Station",
                "street": "Station Road",
                "housenumber": "1",
                "city": "Testville",
                "state": "Somewhere",
                "osm_value": "station",
            },
            "geometry": {"coordinates": [10.001, 50.001]},
        },
        {
            "properties": {"name": "Central Station", "street": "Station Road", "city": "Testville", "osm_value": "yes"},
            "geometry": {"coordinates": [10.0012, 50.0011]},
        },  # the same place again (OSM has a few): one result
        {"properties": {"name": "Museum", "city": "Testville", "osm_value": "museum"}, "geometry": {"coordinates": [10.05, 50.02]}},
    ]
}


class FakeHttp:
    """Answers like Photon, FOSSGIS OSRM, OSM tiles and Google Maps Platform."""

    def __init__(self):
        self.headers = {}
        self.calls = []
        self.google_duration = lambda body: 1800

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        if "photon" in url:
            return Resp(200, PHOTON)
        if "routing.openstreetmap.de" in url:
            return Resp(200, OSRM_ROUTE)
        if "tile.openstreetmap.org" in url or "2dtiles" in url:
            return Resp(200, content=b"\x89PNG fake tile", ctype="image/png")
        return Resp(404, {})

    def post(self, url, json=None, params=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json, headers or {}, params))
        if url.endswith("places:searchText"):
            return Resp(
                200,
                {
                    "places": [
                        {
                            "id": "g1",
                            "displayName": {"text": "Central Station"},
                            "formattedAddress": "1 Station Rd, Testville",
                            "location": {"latitude": 50.001, "longitude": 10.001},
                            "primaryTypeDisplayName": {"text": "Train station"},
                        }
                    ]
                },
            )
        if url.endswith("computeRoutes"):
            d = self.google_duration(json)
            route = {
                "duration": f"{d}s",
                "staticDuration": "1500s",
                "distanceMeters": 21000,
                "description": "A1",
                "polyline": {"encodedPolyline": "_p~iF~ps|U_ulLnnqC"},
                "routeLabels": ["DEFAULT_ROUTE"],
                "legs": [
                    {
                        "steps": [
                            {
                                "navigationInstruction": {"maneuver": "TURN_LEFT", "instructions": "Turn left onto A1"},
                                "distanceMeters": 21000,
                                "staticDuration": "1500s",
                                "travelMode": "DRIVE",
                            }
                        ]
                    }
                ],
            }
            if json["travelMode"] == "TRANSIT":
                route["legs"][0]["steps"] = [
                    {
                        "navigationInstruction": {"instructions": "Walk to Central"},
                        "distanceMeters": 200,
                        "staticDuration": "180s",
                        "travelMode": "WALK",
                    },
                    {
                        "travelMode": "TRANSIT",
                        "distanceMeters": 20000,
                        "staticDuration": "1500s",
                        "transitDetails": {
                            "headsign": "Airport",
                            "stopCount": 5,
                            "transitLine": {
                                "nameShort": "S1",
                                "name": "S-Bahn 1",
                                "color": "#ff0000",
                                "vehicle": {"type": "COMMUTER_TRAIN"},
                            },
                            "stopDetails": {
                                "departureStop": {"name": "Central"},
                                "arrivalStop": {"name": "Airport"},
                                "departureTime": "2030-01-01T10:03:00Z",
                                "arrivalTime": "2030-01-01T10:28:00Z",
                            },
                        },
                    },
                ]
            return Resp(200, {"routes": [route]})
        if url.endswith("createSession"):
            return Resp(200, {"session": "S1", "expiry": str(int(time.time()) + 14 * 86400)})
        return Resp(404, {"error": {"message": "nope"}})


@pytest.fixture
def m(tmp_path, monkeypatch):
    monkeypatch.setenv("COUCHBOX_MAPS_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("COUCHBOX_MAPS_CACHE", str(tmp_path / "cache"))
    fake = FakeHttp()
    monkeypatch.setattr(maps.requests, "Session", lambda: fake)
    key = {"v": ""}
    mm = maps.Maps(home={"name": "Testville", "lat": 50.0, "lon": 10.0}, units="metric", key_source=lambda: key["v"])
    mm.fake, mm.key = fake, key
    return mm


def test_polyline_decodes_googles_example():
    pts = maps.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
    assert pts == [[38.5, -120.2], [40.7, -120.95], [43.252, -126.453]]


def test_osrm_steps_read_like_directions():
    assert maps.osrm_step({"name": "Oak Avenue", "maneuver": {"type": "turn", "modifier": "slight right"}}) == (
        "Turn slight right onto Oak Avenue",
        "turn-slight-right",
    )
    assert maps.osrm_step({"maneuver": {"type": "roundabout", "exit": 2}, "name": "B4"}) == (
        "At the roundabout, take the 2nd exit onto B4",
        "roundabout",
    )
    assert maps.osrm_step({"maneuver": {"type": "arrive", "modifier": "left"}})[0] == "Arrive (on the left)"
    assert (
        maps.osrm_step({"maneuver": {"type": "on ramp", "modifier": "slight right"}, "name": "I 5"})[0]
        == "Take the ramp on the right onto I 5"
    )


def test_without_a_key_it_uses_openstreetmap(m):
    st = m.status()
    assert st["provider"] == "OpenStreetMap" and not st["traffic"] and "transit" not in st["modes"]
    r = m.search("central station")["results"]
    assert [x["name"] for x in r] == ["Central Station", "Museum"]  # the duplicate is gone
    assert r[0]["address"] == "1 Station Road, Testville, Somewhere" and r[0]["distance_text"]
    get = m.fake.calls[-1]
    assert get[2]["lat"] == 50.0 and get[2]["lon"] == 10.0  # near Home
    d = m.directions(r[0])
    assert [x["duration"] for x in d["routes"]] == [600, 720]
    best = d["routes"][0]
    assert best["steps"][1] == {
        "text": "Turn left onto Oak Avenue",
        "icon": "turn-left",
        "distance": 4200,
        "duration": 480,
        "distance_text": "4.2 km",
    }
    assert best["points"][0] == [38.5, -120.2] and best["bbox"]["north"] == 40.7
    assert best["duration_text"] == "10 min" and best["delay"] == 0
    assert "routed-car/route/v1/driving/10.000000,50.000000;10.001000,50.001000" in m.fake.calls[-1][1]
    with pytest.raises(maps.MapsError, match="Google Maps key"):
        m.directions(r[0], mode="transit")
    assert m.places.all()["recent"][0]["name"] == "Central Station"


def test_with_a_key_it_uses_google_with_traffic(m):
    m.key["v"] = "test-fake-key"
    st = m.status()
    assert st["provider"] == "Google Maps" and st["traffic"] and "transit" in st["modes"]
    r = m.search("central")["results"]
    post = m.fake.calls[-1]
    assert post[3]["X-Goog-Api-Key"] == "test-fake-key" and "places.location" in post[3]["X-Goog-FieldMask"]
    assert post[2]["locationBias"]["circle"]["center"] == {"latitude": 50.0, "longitude": 10.0}
    assert r[0]["type"] == "Train station"
    d = m.directions(r[0])
    body = m.fake.calls[-1][2]
    assert body["travelMode"] == "DRIVE" and body["routingPreference"] == "TRAFFIC_AWARE" and body["computeAlternativeRoutes"]
    rt = d["routes"][0]
    assert rt["duration"] == 1800 and rt["static"] == 1500 and rt["traffic"] == "moderate" and rt["delay_text"] == "5 min"
    assert rt["steps"][0]["icon"] == "turn-left" and d["traffic"]
    t = m.directions(r[0], mode="transit")["routes"][0]
    assert t["transit"][0]["line"] == "S1" and t["transit"][0]["vehicle"] == "commuter_train"
    assert t["steps"][1]["icon"] == "transit" and "S1 toward Airport" in t["steps"][1]["text"]
    assert t["depart"] == t["transit"][0]["departure"] - 180  # the walk to the stop first
    assert t["delay"] == 0  # no "traffic" on a train


def test_google_errors_say_what_happened(m, monkeypatch):
    m.key["v"] = "bad"
    monkeypatch.setattr(m.fake, "post", lambda *a, **k: Resp(403, {"error": {"message": "API key not valid."}}))
    with pytest.raises(maps.MapsError, match="Google refused the key"):
        m.search("x")


def test_leave_by_without_traffic_is_arrival_minus_the_drive(m):
    to = {"name": "Museum", "lat": 50.02, "lon": 10.05}
    arrive = time.time() + 7200
    r = m.leave_by(to, arrive)
    assert r["leave"] == int(arrive - 600) and not r["late"] and r["route"]["arrive"] == int(arrive)


def test_leave_by_with_traffic_finds_a_departure_that_arrives_on_time(m):
    m.key["v"] = "k"
    arrive = time.time() + 5 * 3600

    def dur(body):  # rush hour: later departures take longer
        dep = maps.from_rfc3339(body["departureTime"]) if "departureTime" in body else time.time()
        return 1800 + int(max(0, dep - (arrive - 7200)) / 10)

    m.fake.google_duration = dur
    r = m.leave_by({"name": "Museum", "lat": 50.02, "lon": 10.05}, arrive)
    assert abs(r["route"]["arrive"] - arrive) < 300 and not r["late"] and r["traffic"]
    # too late to make it: leave now, and how late
    r = m.leave_by({"name": "Museum", "lat": 50.02, "lon": 10.05}, time.time() + 600)
    assert r["late"] and r["late_by"] > 0


def test_places_home_work_and_names(m):
    p = m.places.all()["places"]
    assert p[0]["kind"] == "home" and p[0]["approx"]  # from Settings until set here
    m.places.save({"name": "Office", "address": "1 Work St", "lat": 50.1, "lon": 10.1}, kind="work")
    m.places.save({"name": "Gym", "lat": 50.2, "lon": 10.2}, name="The gym")
    m.places.save({"name": "Real home", "lat": 50.01, "lon": 10.01}, kind="home")
    p = m.places.all()["places"]
    assert [x["name"] for x in p] == ["Home", "Work", "The gym"] and not p[0].get("approx")
    assert m.places.find("work")["address"] == "1 Work St"
    assert m.places.find("the gym")["name"] == "The gym" and m.places.find("my gym")["name"] == "The gym"
    assert m.places.find("library") is None
    gym = m.places.find("gym")
    m.places.rename(gym["id"], "Gym")
    m.places.remove(gym["id"])
    assert [x["name"] for x in m.places.all()["places"]] == ["Home", "Work"]
    for i in range(20):
        m.places.remember({"name": f"P{i}", "lat": 50 + i / 100, "lon": 10})
    m.places.remember({"name": "P3", "lat": 50.03, "lon": 10})
    rec = m.places.all()["recent"]
    assert len(rec) == maps.RECENT and rec[0]["name"] == "P3" and [x["name"] for x in rec].count("P3") == 1


def test_eta_board_is_cached(m):
    m.places.save({"name": "Office", "lat": 50.1, "lon": 10.1}, kind="work")
    e = m.etas()["etas"]
    assert e[0]["id"] == "work" and e[0]["duration_text"] == "10 min"
    n = len(m.fake.calls)
    m.etas()
    assert len(m.fake.calls) == n
    assert m.resolve("work")["name"] == "Work"
    assert m.resolve("station")["name"] == "Central Station"  # not saved: the best search hit


def test_tiles_come_through_the_relay_and_the_cache(m):
    base = m.status()["tiles"]
    with urllib.request.urlopen(f"{base}/12/2150/1388", timeout=5) as r:
        assert r.read() == b"\x89PNG fake tile" and r.headers["Content-Type"] == "image/png"
    n = len(m.fake.calls)
    with urllib.request.urlopen(f"{base}/12/2150/1388", timeout=5) as r:
        r.read()
    assert len(m.fake.calls) == n  # from the cache
    assert m.fake.calls[-1][1] == "https://tile.openstreetmap.org/12/2150/1388.png"
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(base.rsplit("/", 2)[0] + "/wrong/tile/1/1/1", timeout=5)
    m.key["v"] = "k"  # Google: a tile session, the key, and its own cache
    with urllib.request.urlopen(f"{m.status()['tiles']}/12/2150/1388", timeout=5) as r:
        r.read()
    sess = [c for c in m.fake.calls if c[1].endswith("createSession")][0]
    assert sess[2]["mapType"] == "roadmap" and sess[2]["styles"]
    assert m.fake.calls[-1][2] == {"session": "S1", "key": "k"}


def test_the_same_tile_twice_at_once_is_fine(m):
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        got = list(pool.map(lambda _: m.tile(5, 1, 2)[0], range(16)))
    assert all(g == b"\x89PNG fake tile" for g in got)
    assert not list((maps.cache_dir() / "tiles").rglob("*.tmp"))


def test_demo_needs_no_network(monkeypatch, tmp_path):
    monkeypatch.setenv("COUCHBOX_MAPS_CACHE", str(tmp_path))
    d = maps.Maps(demo=True)
    assert d.status()["home"]["name"] == "Home"
    r = d.directions(d.search("ferry")["results"][0])
    assert len(r["routes"]) == 3 and r["routes"][0]["steps"]
    png, ctype = d.tile(12, 655, 1583)
    assert png.startswith(b"\x89PNG") and ctype == "image/png"
