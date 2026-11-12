// Couchbox: the app row of the home screen, in the order chosen in Settings (HomeData, from
// couchboxd). Hold OK (or press Menu) on an app for its options; "Move" lifts it: Left and
// Right carry it, OK drops it, Back puts it back. A glow in the focused app's colour sits behind.
// Moments (Settings → Moments) come first, each a tile that starts it; the first app has the
// focus when the row appears, so Left reaches them.
// Under it, Continue watching (ContinueRow, when there's something to continue): Down reaches it,
// OK plays the card in its app (couchbox-ontv --open), Up or Back return to the apps.
import QtQuick
import QtQuick.Shapes
import QtQuick.Window

import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.bigscreen as Bigscreen


FocusScope {
    id: root

    property Item navigationUp

    // Moving a tile: a local copy of the row while it's carried
    property bool moving: false
    property var order: []
    property int movedFrom: -1
    function startMove() {
        order = HomeData.apps.slice();
        movedFrom = row.currentIndex;
        moving = true;
        row.forceActiveFocus();
    }
    function carry(d) {
        const i = row.currentIndex, j = i + d;
        if (j < 0 || j >= order.length || order[j].hideable === false) return;
        const o = order.slice(); const t = o[i]; o[i] = o[j]; o[j] = t;
        order = o;
        row.currentIndex = j;
        remember();
    }
    function drop(keep) {
        const a = order[row.currentIndex];
        moving = false;
        if (keep && row.currentIndex !== movedFrom) tileMenu.run("couchbox home move " + a.app + " " + (row.currentIndex - root.lead));
        else row.currentIndex = movedFrom;
    }

    readonly property int gap: 22
    // Six tiles fill the width; fewer keep the same size, more scroll.
    readonly property real tileWidth: Math.floor((width - gap * 5) / 6)
    readonly property real tileHeight: Math.round(tileWidth * 9 / 16)

    readonly property var currentApp: row.model[row.currentIndex] || null
    readonly property int lead: HomeData.apps.filter(a => !!a.moment).length    // Moments' tiles, before the apps
    // A new row (an app renamed, a Moment taught) keeps the same tile in focus, else the first app
    property string focusedId: ""                // the tile last moved to (Left, Right)
    function remember() { if (row.model[row.currentIndex]) focusedId = row.model[row.currentIndex].id; }
    readonly property bool hasContinue: continueRow.shown

    // Continue watching: open a card in its app, as a tile would (the app's window to the front if
    // it runs, else its launch screen), and couchbox-ontv takes it to the item.
    function openItem(it) {
        Bigscreen.NavigationSoundEffects.playClickedSound();
        const list = Plasmoid.applicationListModel;
        const a = continueRow.appOf(it.app);
        if (it.desktop && list.isApplicationRunning(it.desktop)) list.maximizeApplication(it.desktop);
        else Plasmoid.showAppLaunchScreen(a ? a.name : it.name, a ? (a.tile || a.icon) : "");
        exec.connectSource("/usr/lib/couchbox/bin/couchbox-ontv --open " + quote(it.target));
    }
    // A Moment's tile: the voice service plays it (couchboxd hands it on), its app comes forward
    function startMoment(id) { exec.connectSource("/usr/bin/couchbox moment start " + quote(id)); }
    function quote(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }
    // The home screen came to the front: focus back where it was, and ask for a fresh
    // Continue watching (something was probably just watched)
    function becameVisible() {
        forceActiveFocus();
        if (HomeData.continueFile) exec.connectSource("/usr/lib/couchbox/bin/couchbox-ontv --refresh");
    }
    P5Support.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source, data) => disconnectSource(source)
    }

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
        model: root.moving ? root.order : HomeData.apps
        onModelChanged: Qt.callLater(() => {
            const i = model.findIndex(a => a.id === root.focusedId);
            currentIndex = i >= 0 ? i : Math.min(root.lead, count - 1);
        })

        delegate: AppTile {
            width: root.tileWidth
            height: root.tileHeight
            app: modelData
            current: ListView.isCurrentItem && row.activeFocus
            dimmed: row.activeFocus && !ListView.isCurrentItem
            lifted: root.moving && ListView.isCurrentItem
            playing: !!modelData.moment && modelData.moment === HomeData.activeMoment
            onOptions: (held) => { if (!root.moving) tileMenu.open(modelData, row, held); }
            onStartMoment: root.startMoment(modelData.moment)
            onDropped: root.drop(true)
        }

        Keys.onUpPressed: (event) => {
            if (root.navigationUp) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                root.navigationUp.forceActiveFocus();
            }
        }
        Keys.onDownPressed: (event) => {
            if (!root.moving && continueRow.shown) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                continueRow.forceActiveFocus();
            }
        }
        Keys.onEscapePressed: (event) => { if (root.moving) root.drop(false); else event.accepted = false; }
        Keys.onBackPressed: (event) => { if (root.moving) root.drop(false); else event.accepted = false; }
        Keys.onLeftPressed: (event) => {
            if (root.moving) return root.carry(-1);
            if (currentIndex > 0) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                decrementCurrentIndex();
                root.remember();
            }
        }
        Keys.onRightPressed: (event) => {
            if (root.moving) return root.carry(1);
            if (currentIndex < count - 1) {
                Bigscreen.NavigationSoundEffects.playMovingSound();
                incrementCurrentIndex();
                root.remember();
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

    ContinueRow {
        id: continueRow
        anchors { left: parent.left; right: parent.right }
        y: row.y + root.tileHeight + 104
        visible: continueRow.shown
        items: HomeData.continueItems
        apps: HomeData.apps
        navigationUp: row
        cardWidth: root.tileWidth
        cardHeight: root.tileHeight
        gap: root.gap
        onOpened: (it) => root.openItem(it)
        onMoved: Bigscreen.NavigationSoundEffects.playMovingSound()
    }

    TileMenu {
        id: tileMenu
        parent: root.Window.contentItem || root
        anchors.fill: parent
        onMoveRequested: root.startMove()
        onStartRequested: if (root.currentApp && root.currentApp.moment) root.startMoment(root.currentApp.moment)
    }
}
