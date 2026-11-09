// A list of comments (CommentsPanel's: the comments, or one comment's own page: it whole, with
// its Like and Dislike buttons and YouTube's line on replying from the phone, then its replies).
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
    property int button: 0                    // the open comment's button with the focus: 0 Like, 1 Dislike
    property string handoff: ""               // YouTube's line under them (adding comments and replies: the phone)
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
        required property string vote             // like | dislike | "" (this profile's)
        readonly property bool here: ListView.isCurrentItem && lv.live && lv.focused
        readonly property bool on: here && !isParent  // (the open comment: its buttons have the focus, not it)
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
                visible: !c.isParent && (!!c.likes || !!c.vote || c.replies > 0)
                Row {
                    spacing: 8 * Y.u
                    visible: !!c.likes || c.vote === "like"
                    Icon { name: c.vote === "like" ? "like-filled" : "like"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim }
                    Text { text: c.likes; color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
                }
                Icon { visible: c.vote === "dislike"; name: "dislike-filled"; size: 26 * Y.u; color: c.on ? Y.ink : Y.dim }
                Text { visible: c.replies > 0; text: c.replies + (c.replies === 1 ? " reply" : " replies"); color: c.on ? Y.ink : Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u }
            }
            // the open comment: Like (with the likes) and Dislike, as YouTube's TV app has them under it
            Row {
                visible: c.isParent
                topPadding: 10 * Y.u
                spacing: 16 * Y.u
                Vote { icon: c.vote === "like" ? "like-filled" : "like"; label: c.likes; on: c.here && lv.button === 0; objectName: "commentLike" }
                Vote { icon: c.vote === "dislike" ? "dislike-filled" : "dislike"; on: c.here && lv.button === 1; objectName: "commentDislike" }
            }
            // ... and under them, YouTube's line on adding comments and replies (with your picture)
            Row {
                visible: c.isParent
                topPadding: 14 * Y.u
                spacing: 14 * Y.u
                RoundImage { width: 36 * Y.u; height: width; source: (Y.profile || {}).photo || ""; fallback: ((Y.profile || {}).name || "You"); anchors.verticalCenter: parent.verticalCenter }
                Text {
                    width: col.width - 50 * Y.u
                    text: lv.handoff || "Open the YouTube mobile app to add comments and replies."
                    color: Y.dim; font.family: Y.font; font.pixelSize: 21 * Y.u
                    wrapMode: Text.Wrap
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }
    // a button under the open comment: an icon (and the likes) on a faint pill, white with the focus
    component Vote: Rectangle {
        id: vb
        property string icon
        property string label: ""
        property bool on: false
        width: label ? vrow.width + 48 * Y.u : height
        height: 64 * Y.u
        radius: height / 2
        color: on ? Y.text : "#1fffffff"
        Behavior on color { ColorAnimation { duration: Y.tFocus } }
        Row {
            id: vrow
            anchors.centerIn: parent
            spacing: 10 * Y.u
            Icon { name: vb.icon; size: 32 * Y.u; color: vb.on ? Y.ink : Y.text; weight: 1.6; anchors.verticalCenter: parent.verticalCenter }
            Text {
                visible: !!vb.label
                text: vb.label
                color: vb.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
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
