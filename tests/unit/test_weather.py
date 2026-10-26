"""The Weather app's data side against a fake Open-Meteo: parsing (time zones, units, the
first hour saying "Now"), day summaries, alerts, picking spoken days, and the "today at a
glance" line from the assistant's model (couchboxd)."""

import time

import pytest

from couchbox.services import weather


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise weather.requests.HTTPError(str(self.status_code))


def raw_forecast(days=3, start=None, rain_day=1, units="metric"):
    """Open-Meteo's answer (timeformat=unixtime) for `days` days from local midnight."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Europe/Berlin")
    start = start or datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    h = {
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
    d = {
        k: []
        for k in (
            "time",
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "sunrise",
            "sunset",
            "daylight_duration",
            "precipitation_sum",
            "precipitation_probability_max",
            "snowfall_sum",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
            "wind_direction_10m_dominant",
            "uv_index_max",
        )
    }
    for day in range(days):
        wet = day == rain_day
        for hour in range(24):
            t = start + timedelta(days=day, hours=hour)
            for k, v in (
                ("time", int(t.timestamp())),
                ("temperature_2m", 10 + hour / 3),
                ("apparent_temperature", 8 + hour / 3),
                ("precipitation_probability", 80 if wet and 13 <= hour <= 17 else 0),
                ("precipitation", 1.0 if wet and 13 <= hour <= 17 else 0),
                ("weather_code", 63 if wet else 0),
                ("is_day", int(7 <= hour <= 18)),
                ("wind_speed_10m", 12),
                ("wind_gusts_10m", 50 if wet else 20),
                ("wind_direction_10m", 225),
                ("relative_humidity_2m", 70),
                ("uv_index", 2),
            ):
                h[k].append(v)
        day0 = start + timedelta(days=day)
        for k, v in (
            ("time", int(day0.timestamp())),
            ("weather_code", 63 if wet else 0),
            ("temperature_2m_max", 17.6),
            ("temperature_2m_min", 9.6),
            ("apparent_temperature_max", 16),
            ("apparent_temperature_min", 7),
            ("sunrise", int((day0 + timedelta(hours=7, minutes=5)).timestamp())),
            ("sunset", int((day0 + timedelta(hours=17, minutes=40)).timestamp())),
            ("daylight_duration", 38000),
            ("precipitation_sum", 5.0 if wet else 0),
            ("precipitation_probability_max", 80 if wet else 0),
            ("snowfall_sum", 0),
            ("wind_speed_10m_max", 20),
            ("wind_gusts_10m_max", 50 if wet else 20),
            ("wind_direction_10m_dominant", 225),
            ("uv_index_max", 6.4 if not wet else 2),
        ):
            d[k].append(v)
    return {
        "timezone": "Europe/Berlin",
        "current": {
            "temperature_2m": 12.4,
            "apparent_temperature": 9.6,
            "weather_code": 2,
            "is_day": 1,
            "relative_humidity_2m": 71,
            "wind_speed_10m": 11,
            "wind_direction_10m": 230,
            "wind_gusts_10m": 25,
            "precipitation": 0,
            "uv_index": 1.2,
            "pressure_msl": 1013,
            "visibility": 24000,
            "cloud_cover": 40,
        },
        "hourly": h,
        "daily": d,
    }


class FakeHttp:
    def __init__(self, nws=None):
        self.headers = {}
        self.calls = []
        self.nws = nws

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, params))
        if url == weather.FORECAST_URL:
            return Resp(raw_forecast(units="imperial" if params.get("temperature_unit") else "metric"))
        if url == weather.AIR_URL:
            return Resp({"current": {"us_aqi": 61, "european_aqi": 33, "pm2_5": 9.2}})
        if url == weather.NWS_URL:
            return Resp(self.nws or {"features": []})
        return Resp({}, 404)


PLACE = {"name": "Berlin", "lat": 52.52, "lon": 13.4, "units": "metric"}


def test_parse_days_hours_and_units():
    data = weather.parse(raw_forecast(), PLACE, clock24=True)
    assert [d["name"] for d in data["days"][:2]] == ["Today", "Tomorrow"]
    assert data["units"]["temp"] == "°C" and data["now"]["temp"] == 12 and data["now"]["windDir"] == "SW"
    assert data["now"]["visibility"] == 24.0 and data["now"]["visUnit"] == "km"
    assert data["hours"][0]["hour"] == "Now"
    assert all(h["hour"] != "Now" for d in data["days"] for h in d["hours"])  # the days' hours are untouched
    t = data["days"][0]
    assert len(t["hours"]) == 24 and t["hours"][15]["hour"] == "15:00" and t["sunrise"] == "07:05"
    assert t["icon"] == "clear-day" and t["cond"] == "Clear"


def test_day_summaries_say_when_it_rains_and_if_it_is_windy():
    data = weather.parse(raw_forecast(), PLACE)
    wet = data["days"][1]["summary"]
    assert wet.startswith("Rain. High 18°, low 10°.")
    assert "80% chance of rain, mostly in the afternoon, about 5 mm" in wet
    assert "Windy: SW wind up to 20 km/h, gusts to 50." in wet
    dry = data["days"][0]["summary"]
    assert "Dry." in dry and "UV high (6.4)" in dry


def test_icons_cover_every_wmo_code_day_and_night():
    import os

    icons = os.path.join(os.path.dirname(__file__), "../../ui/weather/icons")
    for code in weather.WMO:
        for day in (True, False):
            assert os.path.isfile(os.path.join(icons, weather.icon(code, day) + ".svg")), (code, day)
    assert weather.icon(1, False) == "partly-night" and weather.icon(65) == "heavy-rain"


def test_fetch_adds_air_quality_and_alerts_where_nws_covers():
    nws = {
        "features": [
            {
                "properties": {
                    "event": "Flood Watch",
                    "severity": "Moderate",
                    "headline": "h",
                    "description": "line one\nline two\n\nnext",
                    "ends": "2026-11-01T18:00:00-07:00",
                    "status": "Actual",
                    "messageType": "Alert",
                }
            },
            {"properties": {"event": "High Wind Warning", "severity": "Severe", "status": "Actual"}},
            {"properties": {"event": "Old", "severity": "Severe", "status": "Actual", "messageType": "Cancel"}},
        ]
    }
    http = FakeHttp(nws)
    w = weather.Weather(session=http)
    us = w.get({"name": "Portland", "lat": 45.5, "lon": -122.6, "units": "imperial"})
    assert us["aqi"]["scale"] == "US AQI" and us["aqi"]["value"] == 61 and us["aqi"]["label"] == "Moderate"
    assert [a["event"] for a in us["alerts"]] == ["High Wind Warning", "Flood Watch"]  # worst first, cancels dropped
    assert us["alerts"][1]["description"] == "line one line two\n\nnext" and us["alerts"][1]["until"] == "Sun 6:00 PM"
    assert any(p and p.get("temperature_unit") == "fahrenheit" for _, p in http.calls)
    eu = weather.Weather(session=FakeHttp(nws)).get(PLACE)
    assert eu["alerts"] == [] and eu["aqi"]["scale"] == "European AQI"  # NWS isn't asked outside its area


def test_cached_until_stale(monkeypatch):
    http = FakeHttp()
    w = weather.Weather(session=http)
    w.get(PLACE)
    w.get(PLACE)
    assert sum(u == weather.FORECAST_URL for u, _ in http.calls) == 1
    real = time.time
    monkeypatch.setattr(weather.time, "time", lambda: real() + weather.TTL + 1)
    w.get(PLACE)
    assert sum(u == weather.FORECAST_URL for u, _ in http.calls) == 2


def test_no_town_and_no_network_say_what_to_do():
    with pytest.raises(weather.WeatherError, match="Settings"):
        weather.Weather(session=FakeHttp()).get(None)

    class Down(FakeHttp):
        def get(self, *a, **k):
            raise weather.requests.ConnectionError("down")

    with pytest.raises(weather.WeatherError, match="connection"):
        weather.Weather(session=Down()).get(PLACE)


def test_spoken_days():
    from datetime import date, timedelta

    start = date(2026, 10, 29)  # a Thursday
    days = [{"date": (start + timedelta(days=i)).isoformat(), "name": ["Today", "Tomorrow"][i] if i < 2 else "x"} for i in range(14)]
    pick = lambda s: [d["date"] for d in weather.pick_days(days, s)]  # noqa: E731
    assert pick("tomorrow") == ["2026-10-30"]
    assert pick("this weekend") == ["2026-10-31", "2026-11-01"]
    assert pick("next weekend") == ["2026-11-07", "2026-11-08"]
    assert pick("Saturday") == ["2026-10-31"]
    assert pick("next thursday") == ["2026-11-05"]
    assert pick("2026-11-03") == ["2026-11-03"]
    assert pick("2027-01-01") == []


def test_voice_report_and_glance_facts():
    data = weather.parse(raw_forecast(days=14), PLACE)
    week = weather.voice_report(data, "week")
    assert week.count("\n") == 14 and "rain 80% (5 mm)" in week
    assert "Rain chances by hour: 1 PM 80%, 2 PM 80%" in weather.voice_report(data, "day", "tomorrow")
    assert "No forecast" in weather.voice_report(data, "day", "2030-01-01")
    facts = weather.glance_facts(data)
    assert "Place: Berlin" in facts and "Tomorrow:" in facts


def test_demo_fortnight_parses():
    d = weather.Weather(demo=True).get({"name": "Lakeside", "lat": 1, "lon": 2, "units": "imperial"})
    assert len(d["days"]) == 14 and d["alerts"] and d["units"]["temp"] == "°F"


# ---------------------------------------------------------------------- couchboxd's glance line
def test_glance_asks_the_model_once_and_strips_its_thinking(box, monkeypatch):
    from couchbox import secrets, settings
    from couchbox.daemon import api_weather

    assert api_weather.weather_glance("facts") == {"text": "", "enabled": False}
    settings.update({"voice.mode": "assistant", "voice.llm.url": "http://llm.example/v1", "voice.llm.model": "m"})
    secrets.put("voice.llm.api_key", "test-fake-key")
    asked = []

    class R:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '<think>hmm</think>\n"Grey and mild: an umbrella for the afternoon."'}}]}

    def post(url, json=None, timeout=None, headers=None):
        asked.append((url, json, headers))
        return R()

    monkeypatch.setattr("requests.post", post)
    api_weather._cache.clear()
    assert api_weather.weather_glance("Now 12°C") == {"text": "Grey and mild: an umbrella for the afternoon.", "enabled": True}
    assert api_weather.weather_glance("Now 12°C")["text"]
    assert len(asked) == 1 and asked[0][0] == "http://llm.example/v1/chat/completions"
    assert asked[0][2] == {"Authorization": "Bearer test-fake-key"} and asked[0][1]["messages"][0]["content"].endswith("Now 12°C")
