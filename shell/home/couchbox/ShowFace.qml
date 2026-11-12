// couchbox: the morning show's tile face (couchbox.show's tile): yesterday's backyard at midday
// (or a clip's still), and over a shade at the bottom its name and its day and length. Without
// a picture, dawn: deep blue into amber with the sun coming up. Plain Qt Quick, so couchbox-ontv
// can draw it off screen.
import QtQuick

Item {
    id: face
    property var show: null              // couchbox.show's tile: {name, subtitle, art}
    property real radius: 12

    Rectangle {                          // dawn, until (or without) the picture
        anchors.fill: parent
        radius: face.radius
        visible: pic.status !== Image.Ready
        clip: true
        gradient: Gradient {
            GradientStop { position: 0; color: "#1b2547" }
            GradientStop { position: 0.62; color: "#7a3f4a" }
            GradientStop { position: 1; color: "#f2a541" }
        }
        Rectangle {                      // the sun, half up
            width: parent.height * 0.7; height: width; radius: width / 2
            x: parent.width * 0.68 - width / 2
            y: parent.height * 0.86 - height / 2
            gradient: Gradient {
                GradientStop { position: 0; color: "#ffe2a1" }
                GradientStop { position: 1; color: "#f7b955" }
            }
            opacity: 0.9
        }
    }
    Rectangle {                          // the picture (as Continue watching's cards)
        anchors.fill: parent
        radius: face.radius
        color: "transparent"
        clip: true
        Image {
            id: pic
            anchors.fill: parent
            source: face.show && face.show.art ? face.show.art : ""
            sourceSize.width: 640
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
            smooth: true
            mipmap: true
        }
    }
    Rectangle {                          // the shade for the words
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: parent.height * 0.7
        radius: face.radius
        gradient: Gradient {
            GradientStop { position: 0; color: "transparent" }
            GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.84) }
        }
    }
    Column {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Math.round(face.height * 0.1) }
        spacing: Math.round(face.height * 0.02)
        Text {
            width: parent.width
            text: face.show ? face.show.name : ""
            color: "white"
            elide: Text.ElideRight
            font.family: "Inter"
            font.pixelSize: Math.round(face.height * 0.19)
            font.weight: Font.Bold
        }
        Text {
            width: parent.width
            text: face.show ? face.show.subtitle || "" : ""
            color: "#ffd89a"
            elide: Text.ElideRight
            font.family: "Inter"
            font.pixelSize: Math.round(face.height * 0.115)
            font.weight: Font.DemiBold
        }
    }
}
