// A panel beside the player (the video shrinks to its left), as YouTube's TV app opens them: the
// channel (its picture, name, Subscribe / Subscribed and Go to channel), the notification levels
// (All, Personalized, None, Unsubscribe), and Save (Watch later and the playlists).
// Up and Down move, OK picks, Back closes.
import QtQuick

FocusScope {
    id: panel
    property string title: ""
    property string subtitle: ""
    property string avatar: ""                // the channel panel: a large picture, the name and a line
    property string name: ""
    property string line: ""
    property var options: []                  // [{label, icon, checked, trailing}]
    property int index: 0
    property string note: ""                  // under the options (nothing to show yet...)
    readonly property bool channel: !!name    // the channel's panel: its rows 95 tall, Medium, a larger bell
    readonly property bool levels: title === "Notifications"   // the bell's levels: higher, Medium labels
    signal picked(int index)
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0

    // opening: in from the right; closing: out, quicker
    property bool open: false
    visible: open || opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: panel.open ? Y.tPanel : Y.tOut; easing.type: Easing.OutCubic } }
    transform: Translate {
        x: panel.open ? 0 : 56 * Y.u
        Behavior on x { NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }
    }
    Keys.onUpPressed: index = Math.max(0, index - 1)
    Keys.onDownPressed: index = Math.min(options.length - 1, index + 1)
    Keys.onReturnPressed: if (options.length) picked(index)
    Keys.onEnterPressed: if (options.length) picked(index)
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}

    Column {
        width: parent.width
        y: (panel.channel ? 28 : 38) * Y.u
        spacing: 12 * Y.u
        RoundImage {
            visible: !!panel.name
            width: 342 * Y.u; height: width
            anchors.horizontalCenter: parent.horizontalCenter
            source: panel.avatar
            fallback: panel.name
        }
        Text {
            visible: !!panel.name
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            topPadding: 18 * Y.u
            text: panel.name
            color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            elide: Text.ElideRight
        }
        Text {
            visible: !!panel.line
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: panel.line
            color: Y.dim; font.family: Y.font; font.pixelSize: 28 * Y.u
            elide: Text.ElideRight
        }
        Text {
            visible: !!panel.title
            width: parent.width
            text: panel.title
            color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            height: 40 * Y.u; verticalAlignment: Text.AlignVCenter
        }
        Text {
            visible: !!panel.subtitle
            width: parent.width
            text: panel.subtitle
            color: Y.dim; font.family: Y.font; font.pixelSize: 30 * Y.u
            wrapMode: Text.WordWrap
            lineHeightMode: Text.FixedHeight; lineHeight: 42 * Y.u
        }
        Item { width: 1; height: (panel.name ? 18 : panel.levels ? 6 : 30) * Y.u }   // (the bell's levels: their title at y 59, the list 24 higher)
        MenuRows {
            width: panel.width
            options: panel.options
            index: panel.index
            focused: panel.activeFocus || !panel.open   // (kept while it slides out)
            gap: 12 * Y.u
            rowH: (panel.channel ? 95 : 90) * Y.u
            iconX: 30 * Y.u; iconSize: 38 * Y.u
            textX: 96 * Y.u; plainX: 24 * Y.u
            textSize: 30 * Y.u
            weight: panel.channel || panel.levels ? Font.Medium : Font.DemiBold
            trailSize: (panel.channel ? 42 : 38) * Y.u
        }
        Text {
            visible: !!panel.note
            width: parent.width
            topPadding: 10 * Y.u
            text: panel.note
            color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            wrapMode: Text.WordWrap
        }
    }
}
