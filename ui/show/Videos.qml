// The morning show's last part: the new videos from the YouTube subscriptions, a row of cards.
// Left/Right move along them, OK plays the one in focus in the YouTube app (opened()).
import QtQuick

FocusScope {
    id: vids
    property var part: ({})
    readonly property var videos: part.videos || []
    property alias index: list.currentIndex
    readonly property var current: videos[list.currentIndex] || null
    signal opened(var v)
    signal before()                          // Left on the first: the part before
    signal leave()                           // Back

    readonly property real cardW: (width - 2 * S.side - 2 * gap) / 3
    readonly property real gap: 36 * S.u

    ListView {
        id: list
        x: S.side
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: -20 * S.u
        width: vids.width - S.side
        height: vids.cardW * 9 / 16 + 170 * S.u
        orientation: ListView.Horizontal
        spacing: vids.gap
        focus: true
        clip: false
        interactive: false
        model: vids.videos
        highlightMoveDuration: 220
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: vids.width - 2 * S.side
        delegate: Item {
            id: card
            required property var modelData
            required property int index
            readonly property bool here: ListView.isCurrentItem && list.activeFocus
            width: vids.cardW
            height: list.height
            opacity: list.activeFocus && !here ? 0.62 : 1
            Behavior on opacity { NumberAnimation { duration: 180 } }
            Rectangle {
                id: pic
                width: parent.width; height: width * 9 / 16
                radius: 14 * S.u
                color: S.panel
                clip: true
                scale: card.here ? 1.04 : 1
                Behavior on scale { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }
                Image {
                    anchors.fill: parent
                    source: card.modelData.thumb || ""
                    sourceSize: S.sz(width, height)
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
                Rectangle {                      // its length
                    anchors { right: parent.right; bottom: parent.bottom; margins: 12 * S.u }
                    visible: !!card.modelData.duration
                    width: len.implicitWidth + 16 * S.u; height: len.implicitHeight + 6 * S.u
                    radius: 6 * S.u
                    color: "#cc000000"
                    Text { id: len; anchors.centerIn: parent; text: card.modelData.duration || ""; color: "white"; font.family: S.font; font.pixelSize: 20 * S.u; font.weight: Font.DemiBold }
                }
                Rectangle {                      // focus ring
                    anchors.fill: parent
                    radius: parent.radius
                    color: "transparent"
                    border.color: "white"
                    border.width: 4 * S.u
                    visible: card.here
                }
            }
            Text {
                id: title
                anchors { top: pic.bottom; topMargin: 22 * S.u }
                width: parent.width
                text: card.modelData.title || ""
                color: S.text
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                font.family: S.font; font.pixelSize: 30 * S.u; font.weight: Font.DemiBold
            }
            Text {
                anchors { top: title.bottom; topMargin: 8 * S.u }
                width: parent.width
                text: [card.modelData.channel, card.modelData.ago].filter(x => !!x).join("  ·  ")
                color: S.dim
                elide: Text.ElideRight
                font.family: S.font; font.pixelSize: 24 * S.u
            }
        }
        Keys.onLeftPressed: { if (currentIndex > 0) decrementCurrentIndex(); else vids.before(); }
        Keys.onRightPressed: if (currentIndex < count - 1) incrementCurrentIndex()
        Keys.onReturnPressed: if (vids.current) vids.opened(vids.current)
        Keys.onEnterPressed: if (vids.current) vids.opened(vids.current)
        Keys.onEscapePressed: vids.leave()
        Keys.onBackPressed: vids.leave()
        Keys.onUpPressed: (event) => event.accepted = true
        Keys.onDownPressed: (event) => event.accepted = true
    }
}
