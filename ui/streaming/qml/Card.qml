// One item in a row or grid: a series, collection or video, in the row's shape (poster 2:3,
// square, or wide 16:9). Wide cards carry the title and episode under the picture, and a
// progress bar when it's been started. OK opens it (shows) or plays it (videos).
import QtQuick

Item {
    id: card
    property var c: ({})
    property string shape: "wide"            // poster, square, wide
    property bool playDirect: false          // Continue Watching: OK plays
    readonly property real w: D.shapeW(shape)
    readonly property real h: D.shapeH(shape)
    readonly property bool titled: shape !== "poster"
    width: w
    height: h + (titled ? 96 * D.u : 0)

    function activate() {
        if (c.kind === "video" && (playDirect || !c.collectionId)) D.play(c.id);
        else D.open(c);
    }
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()

    Rectangle {
        id: frame
        width: card.w
        height: card.h
        radius: 6 * D.u
        color: D.panel
        clip: true
        scale: card.activeFocus ? 1.06 : 1
        Behavior on scale { NumberAnimation { duration: 110 } }
        Image {
            anchors.fill: parent
            source: {
                const c = card.c;
                const src = card.shape === "poster" ? (c.poster || c.landscape) : card.shape === "square" ? (c.square || c.poster || c.landscape) : (c.landscape || c.background);
                return D.img(src, card.w * 1.2, card.h * 1.2);
            }
            sourceSize.width: card.w * 1.2
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
        }
        Text {                                 // no picture
            anchors.centerIn: parent
            width: parent.width - 30 * D.u
            visible: !card.c.landscape && !card.c.poster && !card.c.square
            text: card.c.title || ""
            color: D.dim
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            font.family: D.font
            font.pixelSize: 24 * D.u
            font.weight: Font.Bold
        }
        Rectangle {                            // watched so far
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 8 * D.u
            color: Qt.rgba(0, 0, 0, 0.6)
            visible: (card.c.progress || 0) > 0
            Rectangle { width: parent.width * Math.min(1, card.c.progress || 0); height: parent.height; color: D.accent }
        }
        Rectangle {                            // LIVE (Twitch)
            visible: !!card.c.live
            anchors { left: parent.left; top: parent.top; margins: 10 * D.u }
            width: liveText.implicitWidth + 16 * D.u
            height: liveText.implicitHeight + 6 * D.u
            radius: 4 * D.u
            color: "#eb0400"
            Text { id: liveText; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: D.font; font.pixelSize: 17 * D.u; font.weight: Font.Black }
        }
        Rectangle {                            // uptime (Twitch), where videos show their length
            visible: !!card.c.live && !!card.c.started && card.shape === "wide"
            anchors { right: parent.right; top: parent.top; margins: 10 * D.u }
            width: upText.implicitWidth + 16 * D.u
            height: upText.implicitHeight + 6 * D.u
            radius: 4 * D.u
            color: Qt.rgba(0, 0, 0, 0.7)
            Text { id: upText; anchors.centerIn: parent; text: card.c.live ? D.uptime(card.c.started) : ""; color: D.text; font.family: D.font; font.pixelSize: 17 * D.u; font.weight: Font.DemiBold }
        }
        Rectangle {                            // viewers (Twitch)
            visible: !!card.c.viewers && card.c.kind === "video"
            anchors { left: parent.left; bottom: parent.bottom; margins: 10 * D.u }
            width: viewText.implicitWidth + 16 * D.u
            height: viewText.implicitHeight + 6 * D.u
            radius: 4 * D.u
            color: Qt.rgba(0, 0, 0, 0.7)
            Text { id: viewText; anchors.centerIn: parent; text: card.c.viewers || ""; color: D.text; font.family: D.font; font.pixelSize: 17 * D.u; font.weight: Font.DemiBold }
        }
        Rectangle {                            // duration
            visible: card.c.kind === "video" && card.c.duration > 0 && card.shape === "wide"
            anchors { right: parent.right; top: parent.top; margins: 10 * D.u }
            width: dur.implicitWidth + 16 * D.u
            height: dur.implicitHeight + 6 * D.u
            radius: 4 * D.u
            color: Qt.rgba(0, 0, 0, 0.7)
            Text { id: dur; anchors.centerIn: parent; text: D.length(card.c.duration || 0); color: D.text; font.family: D.font; font.pixelSize: 17 * D.u; font.weight: Font.DemiBold }
        }
        Rectangle {                            // focus
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.color: D.accent
            border.width: 5 * D.u
            visible: card.activeFocus
        }
    }
    Column {
        visible: card.titled
        anchors { top: frame.bottom; topMargin: 14 * D.u; left: parent.left; right: parent.right }
        spacing: 4 * D.u
        Text {
            width: parent.width
            text: card.c.title || ""
            elide: Text.ElideRight
            maximumLineCount: 1
            color: card.activeFocus ? D.accent : D.text
            font.family: D.font
            font.pixelSize: 23 * D.u
            font.weight: Font.Bold
        }
        Text {
            width: parent.width
            visible: !!text
            text: card.c.live ? [card.c.series, card.c.description].filter(x => x).join("  ·  ")
                 : card.c.kind === "category" ? (card.c.viewers || "")
                 : card.c.kind === "video" ? [card.c.series, D.epLabel(card.c)].filter(x => x).join("  ·  ")
                 : card.c.seasons ? card.c.seasons + (card.c.seasons === 1 ? " season" : " seasons")
                 : card.c.items ? card.c.items + " videos" : ""
            elide: Text.ElideRight
            color: D.dim
            font.family: D.font
            font.pixelSize: 19 * D.u
        }
    }
}
