// One camera on the live dashboard: its latest picture, refreshed every couple of seconds
// while it's on screen (two images in turn, so the picture never blanks while the next one
// loads), the name, and a red dot when something is going on there.
import QtQuick

Item {
    id: tile
    property var cam: ({})
    property bool current: false
    property bool refreshing: true
    property int tick: 0
    readonly property bool active: F.isActive(cam.name)
    readonly property string base: demo ? "" : backend.snapshot(cam.name || "", 360)
    property bool showA: true

    function next() {
        if (!base) return;
        const url = base + "&t=" + Date.now();
        if (showA) b.source = url; else a.source = url;
    }
    Timer { interval: 2000; repeat: true; triggeredOnStart: true; running: tile.refreshing && tile.visible && !!tile.base; onTriggered: tile.next() }

    Rectangle {
        id: frame
        anchors.fill: parent
        radius: F.radius
        color: F.panel
        clip: true
        border.color: tile.current ? F.focus : tile.active ? F.alert : F.line
        border.width: (tile.current ? 5 : tile.active ? 3 : 1) * F.u

        Item {
            id: pics
            anchors { fill: parent; margins: frame.border.width }
            Text {                               // no picture yet (or demo)
                anchors.centerIn: parent
                visible: a.status !== Image.Ready && b.status !== Image.Ready
                text: tile.base ? "…" : "▣"
                color: F.panel2; font.pixelSize: 90 * F.u
            }
            Image { id: a; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; cache: false; visible: tile.showA
                    onStatusChanged: if (status === Image.Ready && !tile.showA) tile.showA = true }
            Image { id: b; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; cache: false; visible: !tile.showA
                    onStatusChanged: if (status === Image.Ready && tile.showA) tile.showA = false }
        }
        Rectangle {                              // shade under the name
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: frame.border.width }
            height: 90 * F.u
            gradient: Gradient {
                GradientStop { position: 0; color: "#00000000" }
                GradientStop { position: 1; color: "#cc000000" }
            }
        }
        Row {
            anchors { left: parent.left; bottom: parent.bottom; leftMargin: 22 * F.u; bottomMargin: 16 * F.u }
            spacing: 12 * F.u
            Rectangle {
                visible: tile.active
                anchors.verticalCenter: parent.verticalCenter
                width: 16 * F.u; height: width; radius: width / 2; color: F.alert
                SequentialAnimation on opacity { running: tile.active; loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 700 } NumberAnimation { to: 1; duration: 700 } }
            }
            Text { text: tile.cam.label || ""; color: "white"; font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.DemiBold }
        }
    }
    scale: current ? 1.03 : 1
    z: current ? 2 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
}
