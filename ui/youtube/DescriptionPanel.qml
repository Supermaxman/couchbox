// The Description panel beside the video (YouTube's TV app's): the title, likes / views / date,
// the channel, the description, YouTube's summary, the comments (the first one), and the
// chapters. Up and Down move between them; OK opens the channel, the whole description, the
// comments, or plays from a chapter. Back closes.
import QtQuick

FocusScope {
    id: panel
    property var v: ({})                       // the watch page's video
    property var d: ({})                       // its details (description())
    property var chapters: []                  // [{title, start, thumb}]
    property int index: 0                      // 0 channel, 1 description, 2 summary, 3 comments, 4 chapters
    property int chapter: 0
    property bool expanded: false
    signal openChannel()
    signal openComments()
    signal seekTo(real seconds)
    signal closed()
    x: 1254 * Y.u
    width: 612 * Y.u
    height: parent ? parent.height : 0

    // opening: in from the right; closing: out, quicker
    property bool open: false
    visible: open || opacity > 0
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: panel.open ? Y.tPanel : Y.tOut; easing.type: Easing.OutCubic } }
    transform: Translate {
        x: panel.open ? 0 : 56 * Y.u
        Behavior on x { NumberAnimation { duration: Y.tPanel; easing.type: Easing.OutCubic } }
    }
    readonly property var cards: [true, !!d.text, !!d.summary, !!(d.teaser || d.comments), chapters.length > 0]
    function step(dir) {
        let i = index + dir;
        while (i >= 0 && i < cards.length && !cards[i]) i += dir;
        if (i >= 0 && i < cards.length) index = i;
    }
    Keys.onUpPressed: step(-1)
    Keys.onDownPressed: step(1)
    Keys.onLeftPressed: if (index === 4) chapter = Math.max(0, chapter - 1)
    Keys.onRightPressed: if (index === 4) chapter = Math.min(chapters.length - 1, chapter + 1)
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    Keys.onEscapePressed: { if (expanded) expanded = false; else closed(); }
    Keys.onBackPressed: { if (expanded) expanded = false; else closed(); }
    function activate() {
        if (index === 0) openChannel();
        else if (index === 1 || index === 2) expanded = !expanded;
        else if (index === 3) openComments();
        else if (index === 4 && chapters[chapter]) seekTo(chapters[chapter].start);
    }
    onIndexChanged: if (index !== 1 && index !== 2) expanded = false

    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: col.height + 80 * Y.u
        interactive: false
        clip: false
        // keep the focused card in view
        contentY: {
            const c = [chanCard, descCard, sumCard, comCard, chapCard][panel.index];
            if (!c) return 0;
            const bottom = c.y + c.height + 40 * Y.u;
            return Math.max(0, Math.min(col.height + 80 * Y.u - height, bottom - height + 0));
        }
        Behavior on contentY { NumberAnimation { duration: 160 } }
        Column {
            id: col
            y: 35 * Y.u
            width: panel.width
            spacing: 12 * Y.u
            Text {
                width: parent.width; leftPadding: 24 * Y.u
                text: panel.v.title || ""
                color: Y.text; font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: Font.Bold
                wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
                lineHeightMode: Text.FixedHeight; lineHeight: 48 * Y.u
            }
            Item { width: 1; height: 14 * Y.u }
            Row {                              // 46K Likes · 2,088,453 Views · Nov 4 2026 (188 apart)
                anchors.horizontalCenter: parent.horizontalCenter
                Repeater {
                    model: (panel.d.facts || []).slice(0, 4)
                    Column {
                        required property var modelData
                        width: Math.min(188 * Y.u, panel.width / Math.max(1, Math.min(4, (panel.d.facts || []).length)))
                        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: parent.modelData.value; color: Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Bold; height: 36 * Y.u; verticalAlignment: Text.AlignVCenter }
                        Text { width: parent.width; horizontalAlignment: Text.AlignHCenter; text: parent.modelData.label; color: Y.dim; font.family: Y.font; font.pixelSize: 22 * Y.u; height: 36 * Y.u; verticalAlignment: Text.AlignVCenter }
                    }
                }
            }
            Item { width: 1; height: 10 * Y.u }
            Card {
                id: chanCard
                on: panel.index === 0 && panel.activeFocus
                height: 102 * Y.u
                RoundImage { x: 24 * Y.u; width: 54 * Y.u; height: width; anchors.verticalCenter: parent.verticalCenter; source: panel.v.avatar || ""; fallback: panel.v.channel || "" }
                Text {
                    x: 96 * Y.u; width: parent.width - 170 * Y.u
                    anchors.verticalCenter: parent.verticalCenter
                    text: panel.v.channel || ""
                    color: chanCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                Icon {
                    anchors { right: parent.right; rightMargin: 24 * Y.u; verticalCenter: parent.verticalCenter }
                    name: "chevron"; size: 36 * Y.u; color: chanCard.on ? Y.ink : Y.text
                }
            }
            Card {
                id: descCard
                visible: panel.cards[1]
                on: panel.index === 1 && panel.activeFocus
                height: descCol.height + 48 * Y.u
                Column {
                    id: descCol
                    x: 24 * Y.u; y: 24 * Y.u; width: parent.width - 48 * Y.u
                    spacing: 12 * Y.u
                    Text { text: "Description"; color: descCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 24.5 * Y.u; font.weight: Font.Bold }
                    Text {
                        width: parent.width
                        // folded: its first three lines as running text; opened: as written
                        readonly property bool open: panel.expanded && panel.index === 1
                        text: open ? panel.d.text || "" : (panel.d.text || "").replace(/\s+/g, " ").trim()
                        color: descCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u
                        wrapMode: Text.Wrap; maximumLineCount: open ? 40 : 3; elide: Text.ElideNone   // cut off, no "…"
                        lineHeightMode: Text.FixedHeight; lineHeight: 33 * Y.u
                    }
                }
            }
            Card {
                id: sumCard
                visible: panel.cards[2]
                on: panel.index === 2 && panel.activeFocus
                height: sumCol.height + 48 * Y.u
                Column {
                    id: sumCol
                    x: 24 * Y.u; y: 24 * Y.u; width: parent.width - 48 * Y.u
                    spacing: 12 * Y.u
                    Text { text: "Summary"; color: sumCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Bold }
                    Text {
                        width: parent.width
                        text: panel.d.summary || ""
                        color: sumCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u
                        wrapMode: Text.WordWrap; maximumLineCount: panel.expanded && panel.index === 2 ? 20 : 3; elide: Text.ElideNone   // cut off, no "…" (YouTube's)
                        lineHeightMode: Text.FixedHeight; lineHeight: 33 * Y.u
                    }
                }
                Icon {
                    anchors { right: parent.right; rightMargin: 24 * Y.u; top: parent.top; topMargin: 26 * Y.u }
                    name: "sparkle"; size: 30 * Y.u; color: sumCard.on ? Y.ink : Y.text
                }
            }
            Card {
                id: comCard
                visible: panel.cards[3]
                on: panel.index === 3 && panel.activeFocus
                height: comCol.height + 48 * Y.u
                Column {
                    id: comCol
                    x: 24 * Y.u; y: 24 * Y.u; width: parent.width - 48 * Y.u
                    spacing: 14 * Y.u
                    Row {
                        spacing: 12 * Y.u
                        Text { text: "Comments"; color: comCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Bold }
                        Text { text: panel.d.comments || ""; color: comCard.on ? "#606060" : Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u }
                    }
                    Row {
                        visible: !!panel.d.teaser
                        spacing: 18 * Y.u
                        RoundImage { width: 54 * Y.u; height: width; source: panel.d.teaser ? panel.d.teaser.photo : ""; fallback: panel.d.teaser ? panel.d.teaser.author.replace("@", "") : "" }
                        Text {
                            width: comCol.width - 72 * Y.u
                            textFormat: Text.StyledText
                            text: panel.d.teaser ? "<b>" + Y.html(panel.d.teaser.author) + "</b> • " + Y.html(panel.d.teaser.text) : ""
                            color: comCard.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 25 * Y.u
                            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideNone
                        }
                    }
                }
            }
            Card {
                id: chapCard
                visible: panel.cards[4]
                on: false
                height: 360 * Y.u
                Text { x: 24 * Y.u; y: 24 * Y.u; text: "Chapters"; color: Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Bold }
                ListView {
                    id: chapList
                    x: 24 * Y.u; y: 70 * Y.u
                    width: parent.width - 24 * Y.u; height: 270 * Y.u
                    orientation: ListView.Horizontal
                    spacing: 18 * Y.u
                    interactive: false
                    clip: true
                    model: panel.chapters
                    currentIndex: panel.chapter
                    highlightRangeMode: ListView.ApplyRange
                    preferredHighlightBegin: 0
                    preferredHighlightEnd: 360 * Y.u
                    delegate: Item {
                        required property var modelData
                        required property int index
                        readonly property bool on: panel.index === 4 && panel.chapter === index && panel.activeFocus
                        width: 354 * Y.u; height: 270 * Y.u
                        Rectangle {
                            width: parent.width; height: 199 * Y.u; radius: 14 * Y.u
                            color: Qt.hsla(Y.hue(parent.modelData.title), 0.45, 0.3, 1)
                            border.color: parent.on ? Y.text : "transparent"; border.width: 6 * Y.u
                            Image { anchors { fill: parent; margins: parent.parent.on ? 6 * Y.u : 0 } source: parent.parent.modelData.thumb || ""; fillMode: Image.PreserveAspectCrop; sourceSize: Y.sz(width, height); asynchronous: true }
                        }
                        Text { y: 212 * Y.u; width: parent.width; text: parent.modelData.title; color: parent.on ? Y.text : Y.dim; font.family: Y.font; font.pixelSize: 23 * Y.u; font.weight: Font.Medium; elide: Text.ElideRight }
                        Text { y: 242 * Y.u; text: Y.clock(parent.modelData.start); color: Y.dim; font.family: Y.font; font.pixelSize: 21 * Y.u }
                    }
                }
            }
        }
    }
    component Card: Rectangle {
        property bool on: false                // focused (while the panel has the focus): white
        width: panel.width
        radius: 16 * Y.u
        color: on ? Y.text : Y.raised
    }
}
