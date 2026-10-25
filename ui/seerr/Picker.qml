// A list to choose from (the website's dropdowns): Up/Down move, OK picks, Back closes.
import QtQuick

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
        list.currentIndex = Math.max(0, current);
        list.positionViewAtIndex(list.currentIndex, ListView.Center);
        visible = true;
        list.forceActiveFocus();
    }
    function close() { visible = false; if (returnFocus) returnFocus.forceActiveFocus(); }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0.04, 0.05, 0.09, 0.7) }
    Rectangle {
        anchors.centerIn: parent
        width: 620 * S.u
        height: Math.min(parent.height - 120 * S.u, list.contentHeight + heading.height + 90 * S.u)
        radius: 16 * S.u
        color: S.panel
        border.color: S.line
        border.width: 1
        Text {
            id: heading
            x: 32 * S.u; y: 26 * S.u
            text: picker.title
            color: S.heading
            font.family: S.font
            font.pixelSize: 32 * S.u
            font.weight: Font.Bold
        }
        ListView {
            id: list
            anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; margins: 22 * S.u; topMargin: 18 * S.u }
            clip: true
            model: picker.options
            spacing: 6 * S.u
            highlightMoveDuration: 120
            delegate: Rectangle {
                required property int index
                required property var modelData
                width: list.width
                height: 60 * S.u
                radius: 10 * S.u
                color: ListView.isCurrentItem ? S.indigoDark : "transparent"
                border.color: ListView.isCurrentItem ? S.focus : "transparent"
                border.width: 3 * S.u
                Text {
                    anchors { left: parent.left; leftMargin: 22 * S.u; verticalCenter: parent.verticalCenter }
                    text: modelData
                    color: S.text
                    font.family: S.font
                    font.pixelSize: 24 * S.u
                }
            }
            Keys.onReturnPressed: { const cb = picker.done, i = currentIndex; picker.close(); if (cb) cb(i); }
            Keys.onEnterPressed: { const cb = picker.done, i = currentIndex; picker.close(); if (cb) cb(i); }
        }
    }
}
