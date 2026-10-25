// Remote and TV: pair remotes, the Fire TV remote's TV buttons (IR), HDMI-CEC.
import QtQuick

SettingsPage {
    id: p
    title: "Remote and TV"
    property var devices: []
    property var pairing: ({state: "idle"})
    function refresh() { T.call("remote.devices", {}, r => p.devices = r, () => p.devices = []); }
    Component.onCompleted: refresh()
    Connections {
        target: T
        function onEvent(topic, d) {
            if (topic !== "remote.pairing") return;
            p.pairing = d;
            if (d.state === "paired") { T.closeMessage(); T.toast("Paired " + d.name + "."); p.refresh(); }
            else if (d.state === "found") T.message("Pairing…", "Found " + d.name + ". Keep it close.", "", "");
            else if (d.state === "failed") { T.closeMessage(); T.toast("Not paired: " + (d.reason || "try again") + "."); }
        }
    }
    function pair() {
        T.call("remote.pair_start", {seconds: 60}, () => T.message("Pair a remote",
            "Fire TV remote: hold Home for about 10 seconds, until its light blinks.\n\nOther Bluetooth remotes: put them in pairing mode.\n\nDon't reset a Fire TV remote with Menu + Back + Left: that erases its TV buttons.",
            "", "Looking for remotes…"));
    }
    function programIr() {
        T.call("remote.ir_brands", {}, brands => T.pick("Your TV's brand", brands.map(b => ({label: b.name + (b.tested ? "" : " (untested)"), value: b.id})), "",
            b => T.call("remote.ir_program", {brand: b}, r => T.message("TV buttons programmed", r.message, "", ""))));
    }
    rows: {
        T.rev;
        const r = [T.section("Remotes"), T.action("Pair a remote", pair, {help: "Fire TV remotes and other Bluetooth remotes"})];
        for (const d of devices)
            r.push({kind: "action", label: d.name, value: (d.connected ? "Connected" : "Asleep") + (d.battery ? " · " + d.battery + "%" : ""),
                    tone: d.connected ? "good" : "", help: "OK to forget this remote",
                    act: () => T.confirm("Forget " + d.name + "?", "Pair it again to use it.", "Forget",
                                         () => T.call("remote.forget", {address: d.address}, rr => p.devices = rr))});
        r.push(T.action("Program the Fire TV remote's TV buttons", programIr,
                        {help: "Power, volume and mute then control the TV directly by infrared."}));
        r.push(T.section("The TV (HDMI-CEC)"));
        r.push(T.row("tv.cec.enabled", {help: "Turn the TV on and switch inputs with the box. On the TV: Anynet+ (Samsung), SimpLink (LG), Bravia Sync (Sony)."}));
        r.push(T.row("tv.power_on_with_box"));
        r.push(T.row("tv.standby_with_box"));
        r.push(T.row("tv.volume"));
        r.push(T.row("tv.cec.name"));
        r.push(T.row("tv.inputs", {help: "The TV's HDMI ports the input button steps through (CEC addresses)."}));
        return r;
    }
}
