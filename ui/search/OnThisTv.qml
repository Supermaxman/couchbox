// "On this TV": above Google's results, what the TV's own apps have for the search: Jellyfin's
// library, Dropout, 2nd Try, Nebula, Twitch (channels, live streams, categories), Movies & TV,
// and a card for YouTube's own search (couchbox.ontv, one call per app as they answer). Left and
// Right move, OK opens the card in its app, Up is the toolbar, Down the page, Back as anywhere.
import QtQuick

FocusScope {
    id: strip
    property var items: []                   // couchbox.ontv items, in the apps' order
    property var apps: ({})                  // app id -> {name, glow}
    property int pending: 0                  // apps still looking
    signal opened(var item)
    signal up()
    signal down()
    signal back()

    readonly property bool any: items.length > 0
    readonly property real cardW: 272 * S.u
    readonly property real cardH: 153 * S.u
    height: head.height + 14 * S.u + (any ? cardH + 70 * S.u : 0) + 10 * S.u

    // the same card stays in focus as more apps answer
    property string focusedKey: ""
    onItemsChanged: {
        const i = items.findIndex(x => x.key === focusedKey);
        list.currentIndex = i >= 0 ? i : 0;
        if (!any && activeFocus) down();
    }

    Keys.onUpPressed: up()
    Keys.onDownPressed: down()
    Keys.onEscapePressed: back()
    Keys.onBackPressed: back()

    Row {
        id: head
        spacing: 14 * S.u
        Text {
            text: "On this TV"
            color: strip.activeFocus ? S.focus : S.dim
            font.family: S.font; font.pixelSize: S.tMeta; font.weight: Font.Bold
            font.capitalization: Font.AllUppercase; font.letterSpacing: 2 * S.u
        }
        Text {
            text: strip.pending > 0 ? "Looking in your apps…" : strip.any ? "" : "Nothing in your apps"
            color: S.faint; font.family: S.font; font.pixelSize: S.tMeta
        }
    }

    ListView {
        id: list
        visible: strip.any
        anchors { top: head.bottom; topMargin: 14 * S.u; left: parent.left; right: parent.right }
        height: strip.cardH + 70 * S.u
        orientation: ListView.Horizontal
        spacing: 20 * S.u
        focus: true
        clip: true
        leftMargin: 8 * S.u                      // room for the focused card's ring
        rightMargin: 8 * S.u
        highlightMoveDuration: 160
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 8 * S.u
        preferredHighlightEnd: width - 8 * S.u
        boundsBehavior: Flickable.StopAtBounds
        model: strip.items
        onCurrentIndexChanged: if (currentIndex >= 0 && currentIndex < strip.items.length) strip.focusedKey = strip.items[currentIndex].key
        Keys.onLeftPressed: decrementCurrentIndex()
        Keys.onRightPressed: incrementCurrentIndex()
        Keys.onReturnPressed: if (currentIndex >= 0) strip.opened(strip.items[currentIndex])
        Keys.onEnterPressed: if (currentIndex >= 0) strip.opened(strip.items[currentIndex])

        delegate: Item {
            id: card
            required property var modelData
            required property int index
            readonly property bool sel: ListView.isCurrentItem && strip.activeFocus
            readonly property var app: strip.apps[modelData.app] || {}
            readonly property color tint: app.glow || S.accent
            width: strip.cardW
            height: strip.cardH + 62 * S.u

            Rectangle {
                id: frame
                y: 6 * S.u                       // room for the ring (the list clips)
                width: strip.cardW; height: strip.cardH
                radius: S.radius
                color: S.panel
                clip: true
                Rectangle {                      // no picture: the app's colour and the title
                    anchors.fill: parent
                    visible: art.status !== Image.Ready
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0; color: Qt.darker(card.tint, 2.6) }
                        GradientStop { position: 1; color: Qt.darker(card.tint, 4.2) }
                    }
                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 32 * S.u
                        text: card.modelData.title || ""
                        color: S.text; horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                        font.family: S.font; font.pixelSize: 22 * S.u; font.weight: Font.Bold
                    }
                }
                Image {
                    id: art
                    anchors.fill: parent
                    source: card.modelData.art || ""
                    sourceSize: S.sz(strip.cardW, strip.cardH)
                    asynchronous: true
                    fillMode: card.modelData.fit ? Image.PreserveAspectFit : Image.PreserveAspectCrop
                    visible: status === Image.Ready
                }
                Rectangle {                      // how far along
                    visible: (card.modelData.progress || 0) > 0
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 6 * S.u
                    color: Qt.rgba(0, 0, 0, 0.55)
                    Rectangle { width: parent.width * Math.min(1, card.modelData.progress || 0); height: parent.height; color: Qt.lighter(card.tint, 1.25) }
                }
                Rectangle {                      // the app
                    anchors { left: parent.left; top: parent.top; margins: 10 * S.u }
                    width: appName.implicitWidth + 18 * S.u; height: appName.implicitHeight + 8 * S.u
                    radius: 6 * S.u
                    color: Qt.rgba(0, 0, 0, 0.72)
                    border.color: Qt.lighter(card.tint, 1.2); border.width: 1.5 * S.u
                    Text { id: appName; anchors.centerIn: parent; text: card.modelData.name || ""; color: S.text; font.family: S.font; font.pixelSize: 16 * S.u; font.weight: Font.Bold }
                }
                Rectangle {                      // LIVE (Twitch)
                    visible: !!card.modelData.live
                    anchors { right: parent.right; top: parent.top; margins: 10 * S.u }
                    width: liveText.implicitWidth + 14 * S.u; height: liveText.implicitHeight + 6 * S.u
                    radius: 4 * S.u
                    color: "#eb0400"
                    Text { id: liveText; anchors.centerIn: parent; text: "LIVE"; color: "white"; font.family: S.font; font.pixelSize: 15 * S.u; font.weight: Font.Black }
                }
            }
            Rectangle {                          // focus ring
                anchors.fill: frame; anchors.margins: -S.ring
                radius: S.radius + S.ring
                color: "transparent"
                border.color: S.focus; border.width: S.ring
                visible: card.sel
            }
            Column {
                anchors { top: frame.bottom; topMargin: 10 * S.u; left: parent.left; right: parent.right }
                spacing: 2 * S.u
                Text {
                    width: parent.width
                    text: card.modelData.title || ""
                    color: card.sel ? S.text : S.text2; elide: Text.ElideRight
                    font.family: S.font; font.pixelSize: 21 * S.u; font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: [card.modelData.subtitle, card.modelData.live ? card.modelData.viewers : card.modelData.left].filter(x => !!x).join("  ·  ")
                    color: S.dim; elide: Text.ElideRight
                    font.family: S.font; font.pixelSize: 18 * S.u
                }
            }
        }
    }
}
