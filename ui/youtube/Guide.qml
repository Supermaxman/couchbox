// The guide, left of every page: icons only, and with the focus the full guide with names
// (who's watching at the top; Search, Home, Shorts | Music, Subscriptions, Library | Gaming, News,
// Podcasts, Movies & TV, Live, Sports; Settings at the bottom, and at the end of the list when it's
// open). Moving through it shows each page behind it, as YouTube's TV app does; OK or Right goes
// into the page. OK on the picture at the top: who's watching.
import QtQuick

FocusScope {
    id: guide
    objectName: "guide"
    property var entries: []                  // [{key, label, browse}] (Settings is the last)
    property string section: "home"
    readonly property string who: Y.profile ? Y.profile.name : "Guest"
    property bool pinned: false               // Settings: open beside the page, Settings marked
    readonly property bool open: activeFocus || pinned
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
        if (cur < 0) { Y.whoIsWatching(); return; }
        pick.stop();
        // Search always opens on its keys (not the last results), the rest as they are
        if (keyAt(cur) !== section || keyAt(cur) === "search") chosen(keyAt(cur));
        enter();
    }

    Rectangle {                               // the open guide's panel (pinned beside Settings: short of its list at 525)
        width: guide.pinned && !guide.activeFocus ? 500 * Y.u : parent.width
        height: parent.height
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
            visible: guide.activeFocus && guide.cur === -1
        }
        Rectangle {
            id: face
            x: 18 * Y.u
            width: 54 * Y.u; height: width; radius: width / 2
            anchors.verticalCenter: parent.verticalCenter
            color: "#3d5afe"
            Icon { anchors.centerIn: parent; visible: !Y.profile; name: "person"; size: 36 * Y.u; color: "white" }
            RoundImage { anchors.fill: parent; visible: !!Y.profile; source: Y.profile ? Y.profile.photo || "" : ""; fallback: Y.profile ? Y.profile.name : "" }
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
    // Open, the list runs to the bottom of the screen with Settings at its end (48 apart), and
    // scrolls so the focused entry stays about two thirds down (y 700) until the end is in view.
    // Closed, the icons stop above Settings, which sits at the bottom on its own.
    Item {
        id: viewport
        y: guide.open ? 154 * Y.u : 195 * Y.u
        width: parent.width
        height: (guide.open ? 1080 : 900) * Y.u - y
        clip: true
        Column {
            id: column
            width: parent.width
            function topOf(i) {
                let yy = 0;
                for (let k = 0; k < i && k < guide.list.length; k++)
                    yy += 78 * Y.u + (guide.open && (k === guide.groupEnd1 || k === guide.groupEnd2) ? 39 * Y.u : 0);
                return yy + (i >= guide.list.length ? 48 * Y.u : 0);      // Settings, after its gap
            }
            readonly property real full: topOf(guide.list.length) + 78 * Y.u + 58 * Y.u
            // pinned beside Settings: scrolled to its end, Settings in view
            readonly property int at: guide.pinned && !guide.activeFocus ? guide.list.length : guide.cur
            readonly property real curY: topOf(Math.min(at, guide.list.length))
            y: !guide.open || at < 0 ? 0
               : -Math.max(0, Math.min(full - viewport.height, viewport.y + curY + 39 * Y.u - 700 * Y.u))
            Behavior on y { NumberAnimation { duration: 140 } }
            Repeater {
                model: guide.list
                Item {
                    id: entry
                    required property var modelData
                    required property int index
                    readonly property bool sel: guide.section === modelData.key
                    readonly property bool on: guide.activeFocus && guide.cur === index
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
            Item {                             // Settings, the open list's last entry
                visible: guide.open
                width: column.width; height: 48 * Y.u + 78 * Y.u
                SettingsEntry { y: 48 * Y.u }
            }
        }
    }

    // ------------------------------------------------------------------ Settings, at the bottom (closed)
    SettingsEntry { visible: !guide.open; y: 944 * Y.u }

    component SettingsEntry: Item {
        readonly property bool on: guide.activeFocus && guide.cur === guide.list.length
        readonly property bool marked: guide.pinned && !guide.activeFocus
        width: guide.width; height: 78 * Y.u
        Rectangle { x: 33 * Y.u; width: 444 * Y.u; height: parent.height; radius: 16 * Y.u; color: parent.on ? Y.text : Y.raised2; visible: parent.on || parent.marked }
        Icon { x: 58 * Y.u; y: 19 * Y.u; name: "settings"; filled: guide.section === "settings"; size: 40 * Y.u; color: parent.on ? Y.ink : Y.text }
        Text {
            visible: guide.open
            x: 123 * Y.u; y: 39 * Y.u - height / 2
            text: "Settings"
            color: parent.on ? Y.ink : Y.text
            font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium
        }
    }
}
