// Sign in to Frigate: the server (Settings → Apps), a user name and a password (the keyboard
// pop-up, or a phone). The TV keeps the sign-in and signs in again by itself when it runs out.
import QtQuick

FocusScope {
    id: page
    property string user: ""
    property string password: ""
    property string problem: ""
    property bool busy: false
    property int idx: 0
    signal ask(string what, string current, bool secret)
    signal signedIn()
    readonly property bool configured: !!F.status.configured

    function submit() {
        if (!user || !password) { problem = "Enter the user name and the password first."; return; }
        busy = true; problem = "";
        F.call("login", {user: user, password: password}, r => { busy = false; F.status = r; password = ""; page.signedIn(); },
               e => { busy = false; problem = e; });
    }
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(2, idx + 1)
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()
    function press() {
        if (!configured || busy) return;
        if (idx === 0) ask("User name", user, false);
        else if (idx === 1) ask("Password", "", true);
        else submit();
    }

    Rectangle { anchors.fill: parent; color: F.bg }
    Rectangle {
        anchors.centerIn: parent
        width: 900 * F.u
        height: col.implicitHeight + 120 * F.u
        radius: 24 * F.u
        color: F.panel
        border.color: F.line
        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 60 * F.u }
            spacing: 22 * F.u
            Row {
                spacing: 18 * F.u
                Rectangle {
                    width: 64 * F.u; height: width; radius: 16 * F.u; color: F.accent
                    Rectangle { anchors.centerIn: parent; width: 36 * F.u; height: 26 * F.u; radius: 6 * F.u; color: "white"
                        Rectangle { anchors.centerIn: parent; width: 13 * F.u; height: width; radius: width / 2; color: F.accent } }
                }
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Sign in to Frigate"; color: F.text; font.family: F.font; font.pixelSize: 44 * F.u; font.weight: Font.Bold }
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: page.configured ? F.status.url : "No Frigate server is set yet. Add yours in Settings → Apps → Frigate server (for example https://frigate.example.ts.net or http://192.168.1.20:8971), then open Frigate again."
                color: page.configured ? F.dim : F.text2; font.family: F.font; font.pixelSize: 26 * F.u
            }
            Item { width: 1; height: 6 * F.u }
            FButton { visible: page.configured; width: parent.width; text: page.user || "User name"; sub: page.user ? "User name" : "Press OK to type it"
                      border.color: page.activeFocus && page.idx === 0 ? F.focus : F.line; border.width: (page.activeFocus && page.idx === 0 ? 3 : 1) * F.u
                      color: page.activeFocus && page.idx === 0 ? F.panel2 : F.bg }
            FButton { visible: page.configured; width: parent.width; text: page.password ? "•".repeat(page.password.length) : "Password"; sub: page.password ? "Password" : "Press OK to type it"
                      border.color: page.activeFocus && page.idx === 1 ? F.focus : F.line; border.width: (page.activeFocus && page.idx === 1 ? 3 : 1) * F.u
                      color: page.activeFocus && page.idx === 1 ? F.panel2 : F.bg }
            FButton { visible: page.configured; width: parent.width; primary: true; text: page.busy ? "Signing in…" : "Sign in"
                      color: page.activeFocus && page.idx === 2 ? F.accent : "#1d4ed8"
                      border.color: page.activeFocus && page.idx === 2 ? "white" : "transparent"; border.width: 3 * F.u }
            Text { visible: !!page.problem; width: parent.width; wrapMode: Text.WordWrap; text: page.problem; color: F.alert; font.family: F.font; font.pixelSize: 25 * F.u }
            Text {
                visible: page.configured
                width: parent.width; wrapMode: Text.WordWrap
                text: "A Viewer account is enough (Frigate → Settings → Users). The TV remembers it and signs in again by itself."
                color: F.faint; font.family: F.font; font.pixelSize: 22 * F.u
            }
        }
    }
}
