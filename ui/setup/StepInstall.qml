// Running from a USB stick or SD card with an SSD inside: copy the system onto the SSD.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Install to the SSD"
    intro: job.state === "running"
           ? "Copying Couchbox to " + (job.label || "the SSD") + ". It takes about 5 minutes: leave the box on. The TV can stay on this screen."
           : "Couchbox is running from " + (st.booted_from === "mmc" ? "the SD card" : "the USB stick") + ". Copy it to the SSD inside the box: it's faster, and "
           + (st.booted_from === "mmc" ? "the card" : "the stick") + " is free again afterwards.\n\nIt takes about 5 minutes. Everything on the SSD is erased."
    property var st: ({booted_from: "usb", targets: [], job: {state: "idle"}})
    property var job: st.job || {state: "idle"}
    function refresh() { T.call("install.status", {}, r => { p.st = r; p.job = r.job; }, () => {}); }
    Component.onCompleted: refresh()
    Connections {
        target: T
        function onEvent(topic, d) { if (topic === "install.progress") p.job = d; }
    }
    // events bring the progress; this makes sure it, Done and Restart now show even if one is missed
    Timer { interval: 3000; repeat: true; running: p.job.state === "running"; onTriggered: p.refresh() }
    function install(t) {
        T.confirm("Install to " + t.label + "?", "Everything on it is erased, and Couchbox is copied onto it.", "Install", () => {
            // after the restart, the wizard carries on from the next step, on the SSD
            T.call("setup.save", {step: win.step + 1, completed: win.completed.concat(["Install"])}, () => {});
            T.call("install.start", {device: t.path}, r => p.job = r);
        });
    }
    // the whole install's bar, then each phase with its own: done (full), now (moving), next (empty)
    readonly property var stages: [{id: "prepare", label: "Prepare the SSD"}, {id: "format", label: "Format it"},
                                   {id: "copy", label: "Copy the system"}, {id: "finish", label: "Make it bootable"}]
    function gb(b) { return (b / 1e9).toFixed(1); }
    rows: {
        const j = job;
        const r = [];
        if (j.state === "running") {
            const now = Math.max(0, stages.findIndex(x => x.id === (j.stage || "prepare")));
            r.push(T.info("Step " + (now + 1) + " of " + stages.length, (j.percent || 0) + "%", {progress: (j.percent || 0) / 100, key: "overall"}));
            r.push(T.section("Steps"));
            stages.forEach((x, i) => {
                if (i < now) r.push(T.info(x.label, "Done", {tone: "good", progress: 1}));
                else if (i > now) r.push(T.info(x.label, "", {progress: 0}));
                else if (x.id === "copy" && j.total)
                    r.push(T.info(x.label, j.detail || gb(j.copied || 0) + " of " + gb(j.total) + " GB", {progress: Math.min(1, (j.copied || 0) / j.total), busy: true}));
                else if (x.id === "format")
                    r.push(T.info(x.label, Math.round(100 * (j.fraction || 0)) + "%", {progress: j.fraction || 0, busy: true}));
                else r.push(T.info(x.label, j.detail || "", {progress: -1, busy: true}));
            });
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
