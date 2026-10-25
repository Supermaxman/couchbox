// couchbox: colours, font and sizes shared by the home screen.
pragma Singleton
import QtQuick

QtObject {
    readonly property string font: "Inter"
    readonly property color text: "#f5f6f8"
    readonly property color textDim: Qt.rgba(0.96, 0.965, 0.97, 0.6)
    readonly property color surface: Qt.rgba(1, 1, 1, 0.07)
    readonly property color surfaceFocus: Qt.rgba(1, 1, 1, 0.16)
    readonly property color ring: "#ffffff"
    readonly property int duration: 180
}
