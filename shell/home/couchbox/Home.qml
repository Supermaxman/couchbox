// couchbox: the app row of the home screen, from /etc/couchbox/home.tsv (apps.js, written by
// couchbox-home), always in that order. A soft glow in the focused app's colour sits behind it.
import QtQuick
import QtQuick.Shapes

import org.kde.bigscreen as Bigscreen

import "apps.js" as Apps

FocusScope {
    id: root

    property Item navigationUp

    readonly property int gap: 22
    // Six tiles fill the width; fewer keep the same size, more scroll.
    readonly property real tileWidth: Math.floor((width - gap * 5) / 6)
    readonly property real tileHeight: Math.round(tileWidth * 9 / 16)

    readonly property var currentApp: Apps.apps[row.currentIndex] || null

    // Glow behind the focused tile, in its app's colour (data-couchbox-glow in the tile SVG).
    Shape {
        id: glow
        readonly property real radius: root.tileWidth * 2.6
        readonly property real centerX: row.currentItem ? row.currentItem.x - row.contentX + root.tileWidth / 2 : 0
        property color color: root.currentApp && root.currentApp.glow ? root.currentApp.glow : "#7aa2ff"
        Behavior on color { ColorAnimation { duration: 450 } }
        x: centerX - radius
        y: row.y + root.tileHeight / 2 - radius
        width: radius * 2
        height: radius * 2
        Behavior on x { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }
        opacity: row.activeFocus ? 0.32 : 0.14
        Behavior on opacity { NumberAnimation { duration: 300 } }
        preferredRendererType: Shape.CurveRenderer

        ShapePath {
            strokeWidth: -1
            fillGradient: RadialGradient {
                centerX: glow.radius; centerY: glow.radius
                centerRadius: glow.radius
                focalX: glow.radius; focalY: glow.radius
                GradientStop { position: 0; color: glow.color }
                GradientStop { position: 0.35; color: Qt.rgba(glow.color.r, glow.color.g, glow.color.b, 0.35) }
                GradientStop { position: 1; color: "transparent" }
            }
            PathRectangle { x: 0; y: 0; width: glow.width; height: glow.height }
        }
    }

    ListView {
        id: row
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: root.tileHeight
        orientation: ListView.Horizontal
        spacing: root.gap
        clip: false
        focus: true
        keyNavigationEnabled: true
        highlightMoveDuration: Style.duration
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: width
        boundsBehavior: Flickable.StopAtBounds
        model: Apps.apps

        delegate: AppTile {
            width: root.tileWidth
            height: root.tileHeight
            app: modelData
            current: ListView.isCurrentItem && row.activeFocus
            dimmed: row.activeFocus && !ListView.isCurrentItem
        }

        Keys.onUpPressed: (event) => {
            if (root.navigationUp) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                root.navigationUp.forceActiveFocus();
            }
        }
        Keys.onDownPressed: (event) => event.accepted = true
        Keys.onLeftPressed: (event) => {
            if (currentIndex > 0) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                decrementCurrentIndex();
            }
        }
        Keys.onRightPressed: (event) => {
            if (currentIndex < count - 1) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                incrementCurrentIndex();
            }
        }
    }

    // More apps off to the side: an arrow at that edge, and a dot per app under the row
    component More: Rectangle {
        // an inline component can't see this file's ids: the row and tile height come in
        property ListView list
        property real tileHeight
        property bool start: false          // the left edge
        readonly property bool more: !!list && (start ? list.visibleArea.xPosition > 0.005
                                                      : list.visibleArea.xPosition + list.visibleArea.widthRatio < 0.995)
        y: list ? list.y + (tileHeight - height) / 2 : 0
        width: 54; height: 54; radius: 27
        color: Qt.rgba(0, 0, 0, 0.45)
        border.color: Qt.rgba(1, 1, 1, 0.35)
        border.width: 1
        opacity: more ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            anchors.centerIn: parent
            anchors.horizontalCenterOffset: parent.start ? -2 : 2
            text: parent.start ? "‹" : "›"
            color: Style.text
            font.family: Style.font
            font.pixelSize: 40
            font.weight: Font.Light
        }
    }
    More { list: row; tileHeight: root.tileHeight; start: true; x: -width / 2 }
    More { list: row; tileHeight: root.tileHeight; x: root.width - width / 2 }

    Row {
        visible: row.count > 1 && row.contentWidth > row.width + 2
        anchors.horizontalCenter: parent.horizontalCenter
        y: row.y + root.tileHeight + 74
        spacing: 10
        Repeater {
            model: row.count
            Rectangle {
                required property int index
                readonly property bool here: index === row.currentIndex
                width: here ? 26 : 8
                height: 8
                radius: 4
                color: here ? Style.text : Style.textDim
                opacity: here ? 1 : 0.6
                Behavior on width { NumberAnimation { duration: Style.duration } }
            }
        }
    }
}
