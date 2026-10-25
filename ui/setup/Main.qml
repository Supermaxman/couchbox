// Couchbox setup: the first thing on the TV after flashing. Works with the TV's own remote
// (HDMI-CEC), a Fire TV remote (paired in step 2) or a USB keyboard. Each step is a page of
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
        if (arg("--step") !== "") return;
        T.call("install.status", {}, ist => {
            if (ist.can_install || (ist.job && ist.job.state === "running")) skip = [];
            T.call("setup.state", {}, st => {
                if (!st.done && st.step > 0) step = Math.min(st.step, steps.length - 1);
                while (skip.indexOf(steps[step]) >= 0 && step < steps.length - 1) step++;
            });
        }, () => T.call("setup.state", {}, st => { if (!st.done && st.step > 0) step = Math.min(st.step, steps.length - 1); }));
        T.call("remote.pair_start", {seconds: 0}, () => {});          // look for remotes from the start
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
            anchors { left: parent.left; leftMargin: 72 * T.u; bottom: hint.top; bottomMargin: 36 * T.u; right: parent.right; rightMargin: 72 * T.u }
        }
        Text {
            id: hint
            anchors { left: parent.left; leftMargin: 72 * T.u; bottom: parent.bottom; bottomMargin: 120 * T.u; right: parent.right; rightMargin: 72 * T.u }
            text: "Arrows move · OK selects · Back goes back"
            color: T.dim
            font.family: T.font; font.pixelSize: 21 * T.u
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
