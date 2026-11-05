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
    signal picked(int index)
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0
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
        y: panel.avatar || panel.name ? 36 * Y.u : 40 * Y.u
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
        }
        Text {
            visible: !!panel.subtitle
            width: parent.width
            text: panel.subtitle
            color: Y.dim; font.family: Y.font; font.pixelSize: 30 * Y.u
            wrapMode: Text.WordWrap
            lineHeight: 1.1
        }
        Item { width: 1; height: (panel.name ? 18 : 30) * Y.u }
        Repeater {
            model: panel.options
            Rectangle {
                id: opt
                required property var modelData
                required property int index
                readonly property bool on: panel.index === index && panel.activeFocus
                width: panel.width
                height: (panel.name ? 96 : 90) * Y.u
                radius: 16 * Y.u
                color: on ? Y.text : Y.raised
                Icon {
                    id: oi
                    visible: !!opt.modelData.icon
                    x: 30 * Y.u
                    anchors.verticalCenter: parent.verticalCenter
                    name: opt.modelData.icon || ""
                    size: 38 * Y.u
                    color: opt.on ? Y.ink : Y.text
                }
                Text {
                    anchors { left: parent.left; leftMargin: opt.modelData.icon ? 96 * Y.u : 24 * Y.u; right: parent.right; rightMargin: 84 * Y.u; verticalCenter: parent.verticalCenter }
                    text: opt.modelData.label
                    color: opt.on ? Y.ink : Y.text
                    font.family: Y.font; font.pixelSize: 31 * Y.u; font.weight: Font.Medium
                    elide: Text.ElideRight
                }
                Text {
                    visible: !!opt.modelData.value
                    anchors { right: parent.right; rightMargin: 28 * Y.u; verticalCenter: parent.verticalCenter }
                    text: opt.modelData.value || ""
                    color: opt.on ? "#606060" : Y.dim
                    font.family: Y.font; font.pixelSize: 26 * Y.u
                }
                Icon {
                    visible: !!opt.modelData.checked || !!opt.modelData.trailing
                    anchors { right: parent.right; rightMargin: 28 * Y.u; verticalCenter: parent.verticalCenter }
                    name: opt.modelData.trailing || "check"
                    size: 38 * Y.u
                    color: opt.on ? Y.ink : Y.text
                }
            }
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
