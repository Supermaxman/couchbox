// A recent request, as on the website's Discover page: backdrop, year, title, who asked,
// seasons, status, and the poster on the right.
import QtQuick

Rectangle {
    id: card
    property var request: ({})
    property var info: null
    readonly property var media: request.media || {}
    readonly property string mediaType: request.type || media.mediaType || "movie"
    width: 460 * S.u
    height: 240 * S.u
    radius: 12 * S.u
    color: S.panel
    border.color: S.line
    border.width: 1
    clip: true
    scale: activeFocus ? 1.04 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    Component.onCompleted: if (media.tmdbId) S.details(mediaType, media.tmdbId, r => info = r)
    function activate() { S.openMedia(mediaType, media.tmdbId) }
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()

    Image {
        anchors.fill: parent
        source: card.info ? S.img(card.info.backdropPath, "w780") : ""
        sourceSize.width: 600
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.92) }
            GradientStop { position: 1.0; color: Qt.rgba(0.07, 0.09, 0.15, 0.6) }
        }
    }
    Column {
        anchors { left: parent.left; top: parent.top; leftMargin: 20 * S.u; topMargin: 20 * S.u; right: poster.left; rightMargin: 12 * S.u }
        spacing: 6 * S.u
        Text {
            text: card.info ? (card.info.releaseDate || card.info.firstAirDate || "").slice(0, 4) : ""
            color: S.text2; font.family: S.font; font.pixelSize: 17 * S.u
        }
        Text {
            width: parent.width
            text: card.info ? (card.info.title || card.info.name) : ""
            elide: Text.ElideRight
            color: S.text; font.family: S.font; font.pixelSize: 24 * S.u; font.weight: Font.Bold
        }
        Row {
            spacing: 6 * S.u
            RoundImage {
                width: 24 * S.u; height: width
                source: card.request.requestedBy && card.request.requestedBy.avatar
                        ? (card.request.requestedBy.avatar.startsWith("http") ? card.request.requestedBy.avatar : seerrUrl + card.request.requestedBy.avatar) : ""
                sourceWidth: 40
            }
            Text {
                text: card.request.requestedBy ? card.request.requestedBy.displayName || "" : ""
                color: S.text2; font.family: S.font; font.pixelSize: 18 * S.u
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        Row {
            visible: card.mediaType === "tv"
            spacing: 8 * S.u
            Text { text: "Season"; color: S.dim; font.family: S.font; font.pixelSize: 17 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            Repeater {
                model: (card.request.seasons || []).slice(0, 4)
                Pill { text: modelData.seasonNumber; color: S.indigoDark; size: 14 }
            }
        }
        Row {
            spacing: 8 * S.u
            Text { text: "Status"; color: S.dim; font.family: S.font; font.pixelSize: 17 * S.u; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
            Pill { text: S.requestName(card.request); color: S.requestColor(card.request); size: 14 }
        }
    }
    Image {
        id: poster
        anchors { right: parent.right; top: parent.top; bottom: parent.bottom; margins: 20 * S.u }
        width: height * 2 / 3
        source: card.info ? S.img(card.info.posterPath, "w300_and_h450_face") : ""
        sourceSize.width: 200
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
    }
    Ring { on: card.activeFocus; radiusOf: 12 }
}
