// A titled row of cards: posters (titles), people (cast, crew, search results) or seasons.
// Left/Right move along it (Left at the start: edgeLeft()), OK opens the card.
import QtQuick

FocusScope {
    id: shelf
    property string title: ""
    property string note: ""
    property var items: []
    property string kind: "poster"           // poster | person | season
    property alias index: list.currentIndex
    signal open(var item)
    signal edgeLeft()
    width: parent ? parent.width : 0
    height: head.height + 18 * M.u + list.height
    visible: items.length > 0

    Row {
        id: head
        spacing: 16 * M.u
        Text { text: shelf.title; color: M.text; font.family: M.font; font.pixelSize: M.tHead; font.weight: Font.Bold }
        Text { visible: !!shelf.note; anchors.baseline: parent.children[0].baseline; text: shelf.note; color: M.faint; font.family: M.font; font.pixelSize: M.tMeta }
    }
    ListView {
        id: list
        anchors { left: parent.left; right: parent.right; top: head.bottom; topMargin: 18 * M.u }
        height: shelf.kind === "person" ? M.personW + 96 * M.u : M.posterH + 90 * M.u
        orientation: ListView.Horizontal
        spacing: M.gap
        clip: false
        focus: true
        model: shelf.items
        cacheBuffer: 1200
        highlightMoveDuration: 160
        preferredHighlightBegin: 0
        preferredHighlightEnd: width - (shelf.kind === "person" ? M.personW : M.posterW) - 40 * M.u
        highlightRangeMode: ListView.ApplyRange
        keyNavigationEnabled: true
        Keys.onLeftPressed: e => { if (currentIndex === 0) { shelf.edgeLeft(); e.accepted = true; } else e.accepted = false; }
        Keys.onReturnPressed: shelf.open(shelf.items[currentIndex])
        Keys.onEnterPressed: shelf.open(shelf.items[currentIndex])
        delegate: Loader {
            id: cell
            required property var modelData
            required property int index
            readonly property bool on: ListView.isCurrentItem && shelf.activeFocus
            y: 6 * M.u
            sourceComponent: shelf.kind === "person" ? personC : posterC
            Component { id: posterC; Poster { item: cell.modelData; on: cell.on; role: cell.modelData.role || ""
                                              rank: cell.modelData.rank || 0 } }
            Component { id: personC; PersonCard { item: cell.modelData; on: cell.on } }
        }
    }
}
