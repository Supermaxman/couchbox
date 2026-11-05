// Adding a YouTube account: a code to enter at youtube.com/activate on a phone or computer, and a QR
// code that opens that page with the code filled in. The code keeps working for 30 minutes after
// leaving this page (couchbox.services.ytauth waits for it), so it can be entered later; the app
// says so when it's used.
import QtQuick

FocusScope {
    id: page
    objectName: "signin"
    property var c: ({})                      // {state: waiting | expired | ok | denied, code, url, qr, expires}
    property int button: 0                    // 0 Get a new code, 1 Back
    readonly property string label: "Add account"
    signal closed()

    function load(fresh) {
        const show = r => { page.c = r; };
        if (fresh) Y.call("signInStart", {}, show, e => page.c = {state: "error", message: e});
        else Y.call("signInState", {}, r => { if (r.state === "waiting") show(r); else page.load(true); }, e => page.c = {state: "error", message: e});
    }
    Component.onCompleted: load(false)
    Timer {                                    // the countdown, and whether it's been used yet
        interval: 3000; repeat: true; running: page.visible && page.c.state === "waiting"
        onTriggered: Y.call("signInState", {}, r => { if (r.state !== "waiting" || r.code === page.c.code) page.c = Object.assign({}, page.c, r); }, () => {})
    }
    Keys.onLeftPressed: button = 0
    Keys.onRightPressed: button = 1
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()
    Keys.onEscapePressed: closed()
    Keys.onBackPressed: closed()
    function activate() { if (button === 0) load(true); else closed(); }

    Rectangle { anchors.fill: parent; color: Y.bg }
    Logo { x: Y.left; y: 70 * Y.u }
    Text {
        x: Y.left; y: 170 * Y.u
        text: page.c.state === "ok" ? "Signed in" : "Add a YouTube account"
        color: Y.text; font.family: Y.font; font.pixelSize: 56 * Y.u; font.weight: Font.Bold
    }

    Row {
        x: Y.left; y: 300 * Y.u
        spacing: 110 * Y.u
        visible: page.c.state === "waiting"
        Column {
            spacing: 24 * Y.u
            Rectangle {
                width: 380 * Y.u; height: width; radius: 24 * Y.u
                color: "white"
                Image {
                    anchors { fill: parent; margins: 22 * Y.u }
                    source: page.c.qr ? "file://" + page.c.qr : ""
                    sourceSize: Y.sz(width, height)
                    smooth: false
                    cache: false
                }
                Text {
                    anchors.centerIn: parent
                    visible: !page.c.qr
                    text: "QR"
                    color: "#bbbbbb"; font.family: Y.font; font.pixelSize: 80 * Y.u; font.weight: Font.Bold
                }
            }
            Text {
                width: 380 * Y.u
                horizontalAlignment: Text.AlignHCenter
                text: "Scan with your phone's camera"
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
            }
        }
        Column {
            spacing: 26 * Y.u
            width: 1000 * Y.u
            Text { text: "Or on a phone or computer, go to"; color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u }
            Text { text: page.c.url || "youtube.com/activate"; color: Y.text; font.family: Y.font; font.pixelSize: 48 * Y.u; font.weight: Font.Bold }
            Text { text: "and enter this code"; color: Y.dim; font.family: Y.font; font.pixelSize: 32 * Y.u }
            Rectangle {
                width: codeT.implicitWidth + 80 * Y.u; height: 132 * Y.u; radius: 20 * Y.u
                color: Y.raised
                Text {
                    id: codeT
                    anchors.centerIn: parent
                    text: page.c.code || ""
                    color: Y.text
                    font.family: Y.font; font.pixelSize: 80 * Y.u; font.weight: Font.Bold
                    font.letterSpacing: 8 * Y.u
                }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "The code works for " + Math.max(1, Math.round((page.c.expires || 1800) / 60)) + " more minutes. You can leave this page: "
                      + "the TV keeps waiting, and says so once it's been entered."
                color: Y.dim; font.family: Y.font; font.pixelSize: 26 * Y.u
                lineHeight: 1.15
            }
        }
    }
    Text {                                     // done, expired or failed
        x: Y.left; y: 320 * Y.u
        width: parent.width - 2 * Y.left
        visible: page.c.state !== "waiting" && !!page.c.state
        wrapMode: Text.WordWrap
        text: page.c.state === "ok" ? (page.c.name ? page.c.name + " is signed in." : "The account is signed in.") + " Back to choose who's watching."
              : page.c.state === "expired" ? "That code ran out. Get a new code to try again."
              : page.c.state === "denied" ? "Signing in was cancelled on the phone. Get a new code to try again."
              : page.c.message || "Getting a code…"
        color: Y.text; font.family: Y.font; font.pixelSize: 34 * Y.u
    }

    Row {
        x: Y.left; y: 900 * Y.u
        spacing: 24 * Y.u
        Repeater {
            model: ["Get a new code", "Back"]
            Rectangle {
                required property string modelData
                required property int index
                readonly property bool on: page.button === index && page.activeFocus
                width: bt.implicitWidth + 72 * Y.u; height: 72 * Y.u; radius: height / 2
                color: on ? Y.text : Y.raised
                Text { id: bt; anchors.centerIn: parent; text: parent.modelData; color: parent.on ? Y.ink : Y.text; font.family: Y.font; font.pixelSize: 28 * Y.u; font.weight: Font.Medium }
            }
        }
    }
}
