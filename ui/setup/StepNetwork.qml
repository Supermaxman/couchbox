// Ethernet, or pick a Wi-Fi network and type its password.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Internet"
    intro: "Couchbox needs the internet for apps, updates and the clock.\n\nPlugged into Ethernet? You're all set. Otherwise choose your Wi-Fi."
    property var status: ({devices: [], connectivity: ""})
    property var nets: []
    property bool scanning: false
    property string joining: ""            // the network being joined, while it's joined
    function refresh(rescan, bounce) {
        T.call("network.status", {}, r => p.status = r);
        if (rescan) p.scanning = true;
        T.call("network.wifi_scan", {rescan: rescan, bounce: !!bounce}, r => { p.nets = T.keepOrder(p.nets, r, n => n.ssid); if (rescan) p.scanning = false; },
               () => { if (rescan) p.scanning = false; });
    }
    Component.onCompleted: refresh(true)
    Timer { interval: 8000; running: true; repeat: true; onTriggered: p.refresh(false) }
    readonly property bool online: status.connectivity === "full"
    function join(n) {
        const go = pw => {
            p.joining = n.ssid;
            T.call("network.wifi_connect", {ssid: n.ssid, password: pw}, () => { p.joining = ""; T.toast("Connected."); refresh(false); },
                   e => { p.joining = ""; T.toast(e); });
        };
        if (n.secure) T.askText("Password for " + n.ssid, "", true, go); else go("");
    }
    rows: {
        const r = [T.info(online ? "You're online" : "Not online yet", Object.values(status.ips || {}).join(", "), {tone: online ? "good" : "warn", key: "status"})];
        if (online) r.push(cont());
        r.push(T.section("Wi-Fi networks"));
        if (!nets.length && scanning) r.push(T.info("Looking for networks", "", {busy: true, key: "looking"}));
        for (const n of nets)
            r.push({kind: "action", label: (n.secure ? "🔒 " : "") + n.ssid,
                    value: joining === n.ssid ? "Joining" : (n.connected ? "Connected · " : "") + n.band + " · " + n.signal + "%",
                    busy: joining === n.ssid, tone: n.connected ? "good" : "", act: () => p.join(n)});
        r.push(T.action("Join a hidden network", () => T.askText("Network name", "", false, ssid =>
            T.askText("Password (empty if none)", "", true, pw => T.call("network.wifi_connect", {ssid: ssid, password: pw, hidden: true}, () => refresh(false))))));
        r.push(T.action("Look again", () => refresh(true, true), {value: scanning ? "Looking" : "", busy: scanning}));
        if (!online) r.push(cont("Continue without internet"));
        return r;
    }
}
