// Pair a Fire TV remote (or another Bluetooth remote), or carry on with the TV's remote.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Your remote"
    intro: "Have an Amazon Fire TV remote? Hold its Home button for about 10 seconds, until the light blinks. It pairs by itself.\n\nIf it's paired with a Fire TV Stick, unplug the Stick first. Don't reset it with Menu + Back + Left: that erases its TV buttons."
    property var devices: []
    // pairing itself runs in Main (from Hello on): this page follows it
    Component.onCompleted: { T.call("remote.devices", {}, r => p.devices = r, () => {}); T.call("remote.pair_start", {seconds: 0}, r => win.pair = r, () => {}); }
    Connections {
        target: T
        function onEvent(topic, d) {
            if (topic === "remote.pairing" && d.state === "paired") { T.toast("Paired " + d.name + ". Try its buttons."); T.call("remote.devices", {}, r => p.devices = r); }
        }
    }
    rows: {
        const r = [win.pairRow(false)];
        for (const d of devices)
            r.push(T.info(d.name, d.connected ? "Connected" : "Paired", {tone: "good"}));
        r.push(cont(devices.length ? "Continue" : "Skip: use the TV's remote"));
        return r;
    }
}
