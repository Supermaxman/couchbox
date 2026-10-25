// A studio or network tile: its logo on gray (Studios, Networks).
import QtQuick

Rectangle {
    id: card
    property int companyId: 0
    property string name: ""
    property string logo: ""
    property string mediaType: "movie"          // movie: studio, tv: network
    width: S.tileW
    height: S.tileH
    radius: 12 * S.u
    color: activeFocus ? S.panel2 : S.panel
    border.color: S.line
    border.width: 1
    scale: activeFocus ? 1.05 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    Component.onCompleted: {
        if (!logo && companyId)
            S.get((mediaType === "tv" ? "/network/" : "/studio/") + companyId, r => { logo = r.logoPath || ""; if (!name) name = r.name; });
    }
    function activate() { S.openGrid(name, mediaType === "tv" ? "/discover/tv?network=" + companyId : "/discover/movies?studio=" + companyId, mediaType) }
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    Image {
        anchors.fill: parent
        anchors.margins: 30 * S.u
        source: card.logo ? "https://image.tmdb.org/t/p/w780_filter(duotone,ffffff,bababa)" + card.logo : ""
        sourceSize.width: 400
        asynchronous: true
        fillMode: Image.PreserveAspectFit
    }
    Text {
        anchors.centerIn: parent
        visible: !card.logo
        text: card.name
        color: S.text2
        font.family: S.font
        font.pixelSize: 28 * S.u
        font.weight: Font.Bold
    }
    Ring { on: card.activeFocus; radiusOf: 12 }
}
