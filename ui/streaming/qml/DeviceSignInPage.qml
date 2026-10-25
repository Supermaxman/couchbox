// Signing in with a code (Twitch): go to twitch.tv/activate on a phone or computer (or scan
// the QR code) and enter the code shown; this page checks every few seconds until it's done.
import QtQuick

FocusScope {
    id: page
    property var info: null
    property string note: "Getting a code…"
    signal done(var status)

    function start() {
        info = null; note = "Getting a code…";
        D.call("deviceStart", {}, r => { info = r; note = ""; poll.start(); }, err => note = err);
    }
    Component.onCompleted: start()
    Timer {
        id: poll
        interval: 5000
        repeat: true
        onTriggered: D.call("devicePoll", {}, r => {
            if (r.state === "ok") { poll.stop(); D.toast("Signed in as " + r.user + "."); page.done({state: "ok"}); }
            else if (r.state === "expired") { poll.stop(); page.start(); }
        })
    }
    Keys.onEscapePressed: { poll.stop(); page.done({state: "ok"}); }      // Back: browse without signing in
    Keys.onBackPressed: { poll.stop(); page.done({state: "ok"}); }

    Rectangle { anchors.fill: parent; color: D.bg }
    Row {
        anchors.centerIn: parent
        spacing: 120 * D.u
        Column {
            width: 820 * D.u
            spacing: 34 * D.u
            Logo { size: 70 }
            Text { width: parent.width; text: "Sign in to " + D.name; color: D.text; font.family: D.font; font.pixelSize: 52 * D.u; font.weight: Font.Black }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: page.info ? "On your phone or computer, go to\n" : page.note
                color: D.text2; font.family: D.font; font.pixelSize: 30 * D.u; lineHeight: 1.2
            }
            Text {
                visible: !!page.info
                text: page.info ? page.info.url.replace(/^https:\/\/(www\.)?/, "") : ""
                color: D.accent; font.family: D.font; font.pixelSize: 44 * D.u; font.weight: Font.Bold
            }
            Text { visible: !!page.info; text: "and enter this code:"; color: D.text2; font.family: D.font; font.pixelSize: 30 * D.u }
            Rectangle {
                visible: !!page.info
                width: code.implicitWidth + 80 * D.u
                height: code.implicitHeight + 40 * D.u
                radius: 12 * D.u
                color: D.panel
                border.color: D.accent
                border.width: 3 * D.u
                Text {
                    id: code
                    anchors.centerIn: parent
                    text: page.info ? page.info.code : ""
                    color: D.text; font.family: D.font; font.pixelSize: 76 * D.u; font.weight: Font.Black; font.letterSpacing: 10 * D.u
                }
            }
            Text { text: "Back to browse without signing in"; color: D.dim; font.family: D.font; font.pixelSize: 24 * D.u }
        }
        Column {
            visible: !!(page.info && page.info.qr)
            anchors.verticalCenter: parent.verticalCenter
            spacing: 22 * D.u
            Rectangle {
                width: 380 * D.u; height: width; radius: 20 * D.u; color: "white"
                Image { anchors.fill: parent; anchors.margins: 18 * D.u; source: page.info && page.info.qr ? "file://" + page.info.qr : ""; smooth: false; cache: false; fillMode: Image.PreserveAspectFit }
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: "or scan with your phone"; color: D.text2; font.family: D.font; font.pixelSize: 26 * D.u }
        }
    }
}
