import QtQuick
import "../settings"

StepPage {
    title: "Updates"
    intro: "Couchbox improves often. Automatic updates install at night, when nobody's watching, and undo themselves if something goes wrong."
    rows: {
        T.rev;
        const m = T.settings["updates.mode"];
        return [{kind: "action", label: "Automatic (recommended)", value: m === "automatic" ? "✓" : "", tone: "good",
                 act: () => T.set("updates.mode", "automatic", () => win.next())},
                {kind: "action", label: "Manual: I'll install them from Settings", value: m === "manual" ? "✓" : "",
                 act: () => T.set("updates.mode", "manual", () => win.next())}];
    }
}
