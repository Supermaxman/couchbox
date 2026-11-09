// A list of comments (CommentsPanel's: the comments, or one comment and its replies). The focus
// glides from one to the next and the list follows it, keeping it in the upper part of the
// panel; a comment is the same size focused or not. While a page is on its way, placeholder
// cards breathe where the comments will be.
import QtQuick

ListView {
    id: lv
    property bool live: false                 // the list the keys move
    property bool replies: false              // a comment's replies (indented under it)
    property bool busy: false                 // a page on its way
    property string note: ""                  // nothing to show, and why
    property real pulse: 1                    // the placeholders' breathing (one clock: the panel's)
    property bool focused: false              // the panel has the focus
    visible: opacity > 0
    clip: true
    spacing: 12 * Y.u
    interactive: false
    cacheBuffer: Math.round(height)
    highlight: Item {}
    highlightFollowsCurrentItem: true
    highlightMoveDuration: 220
    highlightMoveVelocity: -1
    highlightResizeDuration: 0
    highlightResizeVelocity: -1
    highlightRangeMode: ListView.ApplyRange
    preferredHighlightBegin: 0
    preferredHighlightEnd: height * 0.72
    delegate: Rectangle {
        id: c
        required property int index
        required property string author
        required property string photo
        required property string text
        required property string time
        required property string likes
        required property int replies
        required property string repliesToken
        required property bool pinned
        required property bool isParent
        readonly property bool on: ListView.isCurrentItem && lv.live && lv.focused
        readonly property bool cut: body.truncated
        readonly property color ink: on ? Y.ink : Y.text
        readonly property color sub: on ? "#606060" : Y.dim
        x: lv.replies && !isParent ? 40 * Y.u : 0     // replies indented under their comment
        width: lv.width - x
        height: col.height + 48 * Y.u
        radius: 16 * Y.u
        color: on ? Y.text : Y.raised
        Behavior on color { ColorAnimation { duration: Y.tFocus } }
        RoundImage { x: 24 * Y.u; y: 24 * Y.u; width: 54 * Y.u; height: width; source: c.photo; fallback: c.author.replace("@", "") }
        Column {
            id: col
            x: 96 * Y.u; y: 24 * Y.u
            width: parent.width - 120 * Y.u
            spacing: 8 * Y.u
            Text {
                width: parent.width
                text: (c.pinned ? "Pinned  ·  " : "") + c.author + "  ·  " + c.time
                color: c.sub; font.family: Y.font; font.pixelSize: 22 * Y.u; font.weight: Font.Medium
                elide: Text.ElideRight
                Behavior on color { ColorAnimation { duration: Y.tFocus } }
            }
            Text {
                id: body
                width: parent.width
                text: c.text
                color: c.ink; font.family: Y.font; font.pixelSize: 25 * Y.u
                // the same lines focused or not (nothing grows under the focus); opened, all of it (its replies: 10)
                wrapMode: Text.Wrap; maximumLineCount: c.isParent ? 18 : lv.replies ? 10 : 5; elide: Text.ElideRight
                lineHeight: 1.1
                Behavior on color { ColorAnimation { duration: Y.tFocus } }
            }
            Row {
                spacing: 20 * Y.u
                visible: !!c.likes || (c.replies > 0 && !c.isParent)
                Row {
                    spacing: 8 * Y.u
                    visible: !!c.likes
                    Icon { name: "like"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim }
                    Text { text: c.likes; color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
                }
                Text { visible: c.replies > 0 && !c.isParent; text: c.replies + (c.replies === 1 ? " reply" : " replies"); color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
            }
        }
    }
    // under the last one: why there's nothing, or placeholders while a page comes
    footer: Column {
        width: lv.width
        topPadding: lv.count ? lv.spacing : 0
        spacing: lv.spacing
        Text {
            visible: !!lv.note
            width: parent.width
            topPadding: 8 * Y.u
            text: lv.note
            color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: lv.busy ? (lv.count > 1 ? 1 : lv.replies ? 2 : 4) : 0
            Rectangle {
                id: ph
                required property int index
                x: lv.replies ? 40 * Y.u : 0
                width: lv.width - x
                height: (index % 2 ? 136 : 168) * Y.u
                radius: 16 * Y.u
                color: Y.raised
                opacity: lv.pulse
                Rectangle { x: 24 * Y.u; y: 24 * Y.u; width: 54 * Y.u; height: width; radius: width / 2; color: Y.raised2 }
                Column {
                    x: 96 * Y.u; y: 30 * Y.u
                    spacing: 16 * Y.u
                    Rectangle { width: 180 * Y.u; height: 16 * Y.u; radius: height / 2; color: Y.raised2 }
                    Rectangle { width: 380 * Y.u; height: 18 * Y.u; radius: height / 2; color: Y.raised2 }
                    Rectangle { visible: ph.index % 2 === 0; width: 290 * Y.u; height: 18 * Y.u; radius: height / 2; color: Y.raised2 }
                }
            }
        }
    }
}
