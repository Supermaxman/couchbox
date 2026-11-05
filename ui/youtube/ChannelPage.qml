// A channel: its name, its picture and name in a pill with the description beside it, then its
// shelves of boxed cards (For you, Videos, Shorts, its playlists). The guide gives way to a back
// button (Left from the first card); Back goes back.
import QtQuick

FocusScope {
    id: page
    property string channelId: ""
    property var head: ({})
    property bool loaded: false
    property string problem: ""
    readonly property string label: head.title || ""
    signal closed()

    Component.onCompleted: load()
    function load() {
        Y.call("channel", {id: channelId}, r => {
            loaded = true;
            head = r.header || {};
            feed.setPage(r);
            if (feed.count) feed.forceActiveFocus(); else backButton.forceActiveFocus();
        }, e => { loaded = true; problem = e; backButton.forceActiveFocus(); });
    }
    onActiveFocusChanged: if (activeFocus && !feed.activeFocus && !backButton.activeFocus) (feed.count ? feed : backButton).forceActiveFocus()
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()

    Text {
        x: Y.left; y: 52 * Y.u
        text: page.head.title || ""
        color: Y.text
        font.family: Y.font; font.pixelSize: 44 * Y.u; font.weight: Font.Bold
    }
    Rectangle {
        id: pill
        x: Y.left; y: 120 * Y.u
        visible: !!page.head.title
        height: 72 * Y.u
        width: pillRow.implicitWidth + 44 * Y.u
        radius: height / 2
        color: Y.raised
        Row {
            id: pillRow
            x: 8 * Y.u
            anchors.verticalCenter: parent.verticalCenter
            spacing: 14 * Y.u
            RoundImage {
                width: 56 * Y.u; height: width
                anchors.verticalCenter: parent.verticalCenter
                source: page.head.avatar || ""
                fallback: page.head.title || ""
            }
            Text { text: page.head.title || ""; color: Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
        }
    }
    Text {
        anchors { left: pill.right; leftMargin: 48 * Y.u; verticalCenter: pill.verticalCenter }
        width: page.width - x - 108 * Y.u
        text: page.head.description || (page.head.lines || []).join(" • ")
        color: Y.text
        font.family: Y.font; font.pixelSize: 24 * Y.u
        elide: Text.ElideRight
    }
    Feed {
        id: feed
        y: 205 * Y.u
        width: parent.width
        height: parent.height - y
        boxed: true
        onOpen: it => Y.open(it)
    }
    Connections {                             // Left off the first card: the back button, not the guide
        target: Y
        enabled: page.activeFocus
        function onToGuide() { backButton.forceActiveFocus(); }
    }
    Rectangle {
        id: backButton
        x: 42 * Y.u; y: 504 * Y.u
        width: 72 * Y.u; height: width; radius: width / 2
        color: activeFocus ? Y.text : Y.raised
        Icon { anchors.centerIn: parent; name: "back"; size: 40 * Y.u; color: backButton.activeFocus ? Y.ink : Y.text }
        Keys.onReturnPressed: page.closed()
        Keys.onEnterPressed: page.closed()
        Keys.onRightPressed: if (feed.count) feed.forceActiveFocus()
    }
    Text {
        visible: !page.loaded || !!page.problem
        x: Y.left; y: 260 * Y.u
        text: page.problem || ""
        color: Y.dim
        font.family: Y.font; font.pixelSize: Y.tMeta
    }
}
