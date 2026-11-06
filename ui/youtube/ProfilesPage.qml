// "Who's watching": every signed-in channel as a round picture (the focused one larger, with its
// @handle, YouTube Premium and a gear for signing out), then Add account, and Watch as guest
// under the row. As YouTube's TV app shows it at start.
import QtQuick

FocusScope {
    id: page
    objectName: "profiles"
    property var profiles: []
    property string current: ""
    property int index: 0
    property string area: "row"               // row | gear | guest | menu
    property int menuIndex: 0
    readonly property int count: profiles.length + 1        // + Add account
    readonly property bool onAdd: index === profiles.length
    readonly property var focused: onAdd ? null : profiles[index]
    function focusDetail() { return {count: profiles.length, brands: profiles.filter(p => !!p.pageId).length, index: index, area: area,
                                      id: onAdd ? "add" : (focused ? focused.id : "")}; }
    signal chosen(var profile)                // null: watch as a guest
    signal addAccount()
    signal signOut(var profile)
    signal closed()

    function load(focusId) {
        Y.call("profiles", {}, r => {
            const all = r.profiles || [];
            const last = r.last || r.current || "";       // the one last watched as comes first (YouTube's order)
            const k = all.findIndex(p => p.id === last);
            page.profiles = k > 0 ? [all[k]].concat(all.slice(0, k), all.slice(k + 1)) : all;
            const i = page.profiles.findIndex(p => p.id === (focusId || last));
            page.index = Math.max(0, i);
            page.area = "row";
            list.currentIndex = page.index;
            list.positionViewAtIndex(page.index, ListView.Beginning);
        });
    }

    Keys.onPressed: e => {
        const k = e.key;
        if (k === Qt.Key_Escape || k === Qt.Key_Back) {
            if (area === "menu") area = "gear"; else closed();
        } else if (area === "menu") {
            if (k === Qt.Key_Up || k === Qt.Key_Down) menuIndex = 1 - menuIndex;
            else if (k === Qt.Key_Return || k === Qt.Key_Enter) { if (menuIndex === 0) signOut(focused); area = "row"; }
            else return;
        } else if (k === Qt.Key_Left) {
            if (area === "row" && index > 0) { index--; list.currentIndex = index; }
        } else if (k === Qt.Key_Right) {
            if (area === "row" && index < count - 1) { index++; list.currentIndex = index; }
        } else if (k === Qt.Key_Down) {
            area = area === "row" && !onAdd ? "gear" : "guest";
        } else if (k === Qt.Key_Up) {
            area = area === "guest" && !onAdd ? "gear" : "row";
        } else if (k === Qt.Key_Return || k === Qt.Key_Enter) {
            if (area === "guest") chosen(null);
            else if (area === "gear") { area = "menu"; menuIndex = 0; }
            else if (onAdd) addAccount();
            else chosen(focused);
        } else {
            return;
        }
        e.accepted = true;
    }

    // ------------------------------------------------------------------ the backdrop
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: "#120d0e" }
            GradientStop { position: 0.6; color: "#1a0e11" }
            GradientStop { position: 1; color: "#221013" }
        }
    }
    Repeater {                                 // rounded blobs, bottom right (soft gradients, drawn here)
        model: [{x: 1380, y: 700, w: 560, h: 560, r: -20, a: "#d04a6a", b: "#6a1428", k: "petal"},
                {x: 1660, y: 800, w: 420, h: 420, r: 25, a: "#e8789a", b: "#a0244a", k: "petal"},
                {x: 1060, y: 900, w: 980, h: 300, r: -12, a: "#c8405a", b: "#4a0c1c", k: "ribbon"}]
        Image {
            required property var modelData
            x: modelData.x * Y.u; y: modelData.y * Y.u
            width: modelData.w * Y.u; height: modelData.h * Y.u
            sourceSize: Y.sz(width, height)
            rotation: modelData.r
            opacity: 0.7
            smooth: true
            source: "data:image/svg+xml;utf8," + encodeURIComponent(
                "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' preserveAspectRatio='none'>"
                + "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='" + modelData.a + "'/>"
                + "<stop offset='1' stop-color='" + modelData.b + "'/></linearGradient></defs><path fill='url(#g)' d='"
                + (modelData.k === "petal" ? "M52 3C78 4 97 24 96 50S74 98 46 96 3 74 4 48 26 2 52 3Z"     // a rounded blob
                                           : "M8 52C10 30 34 18 56 22S96 36 94 58 66 90 42 86 6 74 8 52Z")
                + "'/></svg>")
        }
    }
    Logo {
        anchors.horizontalCenter: parent.horizontalCenter
        y: 146 * Y.u
    }

    // ------------------------------------------------------------------ the row
    ListView {
        id: list
        x: 0; y: 300 * Y.u
        width: parent.width
        height: 520 * Y.u
        orientation: ListView.Horizontal
        interactive: false
        spacing: 55 * Y.u
        model: page.count
        highlightRangeMode: ListView.ApplyRange
        preferredHighlightBegin: 95 * Y.u
        preferredHighlightEnd: parent.width - 420 * Y.u
        highlightMoveDuration: 200
        header: Item { width: 95 * Y.u; height: 1 }
        delegate: Item {
            id: cell
            required property int index
            readonly property bool add: index === page.profiles.length
            readonly property var p: add ? ({}) : page.profiles[index]
            readonly property bool on: page.index === index && page.activeFocus
            readonly property real d: on ? 342 * Y.u : 296 * Y.u
            width: 296 * Y.u                   // the focused one grows past its cell (the next one stays put)
            height: list.height
            Item {
                id: face
                width: cell.d; height: cell.d
                anchors.horizontalCenter: parent.horizontalCenter
                y: (cell.on ? 15 : 54) * Y.u
                Rectangle {                    // the white ring around the focused one
                    anchors { fill: parent; margins: -2 * Y.u }
                    radius: width / 2
                    color: Y.text
                    visible: cell.on && page.area === "row"
                }
                RoundImage {
                    anchors { fill: parent; margins: cell.on && page.area === "row" ? 8 * Y.u : 0 }
                    visible: !cell.add
                    source: cell.p.photo || ""
                    fallback: cell.p.name || ""
                }
                Rectangle {
                    visible: cell.add
                    anchors { fill: parent; margins: cell.on && page.area === "row" ? 8 * Y.u : 0 }
                    radius: width / 2
                    color: "#3b272c"                 // opaque: inside the white ring when focused, the plus still shows
                    Rectangle { anchors.centerIn: parent; width: parent.width * 0.3; height: 6 * Y.u; radius: 3 * Y.u; color: Y.text }
                    Rectangle { anchors.centerIn: parent; width: 6 * Y.u; height: parent.height * 0.3; radius: 3 * Y.u; color: Y.text }
                }
            }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 372 * Y.u
                spacing: 4 * Y.u
                width: cell.width                // names ellipsized to the tile
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: cell.add ? "Add account" : cell.p.name || ""
                    color: cell.on ? Y.text : "#c9c4c6"
                    font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: cell.on ? Font.Bold : Font.DemiBold
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: cell.on && !cell.add && !!cell.p.handle
                    horizontalAlignment: Text.AlignHCenter
                    text: cell.p.handle || ""
                    elide: Text.ElideRight
                    color: "#c9c4c6"
                    font.family: Y.font; font.pixelSize: 24 * Y.u
                }
                Text {
                    width: parent.width
                    visible: cell.on && !cell.add && !!(cell.p.membership || cell.p.premium)
                    horizontalAlignment: Text.AlignHCenter
                    text: cell.p.membership || "YouTube Premium"
                    elide: Text.ElideRight
                    color: "#c9c4c6"
                    font.family: Y.font; font.pixelSize: 24 * Y.u
                }
            }
        }
    }
    Rectangle {                                // the gear under the focused profile
        id: gear
        visible: !page.onAdd && !!page.focused
        readonly property bool on: page.area === "gear" && page.activeFocus
        x: list.currentItem ? list.currentItem.x - list.contentX + (list.currentItem.width - width) / 2 : 0
        y: 810 * Y.u
        width: 72 * Y.u; height: width; radius: width / 2
        color: on ? Y.text : "#33ffffff"
        Icon { anchors.centerIn: parent; name: "settings"; size: 38 * Y.u; color: gear.on ? Y.ink : Y.text }
    }
    Rectangle {                                // Watch as guest
        readonly property bool on: page.area === "guest" && page.activeFocus
        anchors.horizontalCenter: parent.horizontalCenter
        y: 912 * Y.u
        width: guestT.implicitWidth + 58 * Y.u; height: 72 * Y.u; radius: height / 2
        color: on ? Y.text : "#1fffffff"
        Text { id: guestT; anchors.centerIn: parent; text: "Watch as guest"; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 26 * Y.u; font.weight: Font.Medium }
    }

    // ------------------------------------------------------------------ the gear's menu
    Rectangle {
        visible: page.area === "menu"
        anchors.fill: parent
        color: "#eb0f0f0f"
        Column {
            anchors.centerIn: parent
            spacing: 16 * Y.u
            width: 700 * Y.u
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: page.focused ? page.focused.name : ""
                color: Y.text; font.family: Y.font; font.pixelSize: 40 * Y.u; font.weight: Font.Bold
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Signing out removes this Google account and its channels from this TV."
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            }
            Item { width: 1; height: 16 * Y.u }
            Repeater {
                model: ["Sign out of this account", "Cancel"]
                Rectangle {
                    required property string modelData
                    required property int index
                    readonly property bool on: page.menuIndex === index
                    width: parent.width; height: 78 * Y.u; radius: 16 * Y.u
                    color: on ? Y.text : Y.raised
                    Text { anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 30 * Y.u; font.weight: Font.Medium }
                }
            }
        }
    }
}
