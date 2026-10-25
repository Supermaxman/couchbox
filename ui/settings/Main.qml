// Couchbox Settings: everything about the box, from the remote. Sections on the left, the
// chosen section's page on the right. Up/Down move, OK changes or opens, Right enters a
// page, Left/Back leaves it; Back on the sections closes Settings.
import QtQuick
import QtQuick.Window
import CouchKit

Window {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Settings"
    color: T.bg

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    onHeightChanged: T.u = height / 1080

    readonly property var sections: [
        {id: "network", name: "Network", icon: "📶"},
        {id: "home", name: "Home screen", icon: "🏠"},
        {id: "apps", name: "Apps and media", icon: "🎬"},
        {id: "voice", name: "Voice", icon: "🎙️"},
        {id: "remote", name: "Remote and TV", icon: "📺"},
        {id: "display", name: "Display and sound", icon: "🖥️"},
        {id: "time", name: "Date, time, location", icon: "🕒"},
        {id: "access", name: "Remote access", icon: "🔗"},
        {id: "security", name: "Security", icon: "🔒"},
        {id: "updates", name: "Updates", icon: "⬇️"},
        {id: "system", name: "System", icon: "⚙️"},
    ]
    property int section: 0
    property var chips: ({})                       // section id -> short status

    Component.onCompleted: {
        T.u = height / 1080;
        T.load();
        const p = arg("--page");
        const i = sections.findIndex(s => s.id === p);
        if (i >= 0) section = i;
        nav.forceActiveFocus();
        if (p && win.args.indexOf("--in") >= 0) enterTimer.start();
    }
    Connections {
        target: backend
        function onReply(id, json) { T.reply(id, json); }
        function onEvent(topic, json) { T.onEvent(topic, json); }
    }
    Connections {
        target: T
        function onAskText(title, text, password, done) {
            win.typed = done;
            keyboard.title = title;
            keyboard.password = password;
            keyboard.doneLabel = "Done";
            keyboard.open(text, win.activeFocusItem);
        }
        function onPick(title, options, current, done) { picker.open(title, options, current, done); }
        function onConfirm(title, text, yes, done) { dialog.show(title, text, "", "", ["Cancel", yes], i => { if (i === 1) done(); }); }
        function onMessage(title, text, qr, extra) { dialog.show(title, text, qr, extra, ["OK"]); }
        function onCloseMessage() { if (dialog.visible) dialog.close(-1); }
        function onToast(text) { toast.show(text); }
    }
    property var typed: null

    function enter() { if (pages.item) pages.item.forceActiveFocus(); }
    Timer { id: enterTimer; interval: 300; onTriggered: win.enter() }

    // ------------------------------------------------------------------ sections
    Rectangle {
        id: sidebar
        width: 520 * T.u
        height: parent.height
        color: T.side
        Text {
            id: brand
            x: 56 * T.u; y: 56 * T.u
            text: "Settings"
            color: T.text
            font.family: T.font; font.pixelSize: 46 * T.u; font.weight: Font.Black
        }
        ListView {
            id: nav
            anchors { left: parent.left; right: parent.right; top: brand.bottom; bottom: parent.bottom; topMargin: 32 * T.u; margins: 28 * T.u }
            model: win.sections
            currentIndex: win.section
            spacing: 4 * T.u
            clip: true
            focus: true
            highlightMoveDuration: 100
            onCurrentIndexChanged: win.section = currentIndex
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool cur: ListView.isCurrentItem
                width: nav.width
                height: 76 * T.u
                radius: 14 * T.u
                color: cur ? (nav.activeFocus ? T.accent : T.panel2) : "transparent"
                Text {
                    id: ic
                    x: 22 * T.u
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.icon
                    font.pixelSize: 28 * T.u
                    color: parent.cur && nav.activeFocus ? T.accentInk : T.text
                }
                Text {
                    anchors { left: ic.right; leftMargin: 18 * T.u; right: chip.left; rightMargin: 10 * T.u; verticalCenter: parent.verticalCenter }
                    text: modelData.name
                    elide: Text.ElideRight
                    color: parent.cur && nav.activeFocus ? T.accentInk : T.text
                    font.family: T.font; font.pixelSize: 27 * T.u; font.weight: parent.cur ? Font.Bold : Font.Medium
                }
                Text {
                    id: chip
                    anchors { right: parent.right; rightMargin: 20 * T.u; verticalCenter: parent.verticalCenter }
                    text: win.chips[modelData.id] || ""
                    color: parent.cur && nav.activeFocus ? T.accentInk : T.dim
                    font.family: T.font; font.pixelSize: 19 * T.u
                }
            }
            Keys.onRightPressed: win.enter()
            Keys.onReturnPressed: win.enter()
            Keys.onEnterPressed: win.enter()
            Keys.onEscapePressed: Qt.quit()
            Keys.onBackPressed: Qt.quit()
        }
    }

    // ------------------------------------------------------------------ the page
    Loader {
        id: pages
        anchors { left: sidebar.right; right: parent.right; top: parent.top; bottom: parent.bottom }
        source: win.sections[win.section].id.charAt(0).toUpperCase() + win.sections[win.section].id.slice(1) + "Page.qml"
        Connections {
            target: pages.item
            ignoreUnknownSignals: true
            function onBack() { nav.forceActiveFocus(); }
        }
    }

    // ------------------------------------------------------------------ overlays
    Picker { id: picker; anchors.fill: parent }
    Dialog { id: dialog; anchors.fill: parent }
    TextEntry {
        id: keyboard
        anchors.fill: parent
        accent: T.accent; bg: T.bg; panel: T.panel; keyColor: T.panel2; line: T.line; ink: T.text; dim: T.dim
        onAccepted: t => { const done = win.typed; win.typed = null; if (done) done(t); }
        onCanceled: win.typed = null
    }
    Rectangle {
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: 60 * T.u }
        width: Math.min(parent.width - 200 * T.u, toastText.implicitWidth + 64 * T.u)
        height: toastText.height + 36 * T.u
        radius: 12 * T.u
        color: T.panel2
        border.color: T.line
        opacity: 0
        z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            id: toastText
            anchors.centerIn: parent
            width: Math.min(implicitWidth, win.width - 260 * T.u)
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            color: T.text
            font.family: T.font; font.pixelSize: 25 * T.u; font.weight: Font.DemiBold
        }
        Timer { id: toastTimer; interval: 4000; onTriggered: toast.opacity = 0 }
    }

    // --shot FILE [--page ID] [--in] [--keys down,ok,...] [--wait MS]: render and save (tests)
    property var keys: []
    Timer {
        interval: 700; repeat: true
        running: shotTimer.running && win.keys.length > 0
        onTriggered: { const k = win.keys.shift(); win.keys = win.keys; shooter.press(k); }
    }
    Timer {
        running: !!win.shot
        interval: 1500
        onTriggered: { win.keys = win.arg("--keys") ? win.arg("--keys").split(",") : []; shotTimer.start(); }
    }
    Timer { id: shotTimer; interval: parseInt(win.arg("--wait") || "3000"); onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
