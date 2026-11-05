// A card, as YouTube's TV app draws it: the thumbnail (rounded, the length bottom right, a red
// bar for what's been watched), then the title and the grey lines under it (the channel; badges
// such as 4K and CC before the views and age). A channel is a round picture with its name
// centred; a game is a box-art poster. `on` draws the white focus ring and the white title.
// boxed: a channel page's card, the title and lines in a panel under the picture that turns white
// with focus.
import QtQuick

Item {
    id: card
    property var item: ({})
    property bool on: false
    property real w: Y.cardW                  // the thumbnail's width (a 16:9 card)
    property bool boxed: false
    property color behind: Y.bg               // the colour around the card (its rounded corners)
    readonly property string kind: item.type || "video"
    readonly property bool round: kind === "channel"
    readonly property real thumbH: Math.round(w * 9 / 16)
    readonly property real artW: round ? thumbH : kind === "game" ? Math.round(thumbH * 0.75) : w
    width: artW
    height: art.height + (boxed ? panel.height : caption.implicitHeight + 26 * Y.u)

    Item {
        id: art
        width: card.artW
        height: card.thumbH
        Rectangle {                          // no picture (yet, or the demo): the title's colours
            anchors.fill: parent
            radius: card.round ? width / 2 : Y.radius
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.hsla(Y.hue(card.item.title), 0.55, 0.32, 1) }
                GradientStop { position: 1; color: Qt.hsla((Y.hue(card.item.title) + 0.15) % 1, 0.6, 0.14, 1) }
            }
            Text {
                visible: img.status !== Image.Ready && !card.round
                anchors { fill: parent; margins: 26 * Y.u }
                text: card.item.title || ""
                color: "white"
                font.family: Y.font; font.pixelSize: card.w * 0.075; font.weight: Font.Black
                wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                verticalAlignment: Text.AlignTop
                style: Text.Raised; styleColor: "#60000000"
            }
            Text {
                visible: img.status !== Image.Ready && card.round
                anchors.centerIn: parent
                text: (card.item.title || "?").slice(0, 2)
                color: "white"
                font.family: Y.font; font.pixelSize: parent.height * 0.4; font.weight: Font.Medium
            }
        }
        Image {
            id: img
            anchors.fill: parent
            source: card.item.thumb || ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize: Y.sz(width, height)
            visible: status === Image.Ready
        }
        Corners {
            anchors.fill: parent
            r: card.round ? width / 2 : Y.radius
            color: card.behind
            lower: !card.boxed
            visible: card.behind.a > 0
        }
        Rectangle {                          // the length, bottom right (LIVE in red)
            visible: !!card.item.duration || card.item.live
            anchors { right: parent.right; bottom: parent.bottom; margins: 8 * Y.u; bottomMargin: (progress.visible ? 14 : 8) * Y.u }
            width: badge.implicitWidth + 16 * Y.u
            height: badge.implicitHeight + 4 * Y.u
            radius: 6 * Y.u
            color: card.item.live ? "#cc0000" : "#cc000000"
            Text {
                id: badge
                anchors.centerIn: parent
                text: card.item.live ? "LIVE" : card.item.duration || ""
                color: "white"
                font.family: Y.font; font.pixelSize: Y.tMeta; font.weight: Font.Medium
            }
        }
        Item {                               // watched so far: red over a faint track
            id: progress
            visible: (card.item.progress || 0) > 0
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 6 * Y.u
            Rectangle { anchors.fill: parent; color: "#66ffffff" }
            Rectangle { width: parent.width * Math.min(1, card.item.progress || 0); height: parent.height; color: Y.red }
        }
    }

    // ------------------------------------------------------------------ text
    Column {
        id: caption
        visible: !card.boxed
        anchors { left: art.left; top: art.bottom; topMargin: 26 * Y.u }
        width: card.round ? card.artW : card.w
        spacing: 6 * Y.u
        Text {
            width: parent.width
            text: card.item.title || ""
            color: card.on ? Y.text : Y.dim
            font.family: Y.font; font.pixelSize: Y.tTitle; font.weight: Font.Medium
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            horizontalAlignment: card.round ? Text.AlignHCenter : Text.AlignLeft
            lineHeight: 1.08
        }
        Text {
            width: parent.width
            visible: (card.item.lines || []).length > 0
            text: (card.item.lines || [])[0] || ""
            color: Y.dim
            font.family: Y.font; font.pixelSize: card.round ? Y.tSmall + 2 * Y.u : Y.tMeta
            elide: Text.ElideRight
            horizontalAlignment: card.round ? Text.AlignHCenter : Text.AlignLeft
        }
        Row {
            visible: (card.item.lines || []).length > 1 || (card.item.badges || []).length > 0
            spacing: 8 * Y.u
            anchors.horizontalCenter: card.round ? parent.horizontalCenter : undefined
            Repeater {
                model: card.item.badges || []
                Rectangle {
                    required property string modelData
                    width: bt.implicitWidth + 14 * Y.u
                    height: bt.implicitHeight + 2 * Y.u
                    radius: 4 * Y.u
                    color: Y.raised
                    anchors.verticalCenter: parent.verticalCenter
                    Text { id: bt; anchors.centerIn: parent; text: parent.modelData; color: Y.dim; font.family: Y.font; font.pixelSize: Y.tMeta; font.weight: Font.Medium }
                }
            }
            Text {
                width: Math.min(implicitWidth, card.w - x)
                text: (card.item.lines || []).slice(1).join(" • ")
                color: Y.dim
                font.family: Y.font; font.pixelSize: card.round ? Y.tSmall + 2 * Y.u : Y.tMeta
                elide: Text.ElideRight
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    Rectangle {                              // boxed: the panel under the picture
        id: panel
        visible: card.boxed
        anchors { left: art.left; right: art.right; top: art.bottom }
        height: 194 * Y.u
        color: card.on ? Y.text : "#212121"
        radius: Y.radius
        Rectangle { width: parent.width; height: parent.radius; color: parent.color }   // square top
        Column {
            anchors { fill: parent; margins: 24 * Y.u; topMargin: 26 * Y.u }
            spacing: 8 * Y.u
            Text {
                width: parent.width
                text: card.item.title || ""
                color: card.on ? Y.ink : Y.dim
                font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Medium
                elide: Text.ElideRight
            }
            Item { width: 1; height: 22 * Y.u }
            Repeater {
                model: (card.item.lines || []).slice(0, 2)
                Text {
                    required property string modelData
                    width: parent.width
                    text: modelData
                    color: card.on ? "#606060" : Y.faint
                    font.family: Y.font; font.pixelSize: Y.tSmall
                    elide: Text.ElideRight
                }
            }
        }
    }
    Rectangle {                              // the focus ring
        visible: card.on
        x: -Y.ring; y: -Y.ring
        width: card.artW + 2 * Y.ring
        height: (card.boxed ? art.height + panel.height : art.height) + 2 * Y.ring
        radius: (card.round ? card.thumbH / 2 : Y.radius) + Y.ring
        color: "transparent"
        border.color: Y.text
        border.width: Y.ring
    }
}
