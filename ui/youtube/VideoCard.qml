// A card, as YouTube's TV app draws it: the thumbnail (rounded, the length bottom right, a red
// bar for what's been watched), then the title and the grey lines under it (the channel; badges
// such as 4K and CC before the views and age). A channel is a round picture with its name
// centred; a game is a box-art poster. `on` draws the white focus ring and the white title.
// boxed: a channel page's card, the title and lines in a panel under the picture that turns white
// with focus.
import QtQuick

Item {
    id: card
    property var item: ({})
    property bool on: false
    property real w: Y.cardW                  // the thumbnail's width (a 16:9 card)
    property bool boxed: false
    readonly property bool box: boxed && !round   // (a channel stays a round picture with its name under it)
    property color behind: Y.bg               // the colour around the card (its rounded corners)
    property bool captioned: true             // the title and lines under it (a hero shelf shows them above)
    property real metaSize: Y.tMeta           // the grey lines (search results: a little smaller)
    readonly property bool overVideo: behind.a === 0 && !round   // nothing behind to paint corners with: a Canvas rounds it
    readonly property string kind: item.type || "video"
    // DeArrow (Settings): its viewers' title and picture in place of YouTube's, when it has them
    property var brand: ({})
    readonly property string title: brand.title || item.title || ""
    readonly property string thumb: brand.thumb || item.thumb || ""
    Component.onCompleted: {
        if (Y.settings.dearrow && (kind === "video" || kind === "live") && item.id)
            Y.call("branding", {id: item.id}, r => { if (card) card.brand = r || {}; }, () => {});
    }
    property bool wide: false                 // drawn 16:9 whatever its shape (a hero shelf's row)
    readonly property string shape: wide ? "wide" : item.shape || "wide"   // wide | poster | square | hero | round
    readonly property bool round: kind === "channel" || shape === "round"
    readonly property real thumbH: Math.round(w * 9 / 16)
    readonly property real artW: round || shape === "square" ? thumbH : kind === "game" || shape === "poster" ? Math.round(thumbH * 0.69) : w
    width: artW
    height: art.height + (box ? panel.height : captioned ? caption.implicitHeight + 26 * Y.u : 0)

    Item {
        id: art
        width: card.artW
        height: card.thumbH
        Rectangle {                          // no picture (yet, or the demo): the title's colours
            anchors.fill: parent
            radius: card.round ? width / 2 : Y.radius
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: Qt.hsla(Y.hue(card.item.title), 0.55, 0.32, 1) }
                GradientStop { position: 1; color: Qt.hsla((Y.hue(card.item.title) + 0.15) % 1, 0.6, 0.14, 1) }
            }
            Text {
                visible: img.status !== Image.Ready && !card.round
                anchors { fill: parent; margins: 26 * Y.u }
                text: card.title
                color: "white"
                font.family: Y.font; font.pixelSize: card.w * 0.075; font.weight: Font.Black
                wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                verticalAlignment: Text.AlignTop
                style: Text.Raised; styleColor: "#60000000"
            }
            Text {
                visible: img.status !== Image.Ready && card.round
                anchors.centerIn: parent
                text: (card.item.title || "?").slice(0, 2)
                color: "white"
                font.family: Y.font; font.pixelSize: parent.height * 0.4; font.weight: Font.Medium
            }
        }
        Image {
            id: img
            anchors.fill: parent
            source: card.thumb
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize: Y.sz(width, height)
            visible: status === Image.Ready && !card.overVideo
        }
        Loader {
            anchors.fill: parent
            active: card.overVideo && !!card.thumb
            sourceComponent: RoundImage { radius: Y.radius; cover: true; source: card.thumb }
        }
        Corners {                            // (over the red bar too: its ends follow the rounding)
            anchors.fill: parent
            z: 1
            r: card.round ? width / 2 : Y.radius
            color: card.behind
            lower: !card.box
            visible: card.behind.a > 0
        }
        Corners {                            // a boxed card's picture: its lower corners rounded over the panel
            anchors.fill: parent
            z: 1
            r: Y.radius
            color: panel.color
            upper: false
            visible: card.box
        }
        Rectangle {                          // the length, bottom right (LIVE in red)
            z: 2
            visible: !!card.item.duration || card.item.live || card.kind === "short"
            anchors { right: parent.right; bottom: parent.bottom; margins: 8 * Y.u; bottomMargin: ((progress.visible ? 10 : 8) + (card.overVideo ? 4 : 0)) * Y.u }
            width: badgeRow.implicitWidth + 16 * Y.u
            height: badge.implicitHeight + 4 * Y.u
            radius: 6 * Y.u
            color: card.item.live ? "#cc0000" : "#cc000000"
            Row {                            // a music video: a note before its length
                id: badgeRow
                anchors.centerIn: parent
                spacing: 4 * Y.u
                Icon { visible: !!card.item.music && !card.item.live; name: "note"; size: 26 * Y.u; color: "white"; anchors.verticalCenter: parent.verticalCenter }
                Icon {                       // a Short: its mark instead of a length
                    visible: card.kind === "short" && !card.item.duration
                    name: "shorts"; filled: true; size: 30 * Y.u; color: "white"; anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    id: badge
                    visible: !!text
                    text: card.item.live ? "LIVE" : card.item.duration || ""
                    color: "white"
                    font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium
                }
            }
        }
        Item {                               // watched so far: solid #FF0033, 5 px, no track (YouTube's cards)
            id: progress
            visible: Y.progressOf(card.item) > 0
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 5 * Y.u
            Rectangle { width: parent.width * Math.min(1, Y.progressOf(card.item)); height: parent.height; color: Y.red }
        }
    }

    // ------------------------------------------------------------------ text
    // the title (two lines, 48 apart), the channel 45 under its last line, and the badges and the
    // views and age 37 under that: badges always sit in a line of text, before it
    Column {
        id: caption
        visible: !card.box && card.captioned
        anchors { left: art.left; top: art.bottom; topMargin: 23 * Y.u }
        width: card.artW
        readonly property var lines: card.item.lines || []
        readonly property var badges: card.item.badges || []
        Text {
            width: parent.width - (card.round ? 0 : 20 * Y.u)   // YouTube's title box stops 20 px short of the picture's edge
            text: card.title
            color: card.on ? Y.text : Y.dim
            font.family: Y.font; font.pixelSize: Y.tTitle; font.weight: Font.DemiBold
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
            horizontalAlignment: card.round ? Text.AlignHCenter : Text.AlignLeft
            lineHeightMode: Text.FixedHeight; lineHeight: Y.tTitleLine
        }
        Item { width: 1; height: 4 * Y.u }
        Repeater {                           // the channel, then the badges and the views and age
            model: caption.lines.length >= 2 ? 2 : caption.lines.length || caption.badges.length ? 1 : 0
            Item {
                id: metaLine
                required property int index
                readonly property int rows: caption.lines.length >= 2 ? 2 : 1
                readonly property bool last: index === rows - 1
                readonly property string line: index === 0 ? caption.lines[0] || "" : caption.lines.slice(1).join(" • ")
                width: caption.width
                height: last ? 34 * Y.u : 37 * Y.u
                Row {
                    height: 34 * Y.u
                    spacing: 8 * Y.u
                    anchors.horizontalCenter: card.round ? parent.horizontalCenter : undefined
                    Repeater {
                        model: metaLine.last ? caption.badges : []
                        Rectangle {
                            required property string modelData
                            width: bt.implicitWidth + 12 * Y.u
                            height: 34 * Y.u
                            radius: 4 * Y.u
                            color: Y.raised
                            Text { id: bt; anchors.centerIn: parent; text: parent.modelData; color: Y.dim; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium }
                        }
                    }
                    Text {
                        width: Math.min(implicitWidth, card.artW - x)
                        height: 34 * Y.u
                        verticalAlignment: Text.AlignVCenter
                        text: metaLine.line
                        color: Y.dim
                        font.family: Y.font; font.pixelSize: card.round ? Y.tSmall + 2 * Y.u : metaLine.index === 0 ? Y.tMeta : card.metaSize
                        elide: Text.ElideRight
                    }
                }
            }
        }
    }
    Rectangle {                              // boxed: the panel under the picture
        id: panel
        visible: card.box
        anchors { left: art.left; right: art.right; top: art.bottom }
        height: 194 * Y.u
        color: card.on ? Y.text : Y.raised
        radius: Y.radius
        Rectangle { width: parent.width; height: parent.radius; color: parent.color }   // square top
        Column {
            anchors { fill: parent; margins: 24 * Y.u; topMargin: 26 * Y.u }
            spacing: 2 * Y.u
            Text {
                width: parent.width
                text: card.title
                color: card.on ? Y.ink : Y.dim
                font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
                elide: Text.ElideRight
            }
            Item { width: 1; height: 36 * Y.u }
            Repeater {                       // the whole title (it's cut short above), then the channel and the rest
                model: [card.title, (card.item.lines || []).join(" • ")].filter(x => !!x)
                Text {
                    required property string modelData
                    width: parent.width
                    text: modelData
                    color: card.on ? "#909090" : "#717171"
                    font.family: Y.font; font.pixelSize: Y.tSmall
                    elide: Text.ElideRight
                }
            }
        }
    }
    Rectangle {                              // a boxed card's focus: white right up to the ring (no dark hairline
        visible: card.on && card.box          // where the panel's rounding and the ring's meet)
        z: -1
        x: -Y.ring; y: -Y.ring
        width: card.artW + 2 * Y.ring
        height: art.height + panel.height + 2 * Y.ring
        radius: Y.radius + Y.ring
        color: Y.text
    }
    Rectangle {                              // the focus ring
        visible: card.on
        x: -Y.ring; y: -Y.ring
        width: card.artW + 2 * Y.ring
        height: (card.box ? art.height + panel.height : art.height) + 2 * Y.ring
        radius: (card.round ? card.thumbH / 2 : Y.radius) + Y.ring
        color: "transparent"
        border.color: Y.text
        border.width: Y.ring
    }
}
