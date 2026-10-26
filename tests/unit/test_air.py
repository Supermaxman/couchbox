"""Air quality and pollen (services/air.py) against answers recorded from Google's Air Quality
and Pollen APIs and Open-Meteo's air-quality API (tests/unit/data/air_samples.json): readings,
the main pollutant, days, pollen with plants, which source is used, caching, the key kept out
of the log, and what the voice assistant reads."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from couchbox.services import air, weather

SAMPLES = json.loads((Path(__file__).parent / "data/air_samples.json").read_text())
LA = ZoneInfo("America/Los_Angeles")
SEATTLE = {"name": "Seattle", "lat": 47.61, "lon": -122.33, "units": "imperial"}
BERLIN = {"name": "Berlin", "lat": 52.52, "lon": 13.4, "units": "metric"}
RECORDED = SAMPLES["open_meteo_seattle"]["current"]["time"]  # when the samples were taken


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            err = air.requests.HTTPError(f"{self.status_code} for url: https://x/?key=SECRET-KEY")
            err.response = self
            raise err


class FakeHttp:
    """Google and Open-Meteo, from the recorded answers."""

    def __init__(self, om="open_meteo_seattle", pollen="google_pollen_seattle", google=200):
        self.om, self.pollen, self.google = om, pollen, google
        self.headers, self.calls = {}, []

    def get(self, url, params=None, timeout=None, headers=None):
        self.calls.append(url)
        if url == air.OPEN_METEO:
            return Resp(SAMPLES[self.om])
        if url == air.GOOGLE_POLLEN:
            assert params["key"] == "SECRET-KEY" and params["days"] == 5
            return Resp(SAMPLES[self.pollen] if self.google == 200 else {"error": {}}, self.google)
        return Resp({}, 404)

    def post(self, url, params=None, json=None, timeout=None):
        self.calls.append(url)
        assert params == {"key": "SECRET-KEY"}
        if self.google != 200:
            return Resp({"error": {"status": "PERMISSION_DENIED"}}, self.google)
        if url.endswith("currentConditions:lookup"):
            assert "LOCAL_AQI" in json["extraComputations"]
            return Resp(SAMPLES["google_current"])
        if url.endswith("forecast:lookup"):
            assert json["pageSize"] == air.FORECAST_HOURS and json["period"]["startTime"] < json["period"]["endTime"]
            return Resp(SAMPLES["google_forecast"])
        return Resp({}, 404)


def test_google_air_uses_the_local_index_with_its_main_pollutant_and_advice():
    a = air.parse_google_air(SAMPLES["google_current"], SAMPLES["google_forecast"], LA)
    assert a["scale"] == "US AQI" and a["source"] == "Google"
    assert a["now"]["value"] == 51 and a["now"]["label"] == "Moderate" and a["now"]["pollutant"] == "PM2.5"
    assert a["now"]["color"] == "#eab308" and a["now"]["pm25"] == 11.5
    assert a["now"]["advice"].startswith("With this level of air quality")
    first = datetime.fromisoformat(SAMPLES["google_forecast"]["hourlyForecasts"][0]["dateTime"].replace("Z", "+00:00"))
    assert first.astimezone(LA).date().isoformat() in a["days"]
    for d in a["days"].values():
        assert d["value"] >= 0 and d["label"] and d["color"].startswith("#")


def test_google_universal_index_when_theres_no_local_one():
    uaqi = [x for x in SAMPLES["google_current"]["indexes"] if x["code"] == "uaqi"]
    scale, r = air.g_reading(uaqi)
    assert scale == "Universal AQI" and r["label"] == "Excellent" and r["color"] == "#58be35" and r["pollutant"] == "NO₂"
    assert air.parse_google_air({"indexes": []}, None, LA) is None


def test_google_pollen_types_levels_and_plants():
    out = air.parse_google_pollen(SAMPLES["google_pollen_sydney"])
    (day,) = out.values()
    tree, grass = day
    assert (tree["type"], tree["value"], tree["level"], tree["inSeason"]) == ("Tree", 1, "Very low", False)
    assert (grass["type"], grass["value"], grass["level"], grass["inSeason"]) == ("Grass", 3, "Moderate", True)
    assert grass["plants"] == ["Grasses"] and tree["plants"] == ["Cypress Pine"]
    seattle = air.parse_google_pollen(SAMPLES["google_pollen_seattle"])
    assert len(seattle) == 5
    first = next(iter(seattle.values()))
    assert [t["code"] for t in first] == ["TREE", "GRASS", "WEED"]  # always in this order
    assert all(t["value"] == 0 and not t["inSeason"] and t["plants"] == [] for t in first)  # late October
    assert air.parse_google_pollen({}) is None


def test_open_meteo_us_aqi_main_pollutant_and_no_pollen_outside_europe():
    a, pollen = air.parse_open_meteo(SAMPLES["open_meteo_seattle"], "imperial", LA)
    c = SAMPLES["open_meteo_seattle"]["current"]
    assert a["scale"] == "US AQI" and a["source"] == "Open-Meteo" and a["now"]["value"] == c["us_aqi"]
    subs = {k: v for k, v in c.items() if k.startswith("us_aqi_")}
    assert a["now"]["pollutant"] == air.POLLUTANT[air.SUB[max(subs, key=subs.get)[len("us_aqi_") :]]]
    assert a["days"] and pollen is None


def test_open_meteo_european_pollen():
    a, pollen = air.parse_open_meteo(SAMPLES["open_meteo_berlin"], "metric", ZoneInfo("Europe/Berlin"))
    assert a["scale"] == "European AQI" and a["now"]["label"] in ("Good", "Fair", "Moderate")
    assert pollen and all([t["code"] for t in p] == ["TREE", "GRASS", "WEED"] for p in pollen.values())
    day = {"birch_pollen": 120.0, "alder_pollen": 3.0, "grass_pollen": 4.0, "ragweed_pollen": None, "mugwort_pollen": 0.0}
    tree, grass, weed = air.om_pollen_day(day)
    assert (tree["level"], tree["plants"]) == ("High", ["Birch", "Alder"])
    assert (grass["level"], grass["plants"]) == ("Low", ["Grasses"])
    assert (weed["level"], weed["plants"], weed["inSeason"]) == ("None", [], False)
    assert air.om_pollen_day({k: None for k in air.OM_POLLEN}) is None


def test_the_key_brings_google_and_both_are_cached(monkeypatch):
    http = FakeHttp()
    a = air.Air(http, key_source=lambda: "SECRET-KEY")
    aq, pollen = a.get(SEATTLE, "America/Los_Angeles")
    assert aq["source"] == "Google" and len(pollen) == 5
    assert air.OPEN_METEO not in http.calls
    a.get(SEATTLE, "America/Los_Angeles")
    assert len(http.calls) == 3  # current, forecast, pollen: once
    real = air.time.time
    monkeypatch.setattr(air.time, "time", lambda: real() + air.AIR_TTL + 1)
    a.get(SEATTLE, "America/Los_Angeles")
    assert len(http.calls) == 5  # air again; pollen keeps for six hours
    monkeypatch.setattr(air.time, "time", lambda: real() + air.POLLEN_TTL + 1)
    a.get(SEATTLE, "America/Los_Angeles")
    assert http.calls.count(air.GOOGLE_POLLEN) == 2


def test_no_key_or_a_refused_key_falls_back_to_open_meteo(capsys):
    aq, pollen = air.Air(FakeHttp()).get(SEATTLE, "America/Los_Angeles")
    assert aq["source"] == "Open-Meteo" and pollen is None
    http = FakeHttp(om="open_meteo_berlin", google=403)
    aq, pollen = air.Air(http, key_source=lambda: "SECRET-KEY").get(BERLIN, "Europe/Berlin")
    assert aq["source"] == "Open-Meteo" and pollen  # Europe: Open-Meteo's pollen
    log = capsys.readouterr().out
    assert "HTTP 403" in log and "SECRET-KEY" not in log


def test_weather_days_get_their_air_and_pollen(monkeypatch):
    from test_weather import raw_forecast

    monkeypatch.setattr(weather.time, "time", lambda: RECORDED + 60)  # the samples' day

    class Http(FakeHttp):
        def get(self, url, params=None, timeout=None, headers=None):
            if url == weather.FORECAST_URL:
                raw = raw_forecast(days=6, start=datetime.fromtimestamp(RECORDED, LA).replace(hour=0, minute=0, second=0, microsecond=0))
                raw["timezone"] = "America/Los_Angeles"
                return Resp(raw)
            if url == weather.NWS_URL:
                return Resp({"features": []})
            return super().get(url, params, timeout, headers)

    d = weather.Weather(session=Http(), key_source=lambda: "SECRET-KEY").get(SEATTLE)
    assert d["aqi"]["value"] == 51 and d["aqi"]["scale"] == "US AQI" and d["aqi"]["source"] == "Google"
    assert sum(1 for x in d["days"] if x["pollen"]) >= 1 and any(x["aqi"] for x in d["days"][1:])
    report = weather.voice_report(d, "air")
    assert "US AQI 51, moderate (mostly PM2.5)" in report and "Source: Google" in report
    assert "pollen: tree out of season, grass out of season, weed out of season" in weather.voice_report(d, "pollen")
    assert "No pollen forecast" in weather.voice_report(d, "pollen", d["days"][-1]["date"])


def test_demo_has_air_and_pollen():
    d = weather.Weather(demo=True).get({"name": "Lakeside", "lat": 1, "lon": 2, "units": "imperial"})
    assert d["aqi"]["pollutant"] and d["days"][0]["pollen"][0]["plants"] and d["days"][2]["aqi"]
    assert "Pollen today: tree high" in weather.glance_facts(d)
    assert d["days"][6]["pollen"] is None


@pytest.mark.parametrize(("value", "words"), [(10, "Good"), (51, "Moderate"), (120, "Unhealthy for some"), (400, "Hazardous")])
def test_us_aqi_words(value, words):
    assert air.aqi_label(value, "us")[0] == words
