// Running from a USB stick or SD card with an SSD inside: copy the system onto the SSD.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Install to the SSD"
    intro: "Couchbox is running from " + (st.booted_from === "mmc" ? "the SD card" : "the USB stick") + ". Copy it to the SSD inside the box: it's faster, and "
           + (st.booted_from === "mmc" ? "the card" : "the stick") + " is free again afterwards.\n\nIt takes about 5 minutes. Everything on the SSD is erased."
    property var st: ({booted_from: "usb", targets: [], job: {state: "idle"}})
    property var job: st.job || {state: "idle"}
    Component.onCompleted: T.call("install.status", {}, r => { p.st = r; p.job = r.job; })
    Connections {
        target: T
        function onEvent(topic, d) { if (topic === "install.progress") p.job = d; }
    }
    function install(t) {
        T.confirm("Install to " + t.label + "?", "Everything on it is erased, and Couchbox is copied onto it.", "Install", () => {
            // after the restart, the wizard carries on from the next step, on the SSD
            T.call("setup.save", {step: win.step + 1, completed: win.completed.concat(["Install"])}, () => {});
            T.call("install.start", {device: t.path}, r => p.job = r);
        });
    }
    rows: {
        const j = job;
        const r = [];
        if (j.state === "running") {
            r.push(T.info((j.step || "Copying") + "…", (j.percent || 0) + "%", {help: "Leave the box on. The TV can stay on this screen."}));
        } else if (j.state === "done") {
            if (j.next === "restart") {
                r.push(T.info("Copied to " + j.label, "", {tone: "good", help: "Restart, and the box runs from the SSD. Unplug the USB stick any time after."}));
                r.push(cont("Restart now", () => T.call("system.reboot", {}, () => {})));
            } else {
                r.push(T.info("Copied to " + j.label, "", {tone: "good",
                    help: "Shut down, then take out the SD card and plug the power back in. Setup carries on from the SSD."}));
                r.push(cont("Shut down", () => T.call("system.poweroff", {}, () => {})));
            }
            return r;
        } else {
            if (j.state === "failed") r.push(T.info("The copy failed", "", {tone: "bad", help: j.error || ""}));
            for (const t of st.targets || [])
                r.push({kind: "action", label: "Install to " + t.label, act: () => p.install(t), primary: true});
            if (!(st.targets || []).length) r.push(T.info("No SSD found", "", {tone: "warn", help: "Check the SSD is seated in the M.2 HAT+, or carry on from the stick."}));
        }
        if (j.state !== "running")
            r.push(cont("Skip: keep running from " + (st.booted_from === "mmc" ? "the SD card" : "the USB stick")));
        return r;
    }
}
