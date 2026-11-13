// Couchbox: options for a home tile (hold OK, or press Menu, on it): move it along the row,
// restart it (while it runs: closed, then started fresh), hide it, or open the app's settings.
// Also a Continue watching card's (open(): a card instead of an app): remove it (until it's
// watched again: couchbox-ontv --remove) or don't show its app there (home.continue_off; While
// you were out and Today at home: turn them off). Changes run the couchbox command, which asks
// couchboxd.
import QtQuick

import org.kde.plasma.plasma5support as P5Support

FocusScope {
    id: menu
    property var app: null
    property var card: null                 // a Continue watching card (then app is null)
    property bool running: false            // the app is open (Restart)
    property Item returnTo: null
    signal moveRequested()
    signal startRequested()
    signal restarting(var app)              // Restart picked: the launch screen goes up
    signal restarted(var app)               // ... the app is closed: start it again
    signal removed(var card)                // a card taken off Continue watching

    readonly property bool welcome: !!card && (card.key === "away" || card.key === "day")
    visible: false
    z: 50

    readonly property var options: card ? cardOptions : !app ? [] : app.moment ? [
        {label: "Start", act: () => { close(); menu.startRequested(); }},
        {label: "Change in Settings", act: () => { run("/usr/lib/couchbox/bin/couchbox-settings --page moments --in"); close(); }},
    ] : [
        {label: "Move", act: () => { close(); menu.moveRequested(); }},
        ...(running ? [{label: "Restart", act: () => restart(app)}] : []),
        ...(app.hideable === false ? [] : [{label: "Hide from the home screen", act: () => { run("couchbox home hide " + app.app); close(); }}]),
        {label: "More in Settings", act: () => { run("/usr/lib/couchbox/bin/couchbox-settings"); close(); }},
    ]

    readonly property var cardOptions: !card ? [] : [
        {label: "Remove from Continue watching", act: () => {
            menu.removed(card);
            run("/usr/lib/couchbox/bin/couchbox-ontv --remove " + quote(card.key));
            close();
        }},
        welcome ? {label: card.key === "away" ? "Turn off While you were out" : "Turn off Today at home", act: () => {
            menu.removed(card);
            run("couchbox config set " + (card.key === "away" ? "home.away" : "home.day") + " false");
            close();
        }} : {label: "Don't show " + (card.name || card.app) + " here", act: () => {
            run("couchbox home continue-off " + quote(card.app));
            close();
        }},
    ]
    function restart(a) {
        close();
        menu.restarting(a);
        runThen("couchbox home quit " + quote(a.app), () => menu.restarted(a));
    }
    function quote(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'"; }

    // Opened by holding OK, the key is still down: its repeats (and its release) must not pick
    // "Move" straight away. OK works once it has been let go.
    property bool armed: true
    function open(a, from, held, isRunning) { card = null; app = a; running = !!isRunning; show(from, held); }
    function openCard(c, from, held) { app = null; card = c; running = false; show(from, held); }
    function show(from, held) { returnTo = from; armed = !held; list.currentIndex = 0; visible = true; list.forceActiveFocus(); }
    function isOk(key) { return key === Qt.Key_Return || key === Qt.Key_Enter || key === Qt.Key_Select; }
    function close() {
        visible = false;
        if (!returnTo) return;
        // (a removed card may have been the last: the row is gone, the apps take the focus)
        if (!returnTo.visible && returnTo.navigationUp) returnTo.navigationUp.forceActiveFocus();
        else returnTo.forceActiveFocus();
    }
    function run(cmd) { exec.connectSource(cmd); }
    property var after: ({})                // command -> what to do once it has finished
    function runThen(cmd, done) { after[cmd] = done; exec.connectSource(cmd); }

    P5Support.DataSource {
        id: exec
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source);
            const done = menu.after[source];
            if (done) { delete menu.after[source]; done(); }
        }
    }

    Keys.onEscapePressed: close()
    Keys.onBackPressed: close()

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.55) }
    Rectangle {
        anchors.centerIn: parent
        width: 620
        height: col.height + 60
        radius: 22
        color: "#151922"
        border.color: Qt.rgba(1, 1, 1, 0.12)
        Column {
            id: col
            x: 30; y: 30
            width: parent.width - 60
            spacing: 14
            Text {
                width: parent.width
                text: menu.card ? menu.card.title || "" : menu.app ? menu.app.name : ""
                elide: Text.ElideRight
                color: Style.text
                font.family: Style.font; font.pixelSize: 34; font.weight: Font.Bold
            }
            ListView {
                id: list
                width: parent.width
                height: contentHeight
                interactive: false
                keyNavigationEnabled: true      // (it follows interactive otherwise: Up and Down did nothing)
                spacing: 6
                model: menu.options
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool cur: ListView.isCurrentItem
                    width: list.width; height: 64; radius: 12
                    color: cur ? "#7aa2ff" : "transparent"
                    Text {
                        anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
                        text: modelData.label
                        color: parent.cur ? "#0b0d12" : Style.text
                        font.family: Style.font; font.pixelSize: 26; font.weight: parent.cur ? Font.Bold : Font.Normal
                    }
                }
                Keys.onPressed: (event) => {
                    if (!menu.isOk(event.key)) return;
                    event.accepted = true;
                    if (!event.isAutoRepeat && menu.armed) menu.options[currentIndex].act();
                }
                Keys.onReleased: (event) => {
                    if (menu.isOk(event.key) && !event.isAutoRepeat) { menu.armed = true; event.accepted = true; }
                }
            }
        }
    }
}
