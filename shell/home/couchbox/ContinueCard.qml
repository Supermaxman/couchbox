// couchbox: one card of the Continue watching row: the picture, the app's badge (its home tile,
// small), how far along (a bar in the app's colour) or LIVE, and the title and episode under it.
// Plain Qt Quick (no Plasma), so couchbox-ontv can draw it off screen for the screenshots.
import QtQuick

Item {
    id: card

    property var item: ({})     // {app, name, title, subtitle, art, fit, progress, left, live, viewers} (couchbox.ontv)
    property var app: null      // its home row entry: {tile, glow} for the badge and the colour
    property bool current: false
    property bool dimmed: false

    readonly property real radius: Math.round(width * 0.045)
    readonly property color tint: app && app.glow ? app.glow : "#7aa2ff"

    z: current ? 1 : 0
    scale: current ? 1.1 : 1
    Behavior on scale { NumberAnimation { duration: Style.duration * 1.4; easing.type: Easing.OutCubic } }

    // A soft shadow under the focused card
    Rectangle {
        anchors.fill: frame
        anchors.topMargin: 10
        anchors.bottomMargin: -10
        radius: card.radius
        color: "black"
        opacity: card.current ? 0.35 : 0
        Behavior on opacity { NumberAnimation { duration: Style.duration } }
    }

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: card.radius
        color: "#1d2028"
        clip: true

        // No picture (or it didn't load): the app's colour, and the title on it
        Rectangle {
            anchors.fill: parent
            visible: art.status !== Image.Ready
            radius: card.radius
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.darker(card.tint, 2.6) }
                GradientStop { position: 1; color: Qt.darker(card.tint, 4.2) }
            }
            Text {
                anchors.centerIn: parent
                width: parent.width - 36
                text: card.item.title || ""
                color: Style.text
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: Style.font
                font.pixelSize: 19
                font.weight: Font.Bold
            }
        }

        Image {
            id: art
            anchors.fill: parent
            source: card.item.art || ""
            sourceSize.width: 560
            asynchronous: true
            fillMode: card.item.fit ? Image.PreserveAspectFit : Image.PreserveAspectCrop
            smooth: true
            mipmap: true
            visible: status === Image.Ready
        }

        // How far along
        Rectangle {
            visible: (card.item.progress || 0) > 0 && !card.item.live
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 6
            color: Qt.rgba(0, 0, 0, 0.55)
            Rectangle {
                width: parent.width * Math.min(1, card.item.progress || 0)
                height: parent.height
                color: Qt.lighter(card.tint, 1.25)
            }
        }

        // Unfocused cards sit back a little while the row has focus
        Rectangle {
            anchors.fill: parent
            radius: card.radius
            color: "black"
            opacity: card.dimmed ? 0.35 : 0
            Behavior on opacity { NumberAnimation { duration: Style.duration } }
        }
    }

    // The app: its tile, small, or its name on a plate
    Rectangle {
        id: badge
        anchors { left: parent.left; top: parent.top; margins: 8 }
        readonly property bool tiled: badgeArt.status === Image.Ready
        width: tiled ? 72 : badgeName.implicitWidth + 16
        height: tiled ? 40 : 24
        radius: 6
        color: Qt.rgba(0, 0, 0, 0.7)
        border.color: Qt.rgba(1, 1, 1, 0.35)
        border.width: 1
        clip: true
        Image {
            id: badgeArt
            anchors.fill: parent
            anchors.margins: 1
            source: card.app && card.app.tile ? "file://" + card.app.tile : ""
            sourceSize.width: 160
            fillMode: Image.PreserveAspectCrop
            smooth: true
            mipmap: true
            visible: status === Image.Ready
        }
        Text {
            id: badgeName
            anchors.centerIn: parent
            visible: !badge.tiled
            text: card.item.name || card.item.app || ""
            color: Style.text
            font.family: Style.font
            font.pixelSize: 12
            font.weight: Font.Bold
        }
    }

    // LIVE (Twitch)
    Rectangle {
        visible: !!card.item.live
        anchors { right: parent.right; top: parent.top; margins: 8 }
        width: liveText.implicitWidth + 14
        height: liveText.implicitHeight + 6
        radius: 4
        color: "#eb0400"
        Text { id: liveText; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: Style.font; font.pixelSize: 13; font.weight: Font.Black }
    }

    // Focus ring
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: card.radius + 4
        color: "transparent"
        border.color: Style.ring
        border.width: 2.5
        opacity: card.current ? 0.95 : 0
        Behavior on opacity { NumberAnimation { duration: Style.duration } }
    }

    Column {
        anchors { top: parent.bottom; topMargin: 12; left: parent.left; right: parent.right }
        spacing: 2
        Text {
            width: parent.width
            text: card.item.title || ""
            elide: Text.ElideRight
            color: Style.text
            font.family: Style.font
            font.pixelSize: 15
            font.weight: Font.DemiBold
        }
        Text {
            width: parent.width
            text: [card.item.subtitle, card.item.live ? card.item.viewers : card.item.left].filter(x => !!x).join("  ·  ")
            elide: Text.ElideRight
            color: Style.textDim
            font.family: Style.font
            font.pixelSize: 13
            font.weight: Font.Medium
        }
    }
}
