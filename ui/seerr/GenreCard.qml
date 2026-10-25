// A genre tile: a backdrop in the genre's two-tone colours with its name (Movie/Series Genres).
import QtQuick

Rectangle {
    id: card
    property int genreId: 0
    property string name: ""
    property string backdrop: ""
    property string mediaType: "movie"
    // the website's genre colours (dark, light) for TMDB's duotone filter
    readonly property var colours: ({28: ["991B1B", "FCA5A5"], 12: ["480c8b", "a96bef"], 16: ["1F2937", "2864d2"],
        35: ["A16207", "FDE68A"], 80: ["1F2937", "60A5FA"], 99: ["065F46", "6EE7B7"], 18: ["9F1239", "FDA4AF"],
        10751: ["777e0d", "e4ed55"], 14: ["5B21B6", "C4B5FD"], 36: ["92400E", "FCD34D"], 27: ["1F2937", "D1D5DB"],
        10402: ["9D174D", "F9A8D4"], 9648: ["3730A3", "A5B4FC"], 10749: ["9F1239", "FDA4AF"], 878: ["1E3A8A", "93C5FD"],
        10770: ["991B1B", "FCA5A5"], 53: ["1F2937", "9CA3AF"], 10752: ["991B1B", "FCA5A5"], 37: ["92400E", "FCD34D"],
        10759: ["991B1B", "FCA5A5"], 10762: ["777e0d", "e4ed55"], 10763: ["1F2937", "9CA3AF"], 10764: ["5B21B6", "C4B5FD"],
        10765: ["1E3A8A", "93C5FD"], 10766: ["9F1239", "FDA4AF"], 10767: ["3730A3", "A5B4FC"], 10768: ["991B1B", "FCA5A5"]})
    readonly property var pair: colours[genreId] || ["030712", "6B7280"]
    width: S.tileW
    height: S.tileH
    radius: 12 * S.u
    color: "#" + pair[0]
    clip: true
    scale: activeFocus ? 1.05 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    function activate() { S.openGrid(name + (mediaType === "tv" ? " Series" : " Movies"), "/discover/" + (mediaType === "tv" ? "tv" : "movies") + "?genre=" + genreId, mediaType) }
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    Image {
        anchors.fill: parent
        source: card.backdrop ? "https://image.tmdb.org/t/p/w780_filter(duotone," + card.pair[0] + "," + card.pair[1] + ")" + card.backdrop : ""
        sourceSize.width: 600
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        opacity: 0.85
    }
    Text {
        anchors.centerIn: parent
        text: card.name
        color: "white"
        style: Text.Raised
        styleColor: Qt.rgba(0, 0, 0, 0.3)
        font.family: S.font
        font.pixelSize: 36 * S.u
        font.weight: Font.Bold
    }
    Ring { on: card.activeFocus; radiusOf: 12 }
}
