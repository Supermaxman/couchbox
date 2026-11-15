// Couchbox setup: the first thing on the TV after flashing. Works with the TV's own remote
// (HDMI-CEC), a Fire TV remote (pairs from the first screen on), the phone or a USB keyboard. Each step is a page of
// rows like Settings; Back goes to the previous step. Progress is saved, so a restart
// carries on where it stopped.
import QtQuick
import QtQuick.Window
import CouchKit
import "../settings"

Window {
    id: win
    width: 1920
    height: 1080
    visible: true
    visibility: shot ? Window.Windowed : Window.FullScreen
    title: "Couchbox setup"
    color: T.bg

    readonly property var args: Qt.application.arguments
    function arg(name) { const i = args.indexOf(name); return i >= 0 ? args[i + 1] || "" : ""; }
    readonly property string shot: arg("--shot")
    onHeightChanged: T.u = height / 1080

    readonly property var steps: ["Hello", "Remote", "Install", "Network", "Time", "Name", "TvButtons", "Updates", "Extras", "Apps", "Done"]
    property int step: arg("--step") !== "" ? parseInt(arg("--step")) : 0
    property var completed: []
    property var typed: null
    // steps that don't apply here: Install only when running from a USB stick or SD card
    // with an SSD to copy to
    property var skip: ["Install"]

    Component.onCompleted: {
        T.u = height / 1080;
        T.load();
        T.call("remote.pair_start", {seconds: 0}, r => win.pair = r, () => {});   // look for remotes from the start
        if (arg("--step") !== "") return;
        T.call("install.status", {}, ist => {
            if (ist.can_install || (ist.job && ist.job.state === "running")) skip = [];
            T.call("setup.state", {}, st => {
                if (!st.done && st.step > 0) step = Math.min(st.step, steps.length - 1);
                while (skip.indexOf(steps[step]) >= 0 && step < steps.length - 1) step++;
            });
        }, () => T.call("setup.state", {}, st => { if (!st.done && st.step > 0) step = Math.min(st.step, steps.length - 1); }));
    }

    // Remote pairing, from the first screen on (Hello and Remote show it): the remote's light
    // barely shows, so the screen is all the feedback there is. A failed try is said until a
    // remote shows up again; meanwhile the search starts over.
    property var pair: ({state: "searching"})
    property string pairFail: ""
    property bool finishing: false
    Timer { id: pairAgain; interval: 5000; onTriggered: T.call("remote.pair_start", {seconds: 0}, r => win.pair = r, () => {}) }
    Connections {
        target: T
        function onEvent(topic, d) {
            if (topic !== "remote.pairing") return;
            win.pair = d;
            if (d.state === "found" || d.state === "paired") win.pairFail = "";
            if (d.state === "failed") win.pairFail = d.why || "Pairing didn't finish";
            if ((d.state === "failed" || d.state === "stopped") && !win.finishing) pairAgain.restart();
        }
    }
    // the row both screens show; how: say how to start pairing
    function pairRow(how) {
        const st = pair.state, name = pair.name || "the remote";
        const tryAgain = "Hold Home for 10 seconds to try again.";
        if (st === "paired")
            return T.info("Fire TV remote", "Paired", {tone: "good", help: name + " is paired: its arrows and OK work now."});
        if (st === "found" || st === "pairing")
            return T.info("Fire TV remote", (st === "found" ? "Found " : "Pairing ") + name + (pair.attempt > 1 ? " · try " + pair.attempt : ""),
                          {busy: true, help: how ? "Keep holding Home until it pairs." : ""});
        if (pairFail)
            return T.info("Fire TV remote", "Didn't pair", {tone: "bad", help: pairFail + ". " + tryAgain});
        return T.info("Fire TV remote", "Looking", {busy: true, help: how ? "Hold its Home button for about 10 seconds. It pairs by itself." : ""});
    }
    function next() {
        if (completed.indexOf(steps[step]) < 0) completed = completed.concat([steps[step]]);
        let n = Math.min(step + 1, steps.length - 1);
        while (skip.indexOf(steps[n]) >= 0 && n < steps.length - 1) n++;
        step = n;
        T.call("setup.save", {step: step, completed: completed}, () => {});
    }
    function prev() {
        let n = step - 1;
        while (n > 0 && skip.indexOf(steps[n]) >= 0) n--;
        if (n >= 0) step = n;
    }
    function finish() {
        finishing = true;
        T.call("remote.pair_stop", {}, () => {});
        T.call("setup.save", {step: steps.length - 1, completed: completed, done: true}, () => Qt.quit());
    }

    Connections {
        target: backend
        function onReply(id, json) { T.reply(id, json); }
        function onEvent(topic, json) { T.onEvent(topic, json); }
    }
    Connections {
        target: T
        function onAskText(title, text, password, done) {
            win.typed = done; keyboard.title = title; keyboard.password = password; keyboard.doneLabel = "Done";
            // the same phone address as the card on the left: one a new user's phone can open
            const ph = phoneCard.phone;
            keyboard.phoneLink = ph.mode === "lan" || ph.mode === "hotspot" ? ph.url : "";
            keyboard.phoneQr = keyboard.phoneLink ? backend.qr(keyboard.phoneLink) : "";
            keyboard.open(text, win.activeFocusItem);
        }
        function onPick(title, options, current, done) { picker.open(title, options, current, done); }
        function onConfirm(title, text, yes, done) { dialog.show(title, text, "", "", ["Cancel", yes], i => { if (i === 1) done(); }); }
        function onMessage(title, text, qr, extra) { dialog.show(title, text, qr, extra, ["OK"]); }
        function onCloseMessage() { if (dialog.visible) dialog.close(-1); }
        function onToast(text) { toast.show(text); }
    }

    // left: where we are
    Rectangle {
        id: left
        width: 640 * T.u
        height: parent.height
        color: T.side
        Column {
            x: 72 * T.u; y: 96 * T.u
            width: parent.width - 144 * T.u
            spacing: 24 * T.u
            Text {
                text: "couchbox"
                color: T.accent
                font.family: T.font; font.pixelSize: 40 * T.u; font.weight: Font.Black; font.letterSpacing: 2 * T.u
            }
            Text {
                width: parent.width
                text: page.item ? page.item.title : ""
                color: T.text
                wrapMode: Text.WordWrap
                font.family: T.font; font.pixelSize: 58 * T.u; font.weight: Font.Bold
            }
            Text {
                width: parent.width
                text: page.item ? page.item.intro : ""
                color: T.dim
                wrapMode: Text.WordWrap
                lineHeight: 1.2
                font.family: T.font; font.pixelSize: 27 * T.u
            }
        }
        Row {
            id: dots
            anchors { left: parent.left; leftMargin: 72 * T.u; bottom: parent.bottom; bottomMargin: 80 * T.u }
            spacing: 12 * T.u
            Repeater {
                model: win.steps.length
                Rectangle {
                    required property int index
                    width: index === win.step ? 36 * T.u : 12 * T.u; height: 12 * T.u; radius: 6 * T.u
                    color: index <= win.step ? T.accent : T.line
                    Behavior on width { NumberAnimation { duration: 150 } }
                }
            }
        }
        PhoneCard {
            id: phoneCard
            anchors { left: parent.left; leftMargin: 72 * T.u; bottom: dots.top; bottomMargin: 48 * T.u; right: parent.right; rightMargin: 72 * T.u }
        }
    }

    Loader {
        id: page
        anchors { left: left.right; right: parent.right; top: parent.top; bottom: parent.bottom }
        source: "Step" + win.steps[win.step] + ".qml"
        focus: true
        onLoaded: item.forceActiveFocus()
        Connections {
            target: page.item
            ignoreUnknownSignals: true
            function onBack() { win.prev(); }
        }
    }

    Picker { id: picker; anchors.fill: parent }
    Dialog { id: dialog; anchors.fill: parent }
    TextEntry {
        id: keyboard
        anchors.fill: parent
        accent: T.accent; bg: T.bg; panel: T.panel; keyColor: T.panel2; line: T.line; ink: T.text; dim: T.dim
        fallbackFocus: page.item
        onAccepted: t => { const done = win.typed; win.typed = null; if (done) done(t); }
        onCanceled: win.typed = null
    }
    Rectangle {
        id: toast
        function show(t) { toastText.text = t; opacity = 1; toastTimer.restart(); }
        anchors { horizontalCenter: page.horizontalCenter; bottom: parent.bottom; bottomMargin: 60 * T.u }
        width: Math.min(page.width - 100 * T.u, toastText.implicitWidth + 64 * T.u)
        height: toastText.height + 36 * T.u
        radius: 12 * T.u
        color: T.panel2; border.color: T.line
        opacity: 0; z: 200
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            id: toastText
            anchors.centerIn: parent
            width: Math.min(implicitWidth, page.width - 160 * T.u)
            wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
            color: T.text; font.family: T.font; font.pixelSize: 25 * T.u; font.weight: Font.DemiBold
        }
        Timer { id: toastTimer; interval: 4000; onTriggered: toast.opacity = 0 }
    }

    // --shot FILE [--step N] [--keys down,ok,...] [--wait MS]: render and save (tests)
    property var keys: arg("--keys") ? arg("--keys").split(",") : []
    Timer {
        interval: 800; repeat: true
        running: !!win.shot && win.keys.length > 0
        onTriggered: { const k = win.keys.shift(); win.keys = win.keys; shooter.press(k); }
    }
    Timer { running: !!win.shot; interval: parseInt(win.arg("--wait") || "4000"); onTriggered: { shooter.save(win.shot); Qt.quit(); } }
}
