// Signing in: first the TV browser's Dropout sign-in is copied (if it's signed in there),
// else email and password, typed with the keyboard pop-up or on a phone.
import QtQuick

FocusScope {
    id: page
    property string email: ""
    property string password: ""
    property string note: "Checking the browser's " + D.name + " sign-in…"
    property bool busy: true
    signal done(var status)

    Component.onCompleted: D.call("import", {}, r => {
        busy = false;
        if (r.state !== "signin") return done(r);
        note = "Sign in with your " + D.name + " account.";
        emailBox.forceActiveFocus();
    }, err => { busy = false; note = err; emailBox.forceActiveFocus(); })

    function submit() {
        if (!email || !password) { note = "Enter your email and password."; return; }
        busy = true; note = "Signing in…";
        D.call("login", {email: email, password: password}, r => {
            busy = false; password = "";
            if (r.state === "signin") { note = "That didn't work. Check the email and password."; return; }
            done(r);
        }, err => { busy = false; note = err; });
    }

    component Field: Rectangle {
        id: f
        property string label: ""
        property string value: ""
        property bool secret: false
        signal entered(string text)
        width: parent ? parent.width : 0
        height: 84 * D.u
        radius: 8 * D.u
        color: activeFocus ? D.panel2 : D.panel
        border.color: activeFocus ? D.accent : D.line
        border.width: activeFocus ? 4 * D.u : 1
        Text {
            anchors { left: parent.left; leftMargin: 28 * D.u; verticalCenter: parent.verticalCenter }
            text: f.value ? (f.secret ? "•".repeat(f.value.length) : f.value) : f.label
            color: f.value ? D.text : D.dim
            font.family: D.font
            font.pixelSize: 28 * D.u
        }
        function ask() { D.askText(f.label, f.value, f.secret, t => f.entered(t)); }
        Keys.onReturnPressed: ask()
        Keys.onEnterPressed: ask()
    }

    Rectangle { anchors.fill: parent; color: D.bg }
    Column {
        anchors.centerIn: parent
        width: 760 * D.u
        spacing: 30 * D.u
        Logo { size: 84 }
        Text { width: parent.width; text: page.note; wrapMode: Text.WordWrap; color: D.text2; font.family: D.font; font.pixelSize: 28 * D.u }
        Field {
            id: emailBox
            visible: !page.busy
            label: "Email"
            value: page.email
            onEntered: t => { page.email = t.trim(); passBox.forceActiveFocus(); }
            KeyNavigation.down: passBox
        }
        Field {
            id: passBox
            visible: !page.busy
            label: "Password"
            secret: true
            value: page.password
            onEntered: t => { page.password = t; signBtn.forceActiveFocus(); }
            KeyNavigation.up: emailBox
            KeyNavigation.down: signBtn
        }
        DButton {
            id: signBtn
            visible: !page.busy
            primary: true
            text: "Sign In"
            onClicked: page.submit()
            KeyNavigation.up: passBox
        }
    }
}
