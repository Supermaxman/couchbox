// Setting Spotify up on this TV, one step at a time: the developer app's client ID (browsing
// your music), the Soloist API key and Spotify's player (playing it here), picking this TV in
// the Spotify app once, and signing in with a phone. The panel on the right explains the step
// that's selected; signing in shows a QR code there. Up/Down, OK.
import QtQuick

FocusScope {
    id: page
    property int idx: 0
    property string qr: ""
    property string loginLink: ""
    property bool busy: false
    signal ask(string what, string current, bool secret, string op)
    signal done()
    readonly property var st: S.status || ({})
    readonly property var pl: st.player || ({})
    readonly property var rows: {
        const r = [
            {id: "client", label: "1. Your Spotify developer app", value: st.client_id ? "Client ID " + st.client_id.slice(0, 6) + "…" : "Not set yet", ok: !!st.client_id},
            {id: "key", label: "2. Your Soloist API key", value: pl.key ? "Saved on this TV" : "Not set yet", ok: !!pl.key},
            {id: "player", label: "3. Spotify's player on this TV", ok: !!pl.installed && !!pl.running,
             value: busy ? "Downloading from Spotify…" : !pl.installed ? "Not downloaded yet" : !pl.running ? "Downloaded, starting…"
                    : "Ready" + (pl.days_left !== null && pl.days_left !== undefined ? " · updates itself (" + Math.round(pl.days_left) + " days left on this build)" : "")},
            {id: "pair", label: "4. Pick this TV in the Spotify app", value: pl.logged_in ? "Done: this TV is a Spotify speaker" : pl.login_error ? "Spotify refused the Soloist key: see step 2" : "Not yet",
             ok: !!pl.logged_in, bad: !pl.logged_in && !!pl.login_error},
            {id: "signin", label: "5. Sign in to your Spotify account", value: st.signedIn ? "Signed in as " + st.user : "Not signed in", ok: !!st.signedIn},
            {id: "paste", label: "Phone ended on a page that won't load?", value: "Type its address here", ok: false, minor: true}
        ];
        r.push({id: "done", label: st.signedIn ? "Done" : "Later", value: "", primary: true});
        if (st.signedIn) r.push({id: "signout", label: "Sign out of Spotify", value: "", minor: true});
        if (pl.installed) r.push({id: "remove", label: "Remove the player from this TV", value: "", minor: true});
        return r;
    }
    readonly property string device: st.device || "this TV"

    function refresh() { S.call("status", {}, s => S.status = s); }
    Timer { interval: 3000; repeat: true; running: page.visible; onTriggered: page.refresh() }
    onVisibleChanged: if (visible) { refresh(); qr = ""; }

    function press() {
        const id = rows[idx].id;
        if (id === "client") ask("Spotify client ID", st.client_id || "", false, "set_client_id");
        else if (id === "key") ask("Soloist API key", "", true, "set_key");
        else if (id === "player") {
            busy = true;
            S.call("install_player", {}, s => { busy = false; S.status = s; S.toast("Spotify's player is ready."); },
                   e => { busy = false; S.toast(e); });
        } else if (id === "signin") startLogin();
        else if (id === "paste") ask("The address your phone ended on", "", false, "login_paste");
        else if (id === "done") done();
        else if (id === "signout") S.call("signout", {}, s => { S.status = s; S.toast("Signed out of Spotify."); });
        else if (id === "remove") S.call("remove_player", {}, s => { S.status = s; S.toast("Removed Spotify's player."); });
    }
    function startLogin() {
        if (!st.client_id) { S.toast("Add your client ID first (step 1)."); idx = 0; return; }
        S.call("login_start", {}, r => { page.qr = backend.qr(r.link); page.loginLink = r.link; page.idx = 4; }, e => S.toast(e));
    }
    Connections {
        target: S
        function onStatusChanged() { if (page.visible && S.status.signedIn && page.qr) { page.qr = ""; S.toast("Signed in as " + S.status.user + "."); } }
    }
    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(rows.length - 1, idx + 1)
    Keys.onReturnPressed: press()
    Keys.onEnterPressed: press()

    Rectangle { anchors.fill: parent; color: S.bg }
    Text { id: title; x: 90 * S.u; y: 70 * S.u; text: "Set up Spotify"; color: S.text; font.family: S.font; font.pixelSize: S.tTitle; font.weight: Font.Bold }
    Text { anchors { left: title.left; top: title.bottom; topMargin: 10 * S.u }
           width: 860 * S.u; wrapMode: Text.WordWrap
           text: "Needs a Spotify Premium account (the one that makes the keys). Do steps 1 and 2 on a computer or phone at developer.spotify.com; type on your phone with the phone remote page."
           color: S.dim; font.family: S.font; font.pixelSize: S.tMeta }
    Column {
        id: list
        x: 90 * S.u; y: 270 * S.u
        width: 860 * S.u
        spacing: 12 * S.u
        Repeater {
            model: page.rows
            delegate: Rectangle {
                required property var modelData
                required property int index
                readonly property bool cur: page.activeFocus && page.idx === index
                width: list.width; height: (modelData.value ? 96 : 76) * S.u; radius: 14 * S.u
                color: modelData.primary ? (cur ? Qt.lighter(S.accent, 1.1) : S.accentDark) : cur ? S.panel2 : modelData.minor ? "transparent" : S.panel
                border.color: cur ? S.focus : "transparent"; border.width: S.ring
                Rectangle {
                    id: tick
                    visible: !modelData.primary && !modelData.minor
                    x: 22 * S.u; anchors.verticalCenter: parent.verticalCenter
                    width: 38 * S.u; height: width; radius: width / 2
                    color: !!modelData.ok ? S.accent : "transparent"; border.color: !!modelData.ok ? S.accent : S.faint; border.width: 3 * S.u
                    Image { anchors.centerIn: parent; visible: !!modelData.ok; width: 24 * S.u; height: width; sourceSize: Qt.size(width, height); source: S.icon("check-dark") }
                }
                Column {
                    anchors { left: parent.left; leftMargin: tick.visible ? 82 * S.u : 28 * S.u; right: parent.right; rightMargin: 24 * S.u; verticalCenter: parent.verticalCenter }
                    spacing: 4 * S.u
                    Text { width: parent.width; text: modelData.label; elide: Text.ElideRight; horizontalAlignment: modelData.primary ? Text.AlignHCenter : Text.AlignLeft
                           color: modelData.primary ? "#000000" : modelData.minor ? S.dim : S.text; font.family: S.font; font.pixelSize: S.tBody; font.weight: Font.DemiBold }
                    Text { width: parent.width; visible: !!modelData.value; text: modelData.value || ""; elide: Text.ElideRight
                           color: !!modelData.ok ? S.accent : modelData.bad ? S.danger : S.dim; font.family: S.font; font.pixelSize: S.tMeta }
                }
            }
        }
    }
    Rectangle {
        id: help
        anchors { left: list.right; leftMargin: 60 * S.u; right: parent.right; rightMargin: 90 * S.u; top: list.top; bottom: parent.bottom; bottomMargin: 80 * S.u }
        radius: 22 * S.u
        color: S.panel
        readonly property string rowId: (page.rows[page.idx] || {}).id || ""
        Column {
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 44 * S.u }
            spacing: 22 * S.u
            Image {
                visible: help.rowId === "signin" && !!page.qr
                width: 340 * S.u; height: width
                source: page.qr
                smooth: false
            }
            Text {
                width: parent.width; wrapMode: Text.WordWrap; textFormat: Text.StyledText
                color: S.text2; font.family: S.font; font.pixelSize: S.tMeta; lineHeight: 1.15
                text: ({
                    client: "<b>Make a developer app</b> (once) at developer.spotify.com → Dashboard → <b>Create app</b>:<br>"
                          + "• App name: Couchbox TV · Description: anything<br>"
                          + "• Redirect URIs, add both:<br>&nbsp;&nbsp;<b>" + (page.st.redirect_tailscale || "(Tailscale off: only the next one)") + "</b><br>&nbsp;&nbsp;<b>" + (page.st.redirect_loopback || "http://127.0.0.1:8792/callback") + "</b><br>"
                          + "• Which API: <b>Web API</b><br>"
                          + "Save, open its Settings and copy the <b>Client ID</b>. Press OK here and type or paste it (the phone remote page types for you).<br><br>"
                          + "Others in your home can use it too: add their Spotify e-mail under the app's User Management (up to 5 people).",
                    key: "<b>Soloist</b> is Spotify's own player for devices like this one. Its key has its own page: <b>developer.spotify.com/dashboard/soloist</b> (in the dashboard, <b>Spotify Soloist API Key</b>, not inside your app). Press <b>Generate</b> (it needs Premium). It's not your app's Client ID or Client secret. Press OK here and type or paste it. It's kept only on this TV.",
                    player: "Downloads <b>Spotify Soloist</b> from Spotify and starts it. Spotify's builds last 90 days, so the TV fetches a new one by itself. By using it you accept Spotify's Terms and Conditions of Use.",
                    pair: (page.pl.login_error && !page.pl.logged_in ? "<font color='" + S.danger + "'><b>" + page.pl.login_error + "</b></font><br><br>" : "")
                        + "On your phone, on the same Wi-Fi: open the Spotify app, play anything, tap the <b>speaker icon</b> and choose <b>" + page.device + "</b>. The TV remembers it. After that, phones can also send music here.",
                    signin: page.qr ? "<b>Scan this with your phone</b> and sign in to Spotify. When it's done, this TV shows your music.<br><br>Not on Tailscale? Your phone ends on a page that won't load: copy its address and use the next step."
                                    : "Press OK for a QR code to sign in with your phone.",
                    paste: "If your phone isn't on your tailnet, Spotify sends it to <b>http://127.0.0.1:8792/callback?code=…</b>, which won't load on a phone. Copy that whole address from the phone's address bar, press OK here and type or paste it.",
                    done: page.st.signedIn ? "All set. Press OK for your music." : "You can finish later: Setup is at the bottom of the sidebar.",
                    signout: "Signs this TV out of your Spotify account. The player stays paired.",
                    remove: "Deletes Spotify's player and its pairing from this TV (not your keys)."
                })[help.rowId] || ""
            }
        }
    }
}
