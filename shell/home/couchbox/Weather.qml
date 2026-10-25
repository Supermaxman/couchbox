// couchbox: the weather at the top of the home screen: now (icon, temperature, what it's like) and
// today's high / low, from Open-Meteo (free, no key), every 15 minutes.
import QtQuick

Row {
    id: root
    property var place: null                  // {lat, lon, name, units} from HomeData (Settings → location)
    property var now: null
    readonly property string unit: place && place.units === "imperial" ? "°F" : "°C"
    visible: !!place && !!now
    spacing: 16

    // WMO weather codes -> what to show
    function describe(code, day) {
        const c = Number(code);
        if (c === 0) return [day ? "☀" : "☾", "Clear"];
        if (c <= 2) return [day ? "⛅" : "☁", "Partly cloudy"];
        if (c === 3) return ["☁", "Cloudy"];
        if (c <= 48) return ["🌫", "Fog"];
        if (c <= 57) return ["🌦", "Drizzle"];
        if (c <= 67) return ["🌧", "Rain"];
        if (c <= 77) return ["❄", "Snow"];
        if (c <= 82) return ["🌧", "Showers"];
        if (c <= 86) return ["🌨", "Snow showers"];
        return ["⛈", "Thunderstorms"];
    }

    function refresh() {
        if (!place) return;
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => {
            if (x.readyState !== XMLHttpRequest.DONE || x.status !== 200) return;
            try {
                const r = JSON.parse(x.responseText);
                root.now = {temp: Math.round(r.current.temperature_2m), code: r.current.weather_code, day: !!r.current.is_day,
                            hi: Math.round(r.daily.temperature_2m_max[0]), lo: Math.round(r.daily.temperature_2m_min[0])};
            } catch (e) {}
        };
        x.open("GET", "https://api.open-meteo.com/v1/forecast?latitude=" + place.lat + "&longitude=" + place.lon +
               "&current=temperature_2m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min" +
               (place.units === "imperial" ? "&temperature_unit=fahrenheit" : "") + "&timezone=auto&forecast_days=1");
        x.send();
    }
    Component.onCompleted: refresh()
    onPlaceChanged: refresh()
    Timer { interval: 15 * 60 * 1000; repeat: true; running: true; onTriggered: root.refresh() }

    Text {
        anchors.verticalCenter: parent.verticalCenter
        text: root.now ? root.describe(root.now.code, root.now.day)[0] : ""
        color: Style.text
        font.pixelSize: 40
    }
    Column {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Row {
            spacing: 10
            Text {
                id: temp
                text: root.now ? root.now.temp + root.unit : ""
                color: Style.text
                font.family: Style.font
                font.pixelSize: 34
                font.weight: Font.Light
            }
            Text {
                anchors.baseline: temp.baseline
                text: root.now ? root.describe(root.now.code, root.now.day)[1] : ""
                color: Style.text
                font.family: Style.font
                font.pixelSize: 18
                font.weight: Font.Medium
            }
        }
        Text {
            text: root.now ? (root.place.name ? root.place.name + "  ·  " : "") + "H " + root.now.hi + root.unit + "  L " + root.now.lo + root.unit : ""
            color: Style.textDim
            font.family: Style.font
            font.pixelSize: 15
            font.weight: Font.Medium
        }
    }
}
