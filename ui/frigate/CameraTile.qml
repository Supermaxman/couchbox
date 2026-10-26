// One camera on the live dashboard: its latest picture, refreshed every couple of seconds
// while it's on screen (two images in turn, so the picture never blanks while the next one
// loads), the name, and when something is going on there a red dot and icons for what.
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
        border.color: tile.active ? F.alert : F.line
        border.width: (tile.active ? 3 : 1) * F.u

        Item {
            id: pics
            anchors { fill: parent; margins: frame.border.width }
            Image {                              // no picture yet (or demo)
                anchors.centerIn: parent
                visible: a.status !== Image.Ready && b.status !== Image.Ready
                width: 70 * F.u; height: width; sourceSize: F.sz(width, height)
                source: F.icon("object"); opacity: 0.12
            }
            Image { id: a; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; cache: false; visible: tile.showA
                    sourceSize.width: F.px(tile.width)
                    onStatusChanged: if (status === Image.Ready && !tile.showA) tile.showA = true }
            Image { id: b; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true; cache: false; visible: !tile.showA
                    sourceSize.width: F.px(tile.width)
                    onStatusChanged: if (status === Image.Ready && tile.showA) tile.showA = false }
        }
        Rectangle {                              // shade under the name
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: frame.border.width }
            height: Math.max(90 * F.u, name.implicitHeight * 2.6)
            gradient: Gradient {
                GradientStop { position: 0; color: "#00000000" }
                GradientStop { position: 1; color: "#d0000000" }
            }
        }
        Rectangle {
            id: dot
            visible: tile.active
            x: 22 * F.u; anchors.verticalCenter: name.verticalCenter
            width: 16 * F.u; height: width; radius: width / 2; color: F.alert
            SequentialAnimation on opacity { running: tile.active && tile.visible; loops: Animation.Infinite
                NumberAnimation { to: 0.3; duration: 700 } NumberAnimation { to: 1; duration: 700 } }
        }
        Text {
            id: name
            anchors { left: tile.active ? dot.right : parent.left; leftMargin: tile.active ? 12 * F.u : 22 * F.u
                      right: parent.right; rightMargin: 22 * F.u; bottom: parent.bottom; bottomMargin: 16 * F.u }
            text: tile.cam.label || ""
            elide: Text.ElideRight; maximumLineCount: 1
            color: "white"; font.family: F.font; font.pixelSize: F.tBody + 2 * F.u; font.weight: Font.DemiBold
            style: Text.Raised; styleColor: "#60000000"
        }
        Row {                                    // what's there right now
            anchors { right: parent.right; top: parent.top; margins: 14 * F.u }
            spacing: 8 * F.u
            visible: tile.active
            Repeater {
                model: (F.activeKinds[tile.cam.name] || []).slice(0, 4)
                delegate: KindBadge { required property var modelData; kind: modelData; size: 46 * F.u; fill: "#cc" + F.alert.toString().slice(1) }
            }
        }
    }
    Rectangle {                                  // focus ring
        anchors.fill: parent; anchors.margins: -F.ring
        radius: F.radius + F.ring
        color: "transparent"
        border.color: F.focus; border.width: F.ring
        visible: tile.current
    }
    scale: current ? 1.03 : 1
    z: current ? 2 : 1
    Behavior on scale { NumberAnimation { duration: 120 } }
}
