// Network: Wi-Fi (scan, join with the keyboard or phone, forget), the wired connection, the
// box's name on the network.
import QtQuick

SettingsPage {
    id: p
    title: "Network"
    property var status: ({devices: [], ips: {}})
    property var nets: []
    property bool scanning: false
    function refresh(rescan) {
        T.call("network.status", {}, r => p.status = r);
        p.scanning = true;
        T.call("network.wifi_scan", {rescan: rescan}, r => { p.nets = r; p.scanning = false; }, () => p.scanning = false);
    }
    Component.onCompleted: refresh(true)
    Timer { interval: 15000; running: true; repeat: true; onTriggered: p.refresh(false) }
    Connections { target: T; function onEvent(topic) { if (topic === "network.changed") p.refresh(false); } }

    function join(n) {
        if (n.connected)
            return T.confirm("Forget " + n.ssid + "?", "The box won't join it by itself any more.", "Forget",
                             () => T.call("network.wifi_forget", {ssid: n.ssid}, () => refresh(false)));
        const go = pw => {
            T.toast("Joining " + n.ssid + "…");
            T.call("network.wifi_connect", {ssid: n.ssid, password: pw}, () => { T.toast("Connected to " + n.ssid + "."); refresh(false); });
        };
        if (n.secure) T.askText("Password for " + n.ssid, "", true, go);
        else go("");
    }
    readonly property var wired: status.devices.find(d => d.type === "ethernet" && d.state === "connected")
    readonly property var wifi: status.devices.find(d => d.type === "wifi" && d.state === "connected")

    rows: {
        T.rev;
        const r = [T.section("Connection"),
            T.info(wired ? "Ethernet" : wifi ? "Wi-Fi: " + wifi.connection.replace(/^couchbox-/, "") : "Not connected",
                   Object.values(status.ips).join(", ") || "", {tone: wired || wifi ? "good" : "bad",
                   help: status.connectivity === "full" ? "Online" : status.connectivity === "none" ? "No internet" : ""}),
            T.section(scanning && !nets.length ? "Wi-Fi networks (looking…)" : "Wi-Fi networks")];
        for (const n of nets)
            r.push({kind: "action", label: (n.secure ? "🔒 " : "") + n.ssid, value: (n.connected ? "Connected · " : "") + n.band + " · " + n.signal + "%",
                    tone: n.connected ? "good" : "", help: n.connected ? "OK to forget this network" : "OK to join", act: () => p.join(n)});
        r.push(T.action("Join a hidden network", () => T.askText("Network name", "", false, ssid =>
            T.askText("Password for " + ssid + " (empty if none)", "", true, pw =>
                T.call("network.wifi_connect", {ssid: ssid, password: pw, hidden: true}, () => refresh(false))))));
        r.push(T.action("Scan again", () => refresh(true)));
        r.push(T.section("This box"));
        r.push(T.row("network.hostname"));
        r.push(T.row("network.wifi_country"));
        return r;
    }
}
