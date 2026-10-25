// The featured banner at the top of the home page: the show's artwork across the screen, its
// logo, description, and Watch / Details. Left / Right at the ends of the buttons (or a
// pause on it) move through the featured shows.
import QtQuick

FocusScope {
    id: hero
    property bool stop: items.length > 0
    property var items: []
    property int at: 0
    readonly property var c: items.length ? items[at % items.length] : ({})
    width: parent ? parent.width : 0
    height: 760 * D.u

    function step(dir) { if (items.length) at = (at + dir + items.length) % items.length; }
    Timer { interval: 9000; repeat: true; running: !hero.activeFocus && hero.items.length > 1; onTriggered: hero.step(1) }

    Image {
        id: art
        anchors.fill: parent
        source: D.img(hero.c.background || hero.c.landscape, 1920, 0)
        sourceSize.width: 1920
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 400 } }
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: Qt.rgba(0, 0, 0, 0.92) }
            GradientStop { position: 0.45; color: Qt.rgba(0, 0, 0, 0.55) }
            GradientStop { position: 0.75; color: Qt.rgba(0, 0, 0, 0.0) }
        }
    }
    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: parent.height * 0.4
        gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: D.bg }
        }
    }

    Column {
        x: D.edge
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 90 * D.u
        width: parent.width * 0.42
        spacing: 26 * D.u
        Image {
            id: logo
            visible: !!hero.c.logo && status === Image.Ready
            source: D.img(hero.c.logo, 720, 0)
            sourceSize.width: 720
            width: Math.min(620 * D.u, implicitWidth)
            height: Math.min(260 * D.u, width * implicitHeight / Math.max(1, implicitWidth))
            fillMode: Image.PreserveAspectFit
            horizontalAlignment: Image.AlignLeft
            asynchronous: true
        }
        Text {
            visible: !logo.visible
            width: parent.width
            text: hero.c.title || ""
            wrapMode: Text.WordWrap
            color: D.text
            font.family: D.font
            font.pixelSize: 64 * D.u
            font.weight: Font.Black
        }
        Text {
            width: parent.width
            text: hero.c.description || ""
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            color: D.text2
            font.family: D.font
            font.pixelSize: 25 * D.u
            lineHeight: 1.2
        }
        Row {
            id: buttons
            spacing: 18 * D.u
            DButton {
                id: watch
                focus: true
                icon: "▶"
                text: hero.c.live ? "Watch Live" : hero.c.kind === "video" ? "Watch" : "Watch Now"
                onClicked: hero.c.kind === "video" ? D.play(hero.c.id) : D.open(Object.assign({autoplay: true}, hero.c))
                KeyNavigation.right: details
            }
            DButton {
                id: details
                visible: hero.c.kind !== "video" || !!hero.c.live
                text: hero.c.live ? "Channel" : "Details"
                onClicked: D.open(hero.c.live ? {kind: "series", id: hero.c.slug} : hero.c)
                KeyNavigation.left: watch
            }
        }
    }
    Keys.onLeftPressed: step(-1)
    Keys.onRightPressed: step(1)

    Row {                                      // which one of the featured
        anchors { right: parent.right; rightMargin: D.edge; bottom: parent.bottom; bottomMargin: 100 * D.u }
        spacing: 12 * D.u
        Repeater {
            model: hero.items.length
            Rectangle {
                required property int index
                width: index === hero.at ? 36 * D.u : 12 * D.u
                height: 12 * D.u
                radius: 6 * D.u
                color: index === hero.at ? D.accent : Qt.rgba(1, 1, 1, 0.4)
                Behavior on width { NumberAnimation { duration: 200 } }
            }
        }
    }
}
