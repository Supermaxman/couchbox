// A channel's section in search results, as YouTube's TV app lays it out: on the left the
// channel's pill over one large card (its title and lines on the picture), on the right a pill
// ("Recently uploaded") over list cards two to a column (the picture, then the title and lines
// beside it). Left / Right move between the large card and the columns, Up / Down within a
// column; the columns scroll left under the focus. OK opens, held (or Menu) the card's menu.
import QtQuick

FocusScope {
    id: cl
    property var row: ({})                    // {cluster: {hero: {pill, items}, list: {pill, items}}}
    property real indent: Y.left
    property real topPad: 0
    readonly property var hero: ((row.cluster || {}).hero || {})
    readonly property var list: ((row.cluster || {}).list || {})
    readonly property var heroItem: (hero.items || [])[0] || null
    readonly property var items: list.items || []
    property int cur: heroItem ? 0 : 1        // 0 the large card, 1.. the list's cards
    readonly property int col: cur > 0 ? Math.floor((cur - 1) / 2) : -1
    readonly property real heroW: 843 * Y.u
    readonly property real colW: 816 * Y.u
    readonly property real colGap: 24 * Y.u
    signal open(var item)
    width: parent ? parent.width : 0
    height: topPad + 90 * Y.u + 474 * Y.u
    Behavior on topPad { NumberAnimation { duration: 180 } }

    function current() { return cur === 0 ? heroItem : items[cur - 1]; }
    Keys.onPressed: e => {
        const k = e.key;
        if (k === Qt.Key_Left) {
            if (cur === 0) Y.toGuide();
            else if (col === 0) { if (heroItem) cur = 0; else Y.toGuide(); }
            else cur = Math.max(1, cur - 2);
        } else if (k === Qt.Key_Right) {
            if (cur === 0) { if (items.length) cur = 1; }
            else if (cur + 2 <= items.length) cur += 2;
            else if (col < Math.floor((items.length - 1) / 2)) cur = items.length;
        } else if (k === Qt.Key_Up && cur > 0 && (cur - 1) % 2 === 1) {
            cur--;
        } else if (k === Qt.Key_Down && cur > 0 && (cur - 1) % 2 === 0 && cur < items.length) {
            cur++;
        } else if (k === Qt.Key_Menu) {
            Y.cardMenu(current(), cl);
        } else if (k === Qt.Key_Return || k === Qt.Key_Enter) {
            if (!e.isAutoRepeat) hold.restart();
        } else {
            e.accepted = false;
            return;
        }
        e.accepted = true;
    }
    Keys.onReleased: e => {
        if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && !e.isAutoRepeat && hold.running) {
            hold.stop();
            open(current());
            e.accepted = true;
        }
    }
    Timer { id: hold; interval: 650; onTriggered: Y.cardMenu(cl.current(), cl) }

    // the columns past the first scroll left under the focus (the large card goes with them)
    Item {
        id: content
        x: cl.indent - (cl.col > 0 ? cl.col * (cl.colW + cl.colGap) + cl.heroW + cl.colGap : 0)
        y: cl.topPad
        Behavior on x { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        // what's scrolled past the left is gone (the guide is there), as on YouTube's TV app
        Pill { visible: !!cl.heroItem && cl.col <= 0; pill: cl.hero.pill || ({}) }
        Item {                                 // the large card
            id: big
            visible: !!cl.heroItem && cl.col <= 0
            y: 90 * Y.u
            width: cl.heroW; height: 474 * Y.u
            readonly property var it: cl.heroItem || ({})
            Rectangle {
                anchors.fill: parent
                radius: Y.radius
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: Qt.hsla(Y.hue(big.it.title), 0.55, 0.32, 1) }
                    GradientStop { position: 1; color: Qt.hsla((Y.hue(big.it.title) + 0.15) % 1, 0.6, 0.14, 1) }
                }
            }
            Image {
                anchors.fill: parent
                source: big.it.thumb || ""
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                sourceSize: Y.sz(width, height)
            }
            Rectangle {                        // the bottom darkens under the title
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: parent.height * 0.6
                gradient: Gradient {
                    GradientStop { position: 0; color: "transparent" }
                    GradientStop { position: 1; color: "#e6000000" }
                }
            }
            Corners { anchors.fill: parent; r: Y.radius; color: Y.bg }
            Column {
                x: 30 * Y.u
                anchors { bottom: parent.bottom; bottomMargin: 26 * Y.u }
                width: parent.width - 60 * Y.u - dur.width
                Text {
                    width: parent.width
                    text: big.it.title || ""
                    color: cl.activeFocus && cl.cur === 0 ? Y.text : Y.soft
                    font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
                    wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                    lineHeightMode: Text.FixedHeight; lineHeight: Y.tTitleLine
                }
                Item { width: 1; height: 4 * Y.u }
                MetaRow { width: parent.width; badges: big.it.badges || []; text: (big.it.lines || []).join(" • ") }
            }
            Text {
                id: dur
                visible: !!big.it.duration
                anchors { right: parent.right; rightMargin: 36 * Y.u; bottom: parent.bottom; bottomMargin: 30 * Y.u }
                text: big.it.duration || ""
                color: Y.text
                font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium
            }
            Rectangle {                        // watched so far
                visible: (big.it.progress || 0) > 0
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 6 * Y.u
                color: "#66ffffff"
                Rectangle { width: parent.width * Math.min(1, big.it.progress || 0); height: parent.height; color: Y.red }
            }
            Ring { visible: cl.activeFocus && cl.cur === 0 }
        }

        Item {                                 // the list, in columns of two
            x: cl.heroItem ? cl.heroW + cl.colGap : 0
            Pill { x: Math.max(0, cl.col) * (cl.colW + cl.colGap); pill: cl.list.pill || ({}) }
            Repeater {
                model: cl.items
                Item {
                    id: lc
                    required property var modelData
                    required property int index
                    readonly property bool on: cl.activeFocus && cl.cur === index + 1
                    x: Math.floor(index / 2) * (cl.colW + cl.colGap)
                    visible: Math.floor(index / 2) >= cl.col
                    y: 90 * Y.u + (index % 2) * 249 * Y.u
                    width: cl.colW; height: 224 * Y.u
                    Rectangle { anchors.fill: parent; radius: Y.radius; color: Y.raised }
                    Item {
                        x: 18 * Y.u; y: 18 * Y.u
                        width: 336 * Y.u; height: 189 * Y.u
                        Rectangle {
                            anchors.fill: parent
                            radius: 12 * Y.u
                            color: Qt.hsla(Y.hue(lc.modelData.title), 0.5, 0.28, 1)
                        }
                        Image {
                            anchors.fill: parent
                            source: lc.modelData.thumb || ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            sourceSize: Y.sz(width, height)
                        }
                        Corners { anchors.fill: parent; r: 12 * Y.u; color: Y.raised }
                        Rectangle {
                            visible: !!lc.modelData.duration
                            anchors { right: parent.right; bottom: parent.bottom; margins: 8 * Y.u }
                            width: ld.implicitWidth + 14 * Y.u; height: ld.implicitHeight + 4 * Y.u; radius: 6 * Y.u
                            color: "#cc000000"
                            Text { id: ld; anchors.centerIn: parent; text: lc.modelData.duration || ""; color: "white"; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
                        }
                        Rectangle {
                            visible: (lc.modelData.progress || 0) > 0
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                            height: 5 * Y.u
                            color: "#66ffffff"
                            Rectangle { width: parent.width * Math.min(1, lc.modelData.progress || 0); height: parent.height; color: Y.red }
                        }
                    }
                    Column {
                        x: 378 * Y.u; y: 28 * Y.u
                        width: parent.width - x - 24 * Y.u
                        Text {
                            width: parent.width
                            text: lc.modelData.title || ""
                            color: lc.on ? Y.text : Y.soft
                            font.family: Y.font; font.pixelSize: 34 * Y.u; font.weight: Font.Bold
                            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
                            lineHeightMode: Text.FixedHeight; lineHeight: Y.tTitleLine
                        }
                        Text {
                            width: parent.width
                            height: 40 * Y.u
                            verticalAlignment: Text.AlignVCenter
                            text: (lc.modelData.lines || [])[0] || ""
                            color: Y.dim
                            font.family: Y.font; font.pixelSize: 24 * Y.u
                            elide: Text.ElideRight
                        }
                        MetaRow { width: parent.width; badges: lc.modelData.badges || []; text: (lc.modelData.lines || []).slice(1).join(" • ") }
                    }
                    Ring { visible: lc.on }
                }
            }
        }
    }

    // the pill over each side: the channel (its picture) or a search ("Recently uploaded")
    component Pill: Rectangle {
        property var pill: ({})
        readonly property bool face: !!pill.avatar || (pill.target || {}).type === "channel"
        height: 72 * Y.u
        width: pr.implicitWidth + 48 * Y.u
        radius: height / 2
        color: Y.glass
        Row {
            id: pr
            anchors { left: parent.left; leftMargin: parent.face ? 10 * Y.u : 26 * Y.u; verticalCenter: parent.verticalCenter }
            spacing: 14 * Y.u
            RoundImage {
                visible: parent.parent.face
                width: 52 * Y.u; height: width
                anchors.verticalCenter: parent.verticalCenter
                source: parent.parent.pill.avatar || ""
                fallback: parent.parent.pill.title || ""
            }
            Icon {
                visible: !parent.parent.face
                name: parent.parent.pill.icon === "search" ? "search" : "history"
                size: 36 * Y.u
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: parent.parent.pill.title || ""
                color: Y.text
                font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
    // badges, then the line they belong to
    component MetaRow: Row {
        property var badges: []
        property string text: ""
        height: 34 * Y.u
        spacing: 8 * Y.u
        Repeater {
            model: parent.badges
            Rectangle {
                required property string modelData
                width: mb.implicitWidth + 12 * Y.u; height: 34 * Y.u; radius: 4 * Y.u
                color: "#33ffffff"
                Text { id: mb; anchors.centerIn: parent; text: parent.modelData; color: Y.soft; font.family: Y.font; font.pixelSize: 24 * Y.u; font.weight: Font.Medium }
            }
        }
        Text {
            width: Math.max(0, parent.width - x)
            height: 34 * Y.u
            verticalAlignment: Text.AlignVCenter
            text: parent.text
            color: Y.dim
            font.family: Y.font; font.pixelSize: 24 * Y.u
            elide: Text.ElideRight
        }
    }
    component Ring: Rectangle {
        x: -Y.ring; y: -Y.ring
        width: parent.width + 2 * Y.ring; height: parent.height + 2 * Y.ring
        radius: Y.radius + Y.ring
        color: "transparent"
        border.color: Y.text; border.width: Y.ring
    }
}
