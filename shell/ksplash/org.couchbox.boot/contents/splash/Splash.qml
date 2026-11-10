// Couchbox: the Plasma splash, drawn exactly where the boot screen (system/plymouth/couchbox)
// left off: same logo, same bar, same line, so the hand-over from boot to Home doesn't show.
// The boot screen stops its bar at 85 %; Plasma's start-up stages fill the rest.
import QtQuick

Rectangle {
    id: root
    color: "#0b0d12"
    property int stage

    // the boot screen's layout: drawn at 3840x2160, scaled to fit, centred
    readonly property real s: Math.min(width / 3840, height / 2160)
    readonly property real top: (height - 2160 * s) / 2
    function px(v) { return Math.round(v * s) }

    property real progress: 0.85 + 0.15 * Math.min(stage, 6) / 6
    Behavior on progress { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }

    Image {
        source: "images/logo.png"
        width: px(300); height: px(270)
        smooth: true
        x: (root.width - width) / 2
        y: root.top + px(760) - height / 2
    }

    Rectangle {
        id: track
        width: px(720); height: px(10); radius: height / 2
        x: (root.width - width) / 2
        y: root.top + px(1080)
        color: Qt.rgba(1, 1, 1, 0.12)

        Item {
            width: track.width * root.progress; height: track.height
            clip: true
            Rectangle {
                width: track.width; height: track.height; radius: track.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: "#7aa2ff" }
                    GradientStop { position: 1; color: "#a98bff" }
                }
            }
        }
    }

    Text {
        text: "Starting Couchbox…"
        font.family: "Inter"
        font.pixelSize: root.px(60)
        color: "#f5f6f8"
        opacity: 0.72
        anchors.horizontalCenter: parent.horizontalCenter
        y: root.top + px(1130)
        renderType: Text.NativeRendering
    }
}
