// Display and sound: resolution (from what the TV offers), interface size, sound output.
import QtQuick

SettingsPage {
    id: p
    title: "Display and sound"
    property var modes: []
    Component.onCompleted: T.call("display.modes", {}, r => p.modes = r.choices)
    rows: {
        T.rev;
        const s = T.settings;
        return [
            {kind: "choice", label: "Resolution", value: s["display.mode"], help: "1080p at 60 Hz suits the Pi best.",
             act: () => T.pick("Resolution", modes.map(m => ({label: m.replace("@", " at ") + " Hz", value: m})), s["display.mode"],
                               m => T.set("display.mode", m))},
            {kind: "choice", label: T.label("appearance.scale"), value: Math.round(s["appearance.scale"] * 100) + "%",
             help: "How big everything looks. 150% suits a big TV from the couch.",
             act: () => T.pick("Interface size", [1.0, 1.25, 1.5, 1.75, 2.0].map(x => ({label: Math.round(x * 100) + "%", value: x})),
                               s["appearance.scale"], x => T.set("appearance.scale", x))},
            T.row("audio.output"),
        ];
    }
}
