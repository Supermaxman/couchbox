// The guide, left of every page: icons only, and with the focus the full guide with names
// (who's watching at the top; Search, Home, Shorts | Music, Subscriptions, Library | Gaming, News,
// Podcasts, Movies & TV, Live, Sports; Settings at the bottom). Moving through it shows each page
// behind it, as YouTube's TV app does; OK or Right goes into the page.
import QtQuick

FocusScope {
    id: guide
    property var entries: []                  // [{key, label, browse}] (Settings is the last)
    property string section: "home"
    property string who: "Guest"
    readonly property bool open: activeFocus
    readonly property var list: entries.filter(e => e.key !== "settings")
    readonly property int groupEnd1: 2        // dividers after Shorts and after Library
    readonly property int groupEnd2: 5
    signal chosen(string key)                 // moved onto an entry (the page behind follows)
    signal enter()                            // OK / Right: into the page
    width: open ? Y.guideOpen : Y.left
    Behavior on width { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    property int cur: 0                       // -1 who's watching, 0.. the entries, list.length Settings
    function sync() {
        const i = list.findIndex(e => e.key === section);
        cur = section === "settings" ? list.length : Math.max(0, i);
    }
    onActiveFocusChanged: if (activeFocus) sync()
    function keyAt(i) { return i === list.length ? "settings" : i >= 0 && i < list.length ? list[i].key : ""; }
    function move(d) {
        const n = Math.max(-1, Math.min(list.length, cur + d));
        if (n === cur) return;
        cur = n;
        if (n >= 0) pick.restart();
    }
    Timer { id: pick; interval: 260; onTriggered: if (guide.keyAt(guide.cur)) guide.chosen(guide.keyAt(guide.cur)) }
    Keys.onUpPressed: move(-1)
    Keys.onDownPressed: move(1)
    Keys.onRightPressed: activate()
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    function activate() {
        if (cur < 0) { Y.toast("Signing in to YouTube comes in the next update."); return; }
        pick.stop();
        if (keyAt(cur) !== section) chosen(keyAt(cur));
        enter();
    }

    Rectangle {                               // the open guide's panel
        anchors.fill: parent
        color: Y.bg
        opacity: guide.open ? 1 : 0
    }

    // ------------------------------------------------------------------ who's watching
    Item {
        x: 33 * Y.u; y: 62 * Y.u
        width: (guide.open ? 444 * Y.u : 90 * Y.u); height: 78 * Y.u
        Rectangle {
            anchors.fill: parent
            radius: 16 * Y.u
            color: Y.text
            visible: guide.open && guide.cur === -1
        }
        Rectangle {
            id: face
            x: 18 * Y.u
            width: 54 * Y.u; height: width; radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            color: "#3d5afe"
            Icon { anchors.centerIn: parent; name: "person"; size: 36 * Y.u; color: "white" }
        }
        Text {
            visible: guide.open
            x: 90 * Y.u
            anchors.verticalCenter: parent.verticalCenter
            text: guide.who
            color: guide.cur === -1 ? Y.ink : Y.text
            font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
        }
    }

    // ------------------------------------------------------------------ the entries
    Item {
        id: viewport
        y: guide.open ? 154 * Y.u : 195 * Y.u
        width: parent.width
        height: (guide.open ? 930 : 900) * Y.u - y
        clip: true
        Column {
            id: column
            width: parent.width
            // keep the current entry in view while the open guide scrolls
            readonly property real curY: {
                let yy = 0;
                for (let i = 0; i < guide.cur && i < guide.list.length; i++)
                    yy += 78 * Y.u + (guide.open && (i === guide.groupEnd1 || i === guide.groupEnd2) ? 39 * Y.u : 0);
                return yy;
            }
            y: guide.open ? -Math.max(0, curY + 78 * Y.u - viewport.height) : 0
            Behavior on y { NumberAnimation { duration: 140 } }
            Repeater {
                model: guide.list
                Item {
                    id: entry
                    required property var modelData
                    required property int index
                    readonly property bool sel: guide.section === modelData.key
                    readonly property bool on: guide.open && guide.cur === index
                    width: column.width
                    height: 78 * Y.u + (guide.open && (index === guide.groupEnd1 || index === guide.groupEnd2) ? 39 * Y.u : 0)
                    Rectangle {
                        x: 33 * Y.u
                        width: 444 * Y.u; height: 78 * Y.u
                        radius: 16 * Y.u
                        color: Y.text
                        visible: entry.on
                    }
                    Icon {
                        x: 58 * Y.u; y: 19 * Y.u
                        name: entry.modelData.key
                        filled: entry.sel
                        size: 40 * Y.u
                        color: entry.on ? Y.ink : Y.text
                    }
                    Text {
                        visible: guide.open
                        x: 123 * Y.u
                        y: 39 * Y.u - height / 2
                        text: entry.modelData.label
                        color: entry.on ? Y.ink : Y.text
                        font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
                    }
                    Rectangle {                // a divider between the groups
                        visible: guide.open && (entry.index === guide.groupEnd1 || entry.index === guide.groupEnd2)
                        x: 33 * Y.u; y: 78 * Y.u + 18 * Y.u
                        width: 444 * Y.u; height: 3 * Y.u
                        color: Y.raised2
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------ Settings, at the bottom
    Item {
        readonly property bool on: guide.open && guide.cur === guide.list.length
        y: 945 * Y.u
        width: parent.width; height: 78 * Y.u
        Rectangle { x: 33 * Y.u; width: 444 * Y.u; height: parent.height; radius: 16 * Y.u; color: Y.text; visible: parent.on }
        Icon { x: 58 * Y.u; y: 19 * Y.u; name: "settings"; size: 40 * Y.u; color: parent.on ? Y.ink : Y.text }
        Text {
            visible: guide.open
            x: 123 * Y.u; y: 39 * Y.u - height / 2
            text: "Settings"
            color: parent.on ? Y.ink : Y.text
            font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
        }
    }
}
