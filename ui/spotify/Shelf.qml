// A titled row of cards (Recently played, Made for you, Albums...). Left/Right move, OK opens,
// Menu shows actions; Left on the first card goes to the sidebar (leftEdge).
import QtQuick

FocusScope {
    id: shelf
    property string title: ""
    property var items: []
    property int idx: 0
    property real cardW: 250 * S.u
    signal leftEdge()
    signal chosen(var item)
    visible: items.length > 0
    implicitHeight: visible ? head.implicitHeight + 18 * S.u + list.height : 0
    onItemsChanged: idx = Math.min(idx, Math.max(0, items.length - 1))

    Keys.onLeftPressed: { if (idx > 0) idx--; else leftEdge(); }
    Keys.onRightPressed: idx = Math.min(items.length - 1, idx + 1)
    Keys.onReturnPressed: chosen(items[idx])
    Keys.onEnterPressed: chosen(items[idx])
    Keys.onMenuPressed: S.menu(items[idx], null)

    Text {
        id: head
        text: shelf.title
        color: S.text; font.family: S.font; font.pixelSize: S.tHead; font.weight: Font.Bold
    }
    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: head.bottom; topMargin: 18 * S.u }
        height: (currentItem ? currentItem.implicitHeight : shelf.cardW * 1.3) + 16 * S.u
        orientation: ListView.Horizontal
        spacing: 22 * S.u
        clip: false
        model: shelf.items
        currentIndex: shelf.idx
        highlightMoveDuration: 160
        preferredHighlightBegin: 0
        preferredHighlightEnd: width - shelf.cardW - 40 * S.u
        highlightRangeMode: ListView.ApplyRange
        interactive: false
        delegate: Card {
            required property var modelData
            required property int index
            width: shelf.cardW
            y: 8 * S.u
            item: modelData
            current: shelf.activeFocus && index === shelf.idx
        }
    }
}
