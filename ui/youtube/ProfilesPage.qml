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
    signal chosen(var profile)                // null: watch as a guest
    signal addAccount()
    signal signOut(var profile)
    signal closed()

    function load(focusId) {
        Y.call("profiles", {}, r => {
            page.profiles = r.profiles || [];
            const want = focusId || r.last || r.current || "";
            const i = page.profiles.findIndex(p => p.id === want);
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
            GradientStop { position: 0; color: "#130d0f" }
            GradientStop { position: 0.6; color: "#2a0d15" }
            GradientStop { position: 1; color: "#4a0c1c" }
        }
    }
    Repeater {                                 // soft shapes, bottom right
        model: [{x: 1430, y: 790, w: 520, h: 640, r: -28, a: "#d04a6a", b: "#7a1830"},
                {x: 1720, y: 850, w: 360, h: 520, r: -18, a: "#e36f8f", b: "#a0244a"},
                {x: 1190, y: 990, w: 760, h: 360, r: -8, a: "#c8405a", b: "#5a1020"}]
        Rectangle {
            id: blob
            required property var modelData
            x: modelData.x * Y.u; y: modelData.y * Y.u
            width: modelData.w * Y.u; height: modelData.h * Y.u
            radius: width / 2
            rotation: modelData.r
            opacity: 0.85
            gradient: Gradient {
                GradientStop { position: 0; color: blob.modelData.a }
                GradientStop { position: 1; color: blob.modelData.b }
            }
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
        preferredHighlightBegin: 71 * Y.u
        preferredHighlightEnd: parent.width - 420 * Y.u
        highlightMoveDuration: 200
        header: Item { width: 71 * Y.u; height: 1 }
        delegate: Item {
            id: cell
            required property int index
            readonly property bool add: index === page.profiles.length
            readonly property var p: add ? ({}) : page.profiles[index]
            readonly property bool on: page.index === index && page.activeFocus
            readonly property real d: on ? 342 * Y.u : 296 * Y.u
            width: on ? 342 * Y.u : 296 * Y.u
            height: list.height
            Behavior on width { NumberAnimation { duration: 140 } }
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
                    color: "#33ffffff"
                    Rectangle { anchors.centerIn: parent; width: parent.width * 0.3; height: 6 * Y.u; radius: 3 * Y.u; color: Y.text }
                    Rectangle { anchors.centerIn: parent; width: 6 * Y.u; height: parent.height * 0.3; radius: 3 * Y.u; color: Y.text }
                }
            }
            Column {
                anchors.horizontalCenter: parent.horizontalCenter
                y: 372 * Y.u
                spacing: 4 * Y.u
                width: Math.max(cell.width + 40 * Y.u, 340 * Y.u)
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    text: cell.add ? "Add account" : cell.p.name || ""
                    color: cell.on ? Y.text : "#c9c4c6"
                    font.family: Y.font; font.pixelSize: 36 * Y.u; font.weight: cell.on ? Font.Bold : Font.Medium
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: cell.on && !cell.add && !!cell.p.handle
                    horizontalAlignment: Text.AlignHCenter
                    text: cell.p.handle || ""
                    color: "#c9c4c6"
                    font.family: Y.font; font.pixelSize: 24 * Y.u
                }
                Text {
                    width: parent.width
                    visible: cell.on && !cell.add && !!cell.p.premium
                    horizontalAlignment: Text.AlignHCenter
                    text: "YouTube Premium"
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
        width: guestT.implicitWidth + 74 * Y.u; height: 72 * Y.u; radius: height / 2
        color: on ? Y.text : "#33ffffff"
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
