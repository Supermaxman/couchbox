// Cover art, or (no picture yet, demo data, a playlist without one) a coloured square with a
// note or the first letter. Round for artists.
import QtQuick

Item {
    id: art
    property var item: ({})
    property bool round: item && item.kind === "artist"
    readonly property bool ready: img.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: art.round ? width / 2 : 8 * S.u
        visible: !art.ready
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.lighter(S.tint(art.item ? art.item.name : ""), 1.35) }
            GradientStop { position: 1; color: S.tint(art.item ? art.item.name : "") }
        }
        Text {
            anchors.centerIn: parent
            visible: art.item && art.item.kind === "artist"
            text: art.item && art.item.name ? art.item.name.charAt(0).toUpperCase() : ""
            color: "#e8ffffff"; font.family: S.font; font.pixelSize: parent.height * 0.42; font.weight: Font.Bold
        }
        Image {
            anchors.centerIn: parent
            visible: !(art.item && art.item.kind === "artist")
            width: parent.width * (art.item && art.item.kind === "liked" ? 0.42 : 0.36); height: width
            sourceSize: Qt.size(width, height)
            source: S.icon(art.item && art.item.kind === "liked" ? "heart-filled" : "note")
            opacity: 0.85
        }
    }
    Image {
        id: img
        anchors.fill: parent
        source: art.item && art.item.image ? art.item.image : ""
        sourceSize.width: Math.round(art.width)
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: art.ready && !art.round
    }
    Rectangle {                                  // round art: the picture through a circle
        anchors.fill: parent
        visible: art.ready && art.round
        radius: width / 2
        clip: true
        color: "transparent"
        Image { anchors.fill: parent; source: img.source; sourceSize.width: Math.round(art.width); fillMode: Image.PreserveAspectCrop; asynchronous: true
                layer.enabled: true; layer.smooth: true }
        layer.enabled: true
    }
}
