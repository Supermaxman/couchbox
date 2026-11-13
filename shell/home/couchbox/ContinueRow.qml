// couchbox: the Continue watching row under the apps: what's part-watched in Jellyfin, Dropout,
// 2nd Try and Nebula, and followed Twitch channels that are live, newest first (couchbox-ontv
// keeps the list; HomeData reads it). Left and Right move, OK plays it in its app (opened()),
// held for half a second (or Menu) it opens the card's options (options(): Remove, Don't show
// the app here), Up or Back return to the apps. Plain Qt Quick (no Plasma), so couchbox-ontv can draw it off
// screen; Home.qml does the launching and the sounds.
import QtQuick

FocusScope {
    id: root

    property var items: []              // couchbox.ontv items
    property var apps: []               // the home row's apps (HomeData.apps): badges and colours
    property Item navigationUp
    property real cardWidth: 270
    property real cardHeight: 152
    property real gap: 22
    signal opened(var item)
    signal options(var item, bool held)   // held: OK is still down (it opened them)
    signal moved()

    readonly property bool shown: items.length > 0
    readonly property var currentItem: list.currentIndex >= 0 && list.currentIndex < items.length ? items[list.currentIndex] : null
    height: label.height + 22 + cardHeight + 52

    function appOf(id) {
        for (const a of apps) if (a.app === id) return a;
        return null;
    }

    // A fresh list keeps the same card in focus (it may have moved), else the same place;
    // While you were out's or Today at home's card, when it arrives, has the focus (they come first)
    property string focusedKey: ""
    property string hadFirst: ""
    function welcome(x) { return x.key === "away" || x.key === "day"; }
    onItemsChanged: {
        const first = items.length > 0 && welcome(items[0]) ? items[0].key : "";
        if (first && first !== hadFirst) focusedKey = first;
        hadFirst = first;
        let i = items.findIndex(x => x.key === focusedKey);
        if (i < 0) i = Math.min(Math.max(0, list.currentIndex), items.length - 1);
        list.currentIndex = i;
        if (!shown && activeFocus && navigationUp) navigationUp.forceActiveFocus();
    }

    Text {
        id: label
        // only While you were out's or Today at home's cards: the household just came home
        text: root.items.length > 0 && root.items.every(root.welcome) ? "Welcome back" : "Continue watching"
        color: list.activeFocus ? Style.text : Style.textDim
        font.family: Style.font
        font.pixelSize: 19
        font.weight: Font.DemiBold
        Behavior on color { ColorAnimation { duration: Style.duration } }
    }

    ListView {
        id: list
        anchors { top: label.bottom; topMargin: 22; left: parent.left; right: parent.right }
        height: root.cardHeight
        orientation: ListView.Horizontal
        spacing: root.gap
        clip: false
        focus: true
        keyNavigationEnabled: false
        highlightMoveDuration: Style.duration
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 0
        preferredHighlightEnd: width
        boundsBehavior: Flickable.StopAtBounds
        model: root.items
        onCurrentIndexChanged: if (currentIndex >= 0 && currentIndex < root.items.length) root.focusedKey = root.items[currentIndex].key

        delegate: ContinueCard {
            required property var modelData
            required property int index
            width: root.cardWidth
            height: root.cardHeight
            item: modelData
            app: root.appOf(modelData.app)
            current: ListView.isCurrentItem && list.activeFocus
            dimmed: list.activeFocus && !ListView.isCurrentItem
            MouseArea {
                anchors.fill: parent
                onClicked: { list.currentIndex = index; list.forceActiveFocus(); root.opened(modelData); }
            }
        }

        Keys.onLeftPressed: if (currentIndex > 0) { root.moved(); decrementCurrentIndex(); }
        Keys.onRightPressed: if (currentIndex < count - 1) { root.moved(); incrementCurrentIndex(); }
        Keys.onUpPressed: root.leave()
        Keys.onDownPressed: (event) => event.accepted = true
        Keys.onEscapePressed: root.leave()
        Keys.onBackPressed: root.leave()
        // OK plays the card when it's let go; held for half a second it opens the options instead
        Timer { id: hold; interval: 550; onTriggered: if (root.currentItem) root.options(root.currentItem, true) }
        function isOk(key) { return key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Select; }
        Keys.onPressed: (event) => {
            if (isOk(event.key)) {
                event.accepted = true;
                if (!event.isAutoRepeat) hold.restart();
            } else if (event.key === Qt.Key_Menu) {
                event.accepted = true;
                if (root.currentItem) root.options(root.currentItem, false);
            }
        }
        Keys.onReleased: (event) => {
            if (!isOk(event.key) || event.isAutoRepeat) return;
            event.accepted = true;
            if (hold.running) { hold.stop(); if (root.currentItem) root.opened(root.currentItem); }
        }
    }
    function leave() {
        if (!navigationUp) return;
        root.moved();
        navigationUp.forceActiveFocus();
    }

    // More cards off to the right / left
    Repeater {
        model: [true, false]
        Rectangle {
            required property bool modelData       // the left edge
            readonly property bool more: modelData ? list.visibleArea.xPosition > 0.005
                                                   : list.visibleArea.xPosition + list.visibleArea.widthRatio < 0.995
            x: modelData ? -width / 2 : root.width - width / 2
            y: list.y + (root.cardHeight - height) / 2
            width: 46; height: 46; radius: 23
            color: Qt.rgba(0, 0, 0, 0.45)
            border.color: Qt.rgba(1, 1, 1, 0.35)
            border.width: 1
            opacity: more && root.shown ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 200 } }
            Text {
                anchors.centerIn: parent
                anchors.horizontalCenterOffset: parent.modelData ? -2 : 2
                text: parent.modelData ? "‹" : "›"
                color: Style.text
                font.family: Style.font
                font.pixelSize: 34
                font.weight: Font.Light
            }
        }
    }
}
