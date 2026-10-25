// MOVIE / SERIES in a poster's top-left corner.
import QtQuick

Rectangle {
    property string mediaType: "movie"
    width: label.implicitWidth + 20 * S.u
    height: 27 * S.u
    radius: height / 2
    color: Qt.rgba(c.r, c.g, c.b, 0.85)
    border.color: Qt.lighter(c, 1.35)
    border.width: 1
    readonly property color c: mediaType === "tv" ? S.seriesPurple : S.movieBlue
    Text {
        id: label
        anchors.centerIn: parent
        text: parent.mediaType === "tv" ? "SERIES" : "MOVIE"
        color: "white"
        font.family: S.font
        font.pixelSize: 14 * S.u
        font.weight: Font.DemiBold
        font.letterSpacing: 0.6 * S.u
    }
}
