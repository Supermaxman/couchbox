// Remote access: Tailscale (sign in with a QR code), SSH (keys only), the phone page.
import QtQuick

SettingsPage {
    id: p
    title: "Remote access"
    property var ts: ({})
    property var ssh: ({keys: []})
    property var phone: ({})
    function refresh() {
        T.call("tailscale.status", {}, r => p.ts = r);
        T.call("ssh.status", {}, r => p.ssh = r);
        T.call("phone.pairing", {}, r => p.phone = r);
    }
    Component.onCompleted: refresh()
    Connections {
        target: T
        function onEvent(topic, d) {
            if (topic === "tailscale.login") T.message("Sign in to Tailscale", "Scan this with your phone and sign in. The box joins your tailnet as " + T.settings["network.hostname"] + ".", backend.qr(d.url), d.url);
            if (topic === "tailscale.changed") { T.closeMessage(); p.refresh(); }
        }
    }
    function signIn() {
        T.toast("Starting Tailscale…");
        T.call("tailscale.up", {}, r => {
            p.ts = r;
            if (r.login_url) T.message("Sign in to Tailscale", "Scan this with your phone and sign in.", backend.qr(r.login_url), r.login_url);
            else if (r.state === "Running") T.toast("Connected to " + r.tailnet + ".");
        });
    }
    rows: {
        T.rev;
        const s = T.settings;
        const running = ts.state === "Running";
        const r = [T.section("Tailscale"),
            T.info(running ? "Connected" : s["tailscale.enabled"] ? (ts.state || "Starting") : "Off",
                   running ? ts.name : "", {tone: running ? "good" : "",
                   help: "Reach this box (and the phone page, over HTTPS) from your devices anywhere, with Tailscale."})];
        if (!running) {
            r.push(T.action("Sign in with a QR code", signIn));
            r.push(T.action("Sign in with an auth key", () => T.askText("Tailscale auth key", "", true,
                k => T.call("tailscale.up", {auth_key: k}, rr => { p.ts = rr; T.toast("Connected."); }))));
        } else {
            r.push(T.row("tailscale.serve_phone_page"));
            r.push(T.action("Turn Tailscale off", () => T.call("tailscale.down", {}, rr => p.ts = rr)));
            r.push(T.action("Sign out of Tailscale", () => T.confirm("Sign out of Tailscale?", "Sign in again to reconnect.", "Sign out",
                () => T.call("tailscale.down", {logout: true}, rr => p.ts = rr)), {danger: true}));
        }
        r.push(T.row("tailscale.tags"));
        r.push(T.section("Phone remote and typing"));
        r.push(T.row("phone.enabled"));
        if (s["phone.enabled"] && phone.url) {
            r.push({kind: "qr", label: "", qr: backend.qr(phone.url)});
            r.push(T.info("Scan it with your phone's camera", phone.base || ""));
            if (phone.code) r.push(T.info("Or open the page and type this code", phone.code, {help: "For a home-screen app on an iPhone, which can't scan"}));
            r.push(T.action("New pairing code", () => T.confirm("Make a new pairing code?", "Phones paired before need to scan the new code.", "New code",
                () => T.call("phone.rotate", {}, rr => p.phone = rr))));
        }
        r.push(T.section("SSH"));
        r.push(T.row("ssh.enabled", {help: "Log in as admin@" + s["network.hostname"] + ".local with a key (never a password)."}));
        r.push(T.info("Keys", ssh.keys.length ? ssh.keys.length + " key" + (ssh.keys.length > 1 ? "s" : "") : "None"));
        r.push(T.action("Add keys from GitHub", () => T.askText("GitHub user name", s["ssh.github_user"] || "", false,
            u => T.call("ssh.import_github", {user: u}, rr => { p.ssh = rr; T.toast(rr.added + " key(s) added."); }))));
        r.push(T.action("Add a key", () => T.askText("Public key (ssh-ed25519 …), easiest from the phone page", "", false,
            k => T.call("ssh.add_key", {key: k}, rr => p.ssh = rr))));
        if (ssh.keys.length)
            r.push(T.action("Remove all keys", () => T.confirm("Remove every SSH key?", "Nobody can log in until you add one again.", "Remove",
                () => T.call("ssh.remove_keys", {}, rr => p.ssh = rr)), {danger: true}));
        return r;
    }
}
