// A list of comments (CommentsPanel's: the comments, or one comment's own page: it whole on the
// page with its Like, Dislike and Report buttons, then YouTube's "Open the YouTube mobile app"
// row, then its replies; laid out as YouTube's TV app's, measured in VacuumTube).
// The focus glides from one to the next and the list follows it, keeping it in the upper part of
// the panel; a comment is the same size focused or not (the open one's buttons take the focus,
// not the comment). While a page is on its way, placeholder cards breathe where the comments will be.
import QtQuick

ListView {
    id: lv
    property bool live: false                 // the list the keys move
    property bool replies: false              // a comment's replies (indented under it)
    property bool busy: false                 // a page on its way
    property string note: ""                  // nothing to show, and why
    property real pulse: 1                    // the placeholders' breathing (one clock: the panel's)
    property bool focused: false              // the panel has the focus
    property int button: 0                    // the open comment's button with the focus: 0 Like, 1 Dislike, 2 Report
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
        required property string kind             // comment | handoff (YouTube's "Open the YouTube mobile app..." row)
        required property string author
        required property string photo
        required property string text
        required property string time
        required property string likes
        required property int replies
        required property string repliesToken
        required property bool pinned
        required property bool isParent
        required property string vote             // like | dislike | "" (this profile's)
        readonly property bool handoff: kind === "handoff"
        readonly property bool here: ListView.isCurrentItem && lv.live && lv.focused
        readonly property bool on: here && !isParent  // (the open comment: its buttons have the focus, not it)
        readonly property bool cut: body.truncated
        readonly property color ink: on ? Y.ink : Y.text
        readonly property color sub: on ? "#606060" : Y.dim
        width: lv.width
        height: handoff ? 104 * Y.u : col.height + (isParent ? 60 : 48) * Y.u   // (the open comment: room under its buttons, as YouTube's)
        radius: 16 * Y.u
        color: isParent ? "transparent" : on ? Y.text : Y.raised   // the open comment: on the page, not a card (YouTube's)
        Behavior on color { ColorAnimation { duration: Y.tFocus } }

        // the handoff row: your picture, YouTube's words, the linked-TV mark
        RoundImage {
            visible: c.handoff
            x: 24 * Y.u; anchors.verticalCenter: parent.verticalCenter; width: 54 * Y.u; height: width
            source: (Y.profile || {}).photo || ""; fallback: ((Y.profile || {}).name || "You")
        }
        Text {
            visible: c.handoff
            x: 96 * Y.u; width: parent.width - 180 * Y.u; anchors.verticalCenter: parent.verticalCenter
            text: c.text
            color: c.ink; font.family: Y.font; font.pixelSize: 24 * Y.u; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
        }
        Icon { visible: c.handoff; anchors { right: parent.right; rightMargin: 24 * Y.u; verticalCenter: parent.verticalCenter } name: "linked-tv"; size: 40 * Y.u; color: c.ink }

        // a comment: the picture and who, when; the words under them, full width; the likes and replies
        Column {
            id: col
            visible: !c.handoff
            x: 24 * Y.u; y: 24 * Y.u
            width: parent.width - 48 * Y.u
            spacing: 14 * Y.u
            Row {
                spacing: 24 * Y.u
                RoundImage { width: 54 * Y.u; height: width; source: c.photo; fallback: c.author.replace("@", "") }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: col.width - 78 * Y.u
                    text: (c.pinned ? "Pinned  ·  " : "") + c.author + "  ·  " + c.time
                    color: c.sub; font.family: Y.font; font.pixelSize: 23 * Y.u; font.weight: Font.Medium
                    elide: Text.ElideRight
                    Behavior on color { ColorAnimation { duration: Y.tFocus } }
                }
            }
            Text {
                id: body
                width: parent.width
                text: c.text
                color: c.isParent ? "#dddddd" : c.ink; font.family: Y.font; font.pixelSize: 25 * Y.u
                // the same lines focused or not (nothing grows under the focus); opened, all of it (its replies: 10)
                wrapMode: Text.Wrap; maximumLineCount: c.isParent ? 18 : lv.replies ? 10 : 5; elide: Text.ElideRight
                lineHeight: 1.1
                Behavior on color { ColorAnimation { duration: Y.tFocus } }
            }
            Row {
                spacing: 24 * Y.u
                visible: !c.isParent && (!!c.likes || !!c.vote || c.replies > 0)
                Row {
                    spacing: 8 * Y.u
                    visible: !!c.likes || c.vote === "like"
                    Icon { name: c.vote === "like" ? "like-filled" : "like"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: c.likes; color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; anchors.verticalCenter: parent.verticalCenter }
                }
                Icon { visible: c.vote === "dislike"; name: "dislike-filled"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim }
                Row {                              // its replies: the speech bubble and the count (YouTube's)
                    spacing: 8 * Y.u
                    visible: c.replies > 0
                    Icon { name: "comments"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: Y.count(c.replies); color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; anchors.verticalCenter: parent.verticalCenter }
                }
            }
            // the open comment: Like, Dislike and Report under it, round, as YouTube's TV app has them
            Row {
                visible: c.isParent
                topPadding: 6 * Y.u
                spacing: 12 * Y.u
                Vote { icon: c.vote === "like" ? "like-filled" : "like"; on: c.here && lv.button === 0; objectName: "commentLike" }
                Vote { icon: c.vote === "dislike" ? "dislike-filled" : "dislike"; on: c.here && lv.button === 1; objectName: "commentDislike" }
                Vote { icon: "flag"; on: c.here && lv.button === 2; objectName: "commentReport" }
            }
        }
    }
    // a round button under the open comment: an icon on a faint circle, white with the focus
    component Vote: Rectangle {
        id: vb
        property string icon
        property bool on: false
        width: 72 * Y.u
        height: width
        radius: width / 2
        color: on ? Y.text : "#1fffffff"
        Behavior on color { ColorAnimation { duration: Y.tFocus } }
        Icon { anchors.centerIn: parent; name: vb.icon; size: 34 * Y.u; color: vb.on ? Y.ink : Y.text; weight: 1.6 }
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
