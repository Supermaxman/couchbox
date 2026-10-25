// Ethernet, or pick a Wi-Fi network and type its password.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Internet"
    intro: "Couchbox needs the internet for apps, updates and the clock.\n\nPlugged into Ethernet? You're all set. Otherwise choose your Wi-Fi."
    property var status: ({devices: [], connectivity: ""})
    property var nets: []
    function refresh(rescan, bounce) {
        T.call("network.status", {}, r => p.status = r);
        T.call("network.wifi_scan", {rescan: rescan, bounce: !!bounce}, r => p.nets = r, () => {});
    }
    Component.onCompleted: refresh(true)
    Timer { interval: 8000; running: true; repeat: true; onTriggered: p.refresh(false) }
    readonly property bool online: status.connectivity === "full"
    function join(n) {
        const go = pw => {
            T.toast("Joining " + n.ssid + "…");
            T.call("network.wifi_connect", {ssid: n.ssid, password: pw}, () => { T.toast("Connected."); refresh(false); });
        };
        if (n.secure) T.askText("Password for " + n.ssid, "", true, go); else go("");
    }
    rows: {
        const r = [T.info(online ? "You're online" : "Not online yet", Object.values(status.ips || {}).join(", "), {tone: online ? "good" : "warn"})];
        if (online) r.push(cont());
        r.push(T.section("Wi-Fi networks"));
        for (const n of nets)
            r.push({kind: "action", label: (n.secure ? "🔒 " : "") + n.ssid, value: (n.connected ? "Connected · " : "") + n.band + " · " + n.signal + "%",
                    tone: n.connected ? "good" : "", act: () => p.join(n)});
        r.push(T.action("Join a hidden network", () => T.askText("Network name", "", false, ssid =>
            T.askText("Password (empty if none)", "", true, pw => T.call("network.wifi_connect", {ssid: ssid, password: pw, hidden: true}, () => refresh(false))))));
        r.push(T.action("Look again", () => refresh(true, true)));
        if (!online) r.push(cont("Continue without internet"));
        return r;
    }
}
