// Couchbox: options for a home tile (hold OK, or press Menu, on it): move it along the row,
// hide it, or open the app's settings. Changes run the couchbox command, which asks couchboxd.
import QtQuick

import org.kde.plasma.plasma5support as P5Support

FocusScope {
    id: menu
    property var app: null
    property Item returnTo: null
    signal moveRequested()
    visible: false
    z: 50

    readonly property var options: !app ? [] : [
        {label: "Move", act: () => { close(); menu.moveRequested(); }},
        ...(app.hideable === false ? [] : [{label: "Hide from the home screen", act: () => { run("couchbox home hide " + app.app); close(); }}]),
        {label: "More in Settings", act: () => { run("/usr/lib/couchbox/bin/couchbox-settings"); close(); }},
    ]

    function open(a, from) { app = a; returnTo = from; list.currentIndex = 0; visible = true; list.forceActiveFocus(); }
    function close() { visible = false; if (returnTo) returnTo.forceActiveFocus(); }
    function run(cmd) { exec.connectSource(cmd); }

    P5Support.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source, data) => disconnectSource(source)
    }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.55) }
    Rectangle {
        anchors.centerIn: parent
        width: 620
        height: col.height + 60
        radius: 22
        color: "#151922"
        border.color: Qt.rgba(1, 1, 1, 0.12)
        Column {
            id: col
            x: 30; y: 30
            width: parent.width - 60
            spacing: 14
            Text {
                text: menu.app ? menu.app.name : ""
                color: Style.text
                font.family: Style.font; font.pixelSize: 34; font.weight: Font.Bold
            }
            ListView {
                id: list
                width: parent.width
                height: contentHeight
                interactive: false
                spacing: 6
                model: menu.options
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool cur: ListView.isCurrentItem
                    width: list.width; height: 64; radius: 12
                    color: cur ? "#7aa2ff" : "transparent"
                    Text {
                        anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
                        text: modelData.label
                        color: parent.cur ? "#0b0d12" : Style.text
                        font.family: Style.font; font.pixelSize: 26; font.weight: parent.cur ? Font.Bold : Font.Normal
                    }
                }
                Keys.onReturnPressed: menu.options[currentIndex].act()
                Keys.onEnterPressed: menu.options[currentIndex].act()
            }
        }
    }
}
