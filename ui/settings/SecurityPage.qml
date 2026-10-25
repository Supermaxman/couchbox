// Security: disk encryption (passphrase + optional network unlock with Tang, over Wi-Fi too).
import QtQuick

SettingsPage {
    id: p
    title: "Security"
    subtitle: "Encrypt the disk so it can't be read if the box or its drive is taken. It keeps working while it encrypts."
    property var st: ({state: "…"})
    function refresh() { T.call("encryption.status", {}, r => p.st = r); }
    Component.onCompleted: refresh()
    Timer { interval: 5000; running: p.st.state === "encrypting" || p.st.finishing === true; repeat: true; onTriggered: p.refresh() }

    // Encrypt: passphrase twice -> network unlock? -> Wi-Fi at boot? -> confirm
    function encrypt() {
        T.askText("Choose a passphrase (at least 8 characters)", "", true, a => {
            if (a.length < 8) return T.toast("Use at least 8 characters.");
            T.askText("Type the passphrase again", "", true, b => {
                if (a !== b) return T.toast("They didn't match. Try again.");
                askTang(a, []);
            });
        });
    }
    function askTang(pass, tang) {
        T.pick("Unlock by itself at home?", [
            {label: "No: always ask for the passphrase at boot (needs a USB keyboard)", value: "no"},
            {label: tang.length ? "Add another Tang server" : "Yes: use a Tang server on my network", value: "add"},
            ...(tang.length ? [{label: "Done adding servers", value: "done"}] : [])], "", v => {
            if (v === "no") return confirm(pass, [], false);
            if (v === "done") return askWifi(pass, tang);
            T.askText("Tang server address, e.g. http://192.168.1.10:7500", "http://", false, url =>
                T.call("encryption.check_tang", {url: url}, r =>
                    T.confirm("Trust this Tang server?", "Its key thumbprint:\n" + r.thumbprints.join("\n") +
                              "\n\nIt should match what tang-show-keys prints on the server.", "Trust",
                              () => askTang(pass, tang.concat([r.url])))));
        });
    }
    function askWifi(pass, tang) {
        T.pick("Unlock over Wi-Fi too?", [
            {label: "Ethernet only", value: false},
            {label: "Ethernet or Wi-Fi (the Wi-Fi password is kept on the boot partition)", value: true}], false,
            w => confirm(pass, tang, w));
    }
    function confirm(pass, tang, wifi) {
        T.confirm("Encrypt this box?", "It takes 15 to 30 minutes in the background. Don't unplug it meanwhile (if it loses power, it carries on later).\n\n" +
                  "Keep the passphrase somewhere safe: without it (and " + (tang.length ? "away from your Tang server" : "with no network unlock") +
                  ") nobody can start this box, including you.", "Encrypt", () =>
            T.call("encryption.encrypt", {passphrase: pass, tang: tang, wifi: wifi}, r => { p.st = r; T.toast("Encrypting…"); }));
    }
    rows: {
        T.rev;
        const r = [T.section("Disk encryption"),
                   T.info(st.state === "encrypted" ? "Encrypted" : st.state === "encrypting" ? "Encrypting… " + (st.percent !== undefined && st.percent !== null ? st.percent + "%" : "")
                          : st.state === "unprotected" ? "Not protected" : st.state === "plain" ? "Not encrypted" : st.state,
                          "", {help: st.detail || "", tone: st.state === "encrypted" ? "good" : st.state === "encrypting" ? "warn" : "bad"})];
        if (st.state === "unprotected")
            r.push(T.action("Encrypt this box", encrypt));
        if (st.state === "plain")
            r.push(T.info("This box's disk wasn't set up for it", "", {help: "Boxes flashed from the Couchbox image can encrypt from here. Installed on an existing system: see the encryption guide."}));
        if (st.state === "encrypted" && st.finishing === false && st.keyslots !== undefined) {
            r.push(T.action("Change the passphrase", () => T.askText("Current passphrase", "", true, old =>
                T.askText("New passphrase", "", true, n => T.call("encryption.change_passphrase", {old: old, new: n}, rr => { p.st = rr; T.toast("Passphrase changed."); })))));
            r.push(T.info("Network unlock", st.tang && st.tang.length ? st.tang.join(", ") : "Off"));
            r.push(T.action(st.tang && st.tang.length ? "Change network unlock" : "Set up network unlock (Tang)", () =>
                T.askText("Passphrase (to change the unlock)", "", true, pass =>
                    T.askText("Tang server addresses, separated by spaces (empty: none)", (st.tang || []).join(" "), false, urls =>
                        T.call("encryption.set_tang", {passphrase: pass, urls: urls.split(/\s+/).filter(x => x)}, rr => p.st = rr)))));
            if (st.tang && st.tang.length)
                r.push({kind: "toggle", label: "Unlock over Wi-Fi too", on: !!st.wifi_at_boot,
                        help: "Uses the Wi-Fi the box is on now. Its password is then kept on the boot partition.",
                        act: () => T.call("encryption.set_wifi", {enabled: !st.wifi_at_boot}, rr => p.st = rr)});
        }
        if (st.finishing === true || (st.state === "encrypted" && st.keyslots === undefined))
            r.push(T.action("Finish: set the passphrase", () => T.askText("Passphrase", "", true, pass =>
                T.call("encryption.finish", {passphrase: pass}, rr => p.st = rr))));
        return r;
    }
}
