// The morning show's weather: the radar's last hour (and its forecast) looping over the map,
// centred on home, with today's forecast line over a shade at the bottom. Fetched as the show
// reaches it (bin/couchbox-show's weather), so it's this morning's.
import QtQuick
import "../weather" as Wx

Item {
    id: wx
    property var info: null                  // {forecast: couchbox.show.forecast(), radar: radar.py's frames()}
    property bool running: false
    readonly property var fc: info ? info.forecast : null

    Rectangle { anchors.fill: parent; color: "#0b0c0f" }
    Wx.RadarLoop {
        anchors.fill: parent
        visible: !!(wx.info && wx.info.radar)
        info: wx.info ? wx.info.radar : null
        running: wx.running
        u: S.u * 1.6
        zoom: 7
        showTime: false
    }
    Image {                                  // without a radar: the day's weather, large
        anchors { horizontalCenter: parent.horizontalCenter; verticalCenter: parent.verticalCenter; verticalCenterOffset: -120 * S.u }
        visible: !!(wx.fc && !(wx.info && wx.info.radar) && wx.fc.icon)
        width: 260 * S.u; height: width
        sourceSize: S.sz(width, height)
        source: wx.fc && wx.fc.icon ? Qt.resolvedUrl("../weather/icons/" + wx.fc.icon + ".svg") : ""
    }
}
