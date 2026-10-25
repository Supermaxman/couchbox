// couchbox: one tile of the home row: the app's artwork (rendered by couchbox-home from
// image/theme/tiles), or its icon and name on a plain card when it has none.
import QtQuick
import QtQuick.Effects

import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.bigscreen as Bigscreen

Item {
    id: tile

    property var app            // {id (desktop file), app, name, icon, tile, glow, hideable} from HomeData
    property bool current: false
    property bool dimmed: false
    property bool lifted: false         // being moved along the row
    signal options()
    signal dropped()

    readonly property real radius: Math.round(width * 0.045)

    z: current ? 1 : 0
    scale: lifted ? 1.18 : current ? 1.1 : 1
    y: lifted ? -24 : 0
    Behavior on y { NumberAnimation { duration: Style.duration } }
    Behavior on scale { NumberAnimation { duration: Style.duration * 1.4; easing.type: Easing.OutCubic } }

    function launch() {
        Bigscreen.NavigationSoundEffects.playClickedSound();
        const list = Plasmoid.applicationListModel;
        if (list.isApplicationRunning(app.id)) {
            list.maximizeApplication(app.id);
        } else {
            Plasmoid.showAppLaunchScreen(app.name, app.tile || app.icon);
            list.runApplication(app.id);
        }
    }

    // OK launches; held for half a second it opens the tile's options (as does Menu).
    // While the tile is being moved, OK drops it instead.
    property bool held: false
    Timer { id: hold; interval: 550; onTriggered: { tile.held = true; tile.options(); } }
    function press(event) {
        if (event.isAutoRepeat) return;
        if (tile.lifted) { tile.dropped(); return; }
        tile.held = false;
        hold.restart();
    }
    function release(event) {
        if (event.isAutoRepeat || tile.lifted) return;
        if (hold.running) { hold.stop(); launch(); }
    }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Select) { press(event); event.accepted = true; }
        else if (event.key === Qt.Key_Menu && !tile.lifted) { tile.options(); event.accepted = true; }
    }
    Keys.onReleased: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Select) { release(event); event.accepted = true; }
    }

    // Soft shadow under the focused tile
    MultiEffect {
        anchors.fill: card
        source: card
        shadowEnabled: true
        shadowColor: "black"
        shadowBlur: 1.0
        shadowVerticalOffset: 10
        shadowOpacity: tile.current ? 0.7 : 0
        Behavior on shadowOpacity { NumberAnimation { duration: Style.duration } }
        visible: shadowOpacity > 0
    }

    Rectangle {
        id: card
        anchors.fill: parent
        radius: tile.radius
        color: "#1d2028"

        Image {
            id: art
            anchors.fill: parent
            source: tile.app.tile ? "file://" + tile.app.tile : ""
            sourceSize.width: 800
            sourceSize.height: 450
            fillMode: Image.PreserveAspectCrop
            smooth: true
            mipmap: true
            visible: status === Image.Ready
        }

        Column {
            anchors.centerIn: parent
            spacing: 8
            visible: !art.visible
            Kirigami.Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                width: tile.height * 0.42
                height: width
                source: tile.app.icon
            }
            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: tile.app.name
                color: Style.text
                font.family: Style.font
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
        }

        // Unfocused tiles sit back a little while the row has focus
        Rectangle {
            anchors.fill: parent
            radius: tile.radius
            color: "black"
            opacity: tile.dimmed ? 0.35 : 0
            Behavior on opacity { NumberAnimation { duration: Style.duration } }
        }
    }

    // Focus ring
    Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        radius: tile.radius + 4
        color: "transparent"
        border.color: Style.ring
        border.width: 2.5
        opacity: tile.current ? 0.95 : 0
        Behavior on opacity { NumberAnimation { duration: Style.duration } }
    }

    Text {
        anchors { top: parent.bottom; topMargin: 14; horizontalCenter: parent.horizontalCenter }
        text: tile.app.name
        color: Style.text
        font.family: Style.font
        font.pixelSize: 14
        font.weight: Font.DemiBold
        opacity: tile.current ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Style.duration } }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {
            tile.ListView.view.currentIndex = index;
            tile.ListView.view.forceActiveFocus();
            tile.launch();
        }
    }
}
