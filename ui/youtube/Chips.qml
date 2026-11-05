// A row of searches as pills (under search results: the suggestions for what was searched).
// OK searches for the chip.
import QtQuick

FocusScope {
    id: chips
    property var chips: []
    property real indent: Y.left
    width: parent ? parent.width : 0
    height: 72 * Y.u
    ListView {
        id: list
        anchors.fill: parent
        orientation: ListView.Horizontal
        spacing: 26 * Y.u
        focus: true
        clip: false
        interactive: false
        model: chips.chips
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: chips.indent
        preferredHighlightEnd: width * 0.7
        header: Item { width: chips.indent; height: 1 }
        highlightMoveDuration: 180
        Keys.onLeftPressed: e => { if (currentIndex === 0) Y.toGuide(); else decrementCurrentIndex(); }
        Keys.onRightPressed: incrementCurrentIndex()
        Keys.onReturnPressed: Y.search(chips.chips[currentIndex])
        Keys.onEnterPressed: Y.search(chips.chips[currentIndex])
        delegate: Rectangle {
            required property string modelData
            readonly property bool on: ListView.isCurrentItem && chips.activeFocus
            width: label.implicitWidth + 68 * Y.u
            height: 72 * Y.u
            radius: height / 2
            color: on ? Y.text : "transparent"
            border.color: on ? Y.text : Y.raised2
            border.width: 3 * Y.u
            Text {
                id: label
                anchors.centerIn: parent
                text: parent.modelData
                color: parent.on ? Y.ink : Y.text
                font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium
            }
        }
    }
}
