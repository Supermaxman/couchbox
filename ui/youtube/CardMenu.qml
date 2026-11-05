// A card's menu (hold OK, or the Menu key, on a card): Play next, Add to queue, Save to Watch later,
// Go to channel. Up and Down move, OK picks, Back closes.
import QtQuick

FocusScope {
    id: menu
    objectName: "cardmenu"
    property var item: null
    property int index: 0
    property var returnFocus: null
    readonly property var options: {
        const o = [];
        if (!item) return o;
        if (item.type === "video" || item.type === "live") {
            o.push({key: "next", label: "Play next", icon: "next"});
            o.push({key: "queue", label: "Add to queue", icon: "list"});
            o.push({key: "later", label: "Save to Watch later", icon: "history"});
        }
        if (item.channelId) o.push({key: "channel", label: "Go to channel", icon: "person"});
        return o;
    }
    signal picked(string key, var item)
    function open(it, back) {
        item = it; index = 0; returnFocus = back;
        if (!options.length) return;
        visible = true;
        forceActiveFocus();
    }
    function close() { visible = false; if (returnFocus) returnFocus.forceActiveFocus(); }
    visible: false
    z: 150
    Keys.onUpPressed: index = Math.max(0, index - 1)
    Keys.onDownPressed: index = Math.min(options.length - 1, index + 1)
    Keys.onReturnPressed: { const k = options[index].key, it = item; close(); picked(k, it); }
    Keys.onEnterPressed: { const k = options[index].key, it = item; close(); picked(k, it); }
    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()
    Keys.onLeftPressed: {}
    Keys.onRightPressed: {}
    Rectangle { anchors.fill: parent; color: "#cc000000" }
    Column {
        anchors.centerIn: parent
        width: 700 * Y.u
        spacing: 14 * Y.u
        Text {
            width: parent.width
            text: menu.item ? menu.item.title : ""
            color: Y.text; font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            bottomPadding: 18 * Y.u
        }
        Repeater {
            model: menu.options
            Rectangle {
                required property var modelData
                required property int index
                readonly property bool on: menu.index === index
                width: parent.width; height: 84 * Y.u; radius: 16 * Y.u
                color: on ? Y.text : Y.raised
                Icon { x: 28 * Y.u; anchors.verticalCenter: parent.verticalCenter; name: parent.modelData.icon; size: 36 * Y.u; color: parent.on ? Y.ink : Y.text }
                Text { x: 90 * Y.u; anchors.verticalCenter: parent.verticalCenter; text: parent.modelData.label; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium }
            }
        }
    }
}
