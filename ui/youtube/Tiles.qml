// Library's row of coloured tiles (History, Watch later, Playlists, Music, Movies & TV, Podcasts).
// OK opens the tile's list.
import QtQuick

FocusScope {
    id: tiles
    property var tiles: []
    property real indent: Y.left
    width: parent ? parent.width : 0
    height: 213 * Y.u                         // the tiles (168) and room under them, as YouTube's
    Item {                                    // cut at the guide's rail (x 130): tiles scrolled left don't show under it
        id: cut
        x: tiles.indent - 26 * Y.u
        y: -2 * Y.ring
        width: tiles.width - x
        height: 168 * Y.u + 4 * Y.ring
        clip: true
    ListView {
        id: list
        x: -cut.x
        y: 2 * Y.ring
        width: tiles.width
        height: 168 * Y.u
        orientation: ListView.Horizontal
        spacing: 36 * Y.u
        focus: true
        clip: false
        interactive: false
        model: tiles.tiles
        highlightRangeMode: ListView.StrictlyEnforceRange
        preferredHighlightBegin: tiles.indent
        preferredHighlightEnd: tiles.indent + 300 * Y.u
        highlightMoveDuration: 180
        Keys.onLeftPressed: e => { if (currentIndex === 0) Y.toGuide(); else decrementCurrentIndex(); }
        Keys.onRightPressed: incrementCurrentIndex()
        Keys.onReturnPressed: Y.openList(tiles.tiles[currentIndex].title, tiles.tiles[currentIndex].id)
        Keys.onEnterPressed: Y.openList(tiles.tiles[currentIndex].title, tiles.tiles[currentIndex].id)
        delegate: Item {
            id: tile
            required property var modelData
            readonly property bool on: ListView.isCurrentItem && tiles.activeFocus
            width: 300 * Y.u; height: 168 * Y.u
            Rectangle {
                anchors.fill: parent
                radius: Y.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: tile.modelData.colors[0] }
                    GradientStop { position: 1; color: tile.modelData.colors[1] }
                }
            }
            Text {
                x: 24 * Y.u; y: parent.height - height - 22 * Y.u
                text: parent.modelData.title
                color: "white"
                font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
            }
            Rectangle {
                visible: parent.on
                anchors { fill: parent; margins: -Y.ring }
                radius: Y.radius + Y.ring
                color: "transparent"
                border.color: Y.text; border.width: Y.ring
            }
        }
    }
    }
}
