// couchbox: one tile of the home row: the app's artwork (rendered by couchbox-home from
// image/theme/tiles), or its icon and name on a plain card when it has none. A Moment's tile
// (app.moment: Settings → Moments) shows what it plays, its name and its app; OK starts it.
// The morning show's (app.show: couchbox.show) shows its picture and day (ShowFace); OK opens it.
import QtQuick
import QtQuick.Effects

import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.bigscreen as Bigscreen

Item {
    id: tile

    property var app            // {id (desktop file), app, name, icon, tile, glow, hideable} from HomeData
                                // (a Moment: {moment, name, title, art, plays, badge, glow})
    property bool playing: false        // a Moment's: it's the one playing now
    property bool current: false
    property bool dimmed: false
    property bool lifted: false         // being moved along the row
    signal options(bool held)           // held: OK is still down (it opened them)
    signal dropped()
    signal startMoment()
    signal startShow()
    readonly property bool isMoment: !!(app && app.moment)
    readonly property bool isShow: !!(app && app.show)

    readonly property real radius: Math.round(width * 0.045)

    // OK is down on it: it dips a little at once (the press is felt before the app shows), and
    // comes back as OK is let go, or as its options open
    property bool pressed: false
    onCurrentChanged: if (!current) pressed = false

    z: current ? 1 : 0
    scale: lifted ? 1.18 : current ? (pressed ? 1.05 : 1.1) : 1
    y: lifted ? -24 : 0
    Behavior on y { NumberAnimation { duration: Style.duration } }
    Behavior on scale { NumberAnimation { duration: tile.pressed ? Style.pressDuration : Style.duration * 1.25; easing.type: Easing.OutCubic } }

    function launch() {
        if (isShow) { startShow(); return; }       // (Home.qml opens it, with the sound)
        Bigscreen.NavigationSoundEffects.playClickedSound();
        if (isMoment) { startMoment(); return; }
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
    Timer { id: hold; interval: 550; onTriggered: { tile.pressed = false; tile.held = true; tile.options(true); } }
    function press(event) {
        if (event.isAutoRepeat) return;
        if (tile.lifted) { tile.dropped(); return; }
        tile.held = false;
        tile.pressed = true;
        hold.restart();
    }
    function release(event) {
        if (event.isAutoRepeat || tile.lifted) return;
        tile.pressed = false;
        if (hold.running) { hold.stop(); launch(); }
    }
    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Select) { press(event); event.accepted = true; }
        else if (event.key === Qt.Key_Menu && !tile.lifted) { tile.options(false); event.accepted = true; }
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
            visible: !art.visible && !tile.isMoment && !tile.isShow
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

        Loader {
            anchors.fill: parent
            active: tile.isMoment
            sourceComponent: momentFace
        }
        ShowFace {
            anchors.fill: parent
            visible: tile.isShow
            show: tile.isShow ? tile.app : null
            radius: tile.radius
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
        width: Math.min(implicitWidth, tile.width)
        elide: Text.ElideRight
        text: tile.isMoment ? (tile.app.title || "") : tile.app.name
        color: Style.text
        font.family: Style.font
        font.pixelSize: 14
        font.weight: Font.DemiBold
        opacity: tile.current && !tile.isShow ? 1 : 0        // (the show's face says it)
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

    // A Moment: its picture (or its app's colour), its name, its app's tile small, and Playing
    Component {
        id: momentFace
        Item {
            readonly property color tint: tile.app.glow || "#7aa2ff"
            Rectangle {
                anchors.fill: parent
                radius: tile.radius
                visible: pic.status !== Image.Ready
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.darker(tint, 2.2) }
                    GradientStop { position: 1; color: Qt.darker(tint, 4.0) }
                }
            }
            Image {
                id: pic
                anchors.fill: parent
                source: tile.app.art || ""
                sourceSize.width: 640
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
                smooth: true
                mipmap: true
                visible: false
            }
            // rounded like the card, with a shade at the bottom for the name
            Rectangle { id: picMask; anchors.fill: parent; radius: tile.radius; visible: false; layer.enabled: true }
            MultiEffect {
                anchors.fill: parent
                source: pic
                maskEnabled: true
                maskSource: picMask
                visible: pic.status === Image.Ready
            }
            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: parent.height * 0.62
                radius: tile.radius
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 1; color: Qt.rgba(0, 0, 0, 0.82) }
                }
            }
            Text {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Math.round(parent.height * 0.1) }
                text: tile.app.name
                color: "white"
                elide: Text.ElideRight
                maximumLineCount: 2
                wrapMode: Text.WordWrap
                font.family: Style.font
                font.pixelSize: Math.round(parent.height * 0.19)
                font.weight: Font.Bold
            }
            Rectangle {                     // the app it plays in: its tile, small
                anchors { left: parent.left; top: parent.top; margins: 8 }
                width: 56; height: 32
                radius: 5
                color: Qt.rgba(0, 0, 0, 0.7)
                border.color: Qt.rgba(1, 1, 1, 0.3)
                border.width: 1
                clip: true
                visible: badgeArt.status === Image.Ready
                Image {
                    id: badgeArt
                    anchors.fill: parent
                    anchors.margins: 1
                    source: tile.app.badge ? "file://" + tile.app.badge : ""
                    sourceSize.width: 160
                    fillMode: Image.PreserveAspectCrop
                    smooth: true
                    mipmap: true
                }
            }
            Rectangle {                     // the one playing now
                anchors { right: parent.right; top: parent.top; margins: 8 }
                visible: tile.playing
                width: playingText.implicitWidth + 16
                height: playingText.implicitHeight + 6
                radius: height / 2
                color: tint
                Text {
                    id: playingText
                    anchors.centerIn: parent
                    text: "Playing"
                    color: "#0b0d12"
                    font.family: Style.font
                    font.pixelSize: 12
                    font.weight: Font.Bold
                }
            }
        }
    }
}
