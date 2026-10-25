// A list to choose from: Up/Down move, OK picks, Back closes.
import QtQuick
import QtQuick.Window

FocusScope {
    id: picker
    visible: false
    z: 60
    property string title: ""
    property var options: []
    property var done: null
    property var returnFocus: null

    function open(t, opts, current, cb) {
        title = t; options = opts; done = cb;
        returnFocus = Window.activeFocusItem;
        let i = opts.findIndex(o => o.value === current);
        list.currentIndex = Math.max(0, i);
        visible = true;
        list.forceActiveFocus();
        list.positionViewAtIndex(list.currentIndex, ListView.Center);
    }
    function close() { visible = false; if (returnFocus) returnFocus.forceActiveFocus(); }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.02, 0.03, 0.05, 0.75) }
    Rectangle {
        anchors.centerIn: parent
        width: 760 * T.u
        height: Math.min(parent.height - 140 * T.u, list.contentHeight + heading.height + 100 * T.u)
        radius: 22 * T.u
        color: T.panel
        border.color: T.line
        Text {
            id: heading
            x: 40 * T.u; y: 32 * T.u
            width: parent.width - 80 * T.u
            text: picker.title
            color: T.text
            elide: Text.ElideRight
            font.family: T.font; font.pixelSize: 32 * T.u; font.weight: Font.Bold
        }
        ListView {
            id: list
            anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; margins: 24 * T.u }
            clip: true
            model: picker.options
            spacing: 6 * T.u
            highlightMoveDuration: 100
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool cur: ListView.isCurrentItem
                width: list.width
                height: 70 * T.u
                radius: 12 * T.u
                color: cur ? T.accent : "transparent"
                Text {
                    anchors { left: parent.left; leftMargin: 24 * T.u; right: parent.right; rightMargin: 24 * T.u; verticalCenter: parent.verticalCenter }
                    text: modelData.label
                    color: parent.cur ? T.accentInk : T.text
                    elide: Text.ElideRight
                    font.family: T.font; font.pixelSize: 26 * T.u; font.weight: parent.cur ? Font.Bold : Font.Normal
                }
            }
            Keys.onReturnPressed: choose()
            Keys.onEnterPressed: choose()
            function choose() {
                const o = picker.options[currentIndex];
                const cb = picker.done;
                picker.close();
                if (o && cb) cb(o.value);
            }
        }
    }
}
