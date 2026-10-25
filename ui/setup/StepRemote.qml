// Pair a Fire TV remote (or another Bluetooth remote), or carry on with the TV's remote.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Your remote"
    intro: "Have an Amazon Fire TV remote? Hold its Home button for about 10 seconds, until the light blinks. It pairs by itself.\n\nDon't reset it with Menu + Back + Left: that erases its TV buttons."
    property var pstate: ({state: "searching"})
    property var devices: []
    Component.onCompleted: { T.call("remote.devices", {}, r => p.devices = r, () => {}); T.call("remote.pair_start", {seconds: 0}, () => {}); }
    Connections {
        target: T
        function onEvent(topic, d) {
            if (topic !== "remote.pairing") return;
            p.pstate = d;
            if (d.state === "paired") { T.toast("Paired " + d.name + ". Try its buttons."); T.call("remote.devices", {}, r => p.devices = r); }
            if (d.state === "failed" || d.state === "stopped") Qt.callLater(() => T.call("remote.pair_start", {seconds: 0}, () => {}));
        }
    }
    rows: {
        const state = pstate;
        const r = [T.info(state.state === "paired" ? "Paired " + state.name : state.state === "pairing" ? "Pairing " + (state.name || "") + "…"
                          : state.state === "found" ? "Found " + state.name : "Looking for remotes…", "",
                          {tone: state.state === "paired" ? "good" : "", help: state.state === "paired" ? "Press a few buttons on it to check." : ""})];
        for (const d of devices)
            r.push(T.info(d.name, d.connected ? "Connected" : "Paired", {tone: "good"}));
        r.push(cont(devices.length ? "Continue" : "Skip: use the TV's remote"));
        return r;
    }
}
