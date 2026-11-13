// Pop-ups: when a camera sees something picked here, its live picture pops up in a corner of
// the TV over whatever is on (couchbox-frigate-popup shows it). These are its settings
// (media.frigate.popup.*), saved through couchboxd as they change; the pop-up follows at once.
// Up/Down move. OK switches a row, steps a choice, or shows the test pop-up; Left/Right step a
// choice (and the test's camera). Left on the other rows, and Back, go to the sidebar.
import QtQuick

FocusScope {
    id: page
    property var s: ({})                     // the settings, short keys: enabled, cameras, labels, severity ...
    property bool running: true              // the pop-up service is up
    property bool loading: true
    property string problem: ""
    property int idx: 0
    property int testIdx: 0
    property int saving: 0
    signal toRail()

    readonly property var secs: [10, 15, 20, 30, 45, 60, 90, 120, 180, 300]
    readonly property var quiet: [0, 30, 60, 120, 300, 600, 1800, 3600]
    // what the cameras track (frigate.py's config()), and anything chosen before that they no longer do
    readonly property var labelList: {
        const out = F.labels.slice();
        for (const n of (s.labels || []))
            if (!out.some(l => l.name === n)) out.push({name: n, label: titled(n), kind: "object"});
        return out;
    }
    readonly property var testCams: { const on = F.cameras.filter(c => camOn(c.name)); return on.length ? on : F.cameras; }
    readonly property var rows: {
        const r = [{kind: "switch", label: "Pop-ups", on: !!s.enabled,
                    sub: s.enabled ? "On: a camera's picture pops up over whatever is on the TV" : "Off: nothing pops up"},
                   {kind: "test", label: "Test pop-up", value: (testCams[testIdx] || {label: ""}).label,
                    sub: "Shows a camera live now, labelled as a test"},
                   choice("severity", "Show for", ["alert", "any"], ["Alerts only", "Alerts and detections"], "")];
        F.cameras.forEach((c, i) => r.push({kind: "camera", name: c.name, label: c.label, on: camOn(c.name), section: i === 0 ? "Cameras" : ""}));
        labelList.forEach((l, i) => r.push({kind: "label", name: l.name, label: l.label, icon: l.kind, on: labelOn(l.name), section: i === 0 ? "What they see" : ""}));
        r.push(choice("seconds", "Shows for", secs, secs.map(duration), "Look and timing", "Longer while it's still going on, up to 3 times as long"));
        r.push(choice("cooldown", "Then that camera waits", quiet, quiet.map(duration), "", "Before it can pop up again"));
        r.push(choice("position", "Corner", ["top-right", "top-left", "bottom-right", "bottom-left"], ["Top right", "Top left", "Bottom right", "Bottom left"], ""));
        r.push(choice("size", "Size", ["small", "medium", "large"], ["Small", "Medium", "Large"], ""));
        r.push(choice("picture", "Picture", ["live", "snapshots"], ["Live video", "Snapshots"], "",
                      s.picture === "snapshots" ? "A new picture every second: lighter on a busy box" : "The camera's live video, without sound"));
        return r;
    }
    onRowsChanged: idx = Math.min(idx, rows.length - 1)

    function titled(n) { return n.split(/[_-]/).filter(w => w).map(w => w[0].toUpperCase() + w.slice(1)).join(" "); }
    function duration(t) {
        if (t === 0) return "No wait";
        if (t === 3600) return "1 hour";
        return t < 60 ? t + " s" : Math.floor(t / 60) + " min" + (t % 60 ? " " + t % 60 + " s" : "");
    }
    function choice(key, label, values, names, section, sub) {
        const i = values.indexOf(s[key]);
        return {kind: "choice", key: key, label: label, values: values, section: section, sub: sub || "",
                value: i >= 0 ? names[i] : (typeof s[key] === "number" ? duration(s[key]) : String(s[key] || ""))};
    }
    // no cameras or labels chosen means all of them
    function camOn(name) { return !(s.cameras || []).length || s.cameras.indexOf(name) >= 0; }
    function labelOn(name) { return !(s.labels || []).length || s.labels.indexOf(name) >= 0; }

    function load() {
        loading = true; problem = "";
        F.call("popup", {}, r => { s = r.settings; running = r.running; loading = false; },
               e => { problem = e; loading = false; });
    }
    onVisibleChanged: if (visible) load()

    function save(ch) {
        const before = s, n = ++saving;
        s = Object.assign({}, s, ch);
        F.call("popupSet", {changes: ch}, r => { if (n === page.saving) { page.s = r.settings; page.running = r.running; } },
               e => { if (n === page.saving) page.s = before; F.toast(e); });
    }
    // turn one camera (or label) on or off; all on is saved as [] (everything, also what's added later)
    function toggle(key, all, name, on, what) {
        let chosen = all.filter(n => on(n));
        if (on(name)) {
            if (chosen.length <= 1) return F.toast("Keep one " + what + " on, or turn pop-ups off at the top.");
            chosen = chosen.filter(n => n !== name);
        } else chosen.push(name);
        save({[key]: all.every(n => chosen.indexOf(n) >= 0) ? [] : all.filter(n => chosen.indexOf(n) >= 0)});
    }
    function step(row, d) {
        if (row.kind === "test") { if (testCams.length) testIdx = (testIdx + d + testCams.length) % testCams.length; return; }
        const vals = row.values, cur = s[row.key];
        let i = vals.indexOf(cur);
        if (i >= 0) i = (i + d + vals.length) % vals.length;
        else {                                   // set to something else elsewhere: the next step from it
            const up = vals.findIndex(v => v > cur), down = vals.length - 1 - vals.slice().reverse().findIndex(v => v < cur);
            i = d > 0 ? (up >= 0 ? up : 0) : (down < vals.length ? down : vals.length - 1);
        }
        save({[row.key]: vals[i]});
    }
    function runTest() {
        const c = testCams[testIdx];
        F.call("popupTest", {camera: c ? c.name : ""}, r => F.toast("Showing " + (r.camera || "a camera") + " as a test pop-up."), e => F.toast(e));
    }
    function activate() {
        const r = rows[idx];
        if (!r || loading) return;
        if (r.kind === "switch") save({enabled: !s.enabled});
        else if (r.kind === "test") runTest();
        else if (r.kind === "choice") step(r, 1);
        else if (r.kind === "camera") toggle("cameras", F.cameras.map(c => c.name), r.name, camOn, "camera");
        else if (r.kind === "label") toggle("labels", labelList.map(l => l.name), r.name, labelOn, "kind of thing");
    }
    function stepper(r) { return r && (r.kind === "choice" || r.kind === "test"); }

    function ensureVisible() {
        const it = rep.itemAt(idx);
        if (!it) return;
        if (idx === 0) { flick.contentY = 0; return; }
        const top = list.y + it.y - 10 * F.u, bottom = list.y + it.y + it.height + 40 * F.u;
        if (top < flick.contentY) flick.contentY = Math.max(0, top);
        else if (bottom > flick.contentY + flick.height) flick.contentY = Math.min(bottom - flick.height, Math.max(0, flick.contentHeight - flick.height));
    }
    onIdxChanged: ensureVisible()

    Keys.onUpPressed: idx = Math.max(0, idx - 1)
    Keys.onDownPressed: idx = Math.min(rows.length - 1, idx + 1)
    Keys.onLeftPressed: { if (stepper(rows[idx])) step(rows[idx], -1); else toRail(); }
    Keys.onRightPressed: if (stepper(rows[idx])) step(rows[idx], 1)
    Keys.onReturnPressed: activate()
    Keys.onEnterPressed: activate()

    Flickable {
        id: flick
        anchors { fill: parent; rightMargin: F.edge - 30 * F.u }
        contentHeight: list.y + list.height + 80 * F.u
        interactive: false
        clip: true
        Behavior on contentY { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

        Column {                                     // the title, what this is
            id: head
            x: 56 * F.u; y: 48 * F.u
            width: list.width
            spacing: 14 * F.u
            Row {
                spacing: 20 * F.u
                Text { id: heading; text: "Pop-ups"; color: F.text; font.family: F.font; font.pixelSize: F.tTitle; font.weight: Font.Bold }
                Text { anchors.baseline: heading.baseline; text: "Over whatever is on the TV"; color: F.dim; font.family: F.font; font.pixelSize: F.tMeta + 2 * F.u }
            }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "When a camera chosen here sees one of the things chosen here, its live picture pops up in a corner of the TV. "
                      + "On the remote, OK opens that camera here, and Back dismisses it."
                color: F.text2; font.family: F.font; font.pixelSize: F.tMeta
            }
            Text {
                width: parent.width
                visible: !page.loading && (!!page.problem || !page.running)
                wrapMode: Text.WordWrap
                text: page.problem || "The pop-up isn't running on this TV right now: it starts with the TV's session (couchbox-frigate-popup)."
                color: F.detection; font.family: F.font; font.pixelSize: F.tMeta
            }
        }

        Column {
            id: list
            x: 56 * F.u
            y: head.y + head.height + 30 * F.u
            width: Math.min(1100 * F.u, flick.width - 56 * F.u - 30 * F.u)
            spacing: 10 * F.u
            Repeater {
                id: rep
                model: page.rows
                delegate: Column {
                    id: rowCol
                    required property var modelData
                    required property int index
                    readonly property bool cur: page.activeFocus && page.idx === index
                    readonly property bool primary: modelData.kind === "test"
                    readonly property bool hasSwitch: ["switch", "camera", "label"].indexOf(modelData.kind) >= 0
                    width: list.width
                    spacing: 10 * F.u
                    Text {
                        visible: !!rowCol.modelData.section
                        topPadding: 26 * F.u
                        leftPadding: 6 * F.u
                        text: (rowCol.modelData.section || "").toUpperCase()
                        color: F.faint; font.family: F.font; font.pixelSize: 20 * F.u; font.weight: Font.Bold; font.letterSpacing: 2 * F.u
                    }
                    Rectangle {
                        width: parent.width
                        height: (rowCol.modelData.sub ? 92 : 74) * F.u
                        radius: 12 * F.u
                        color: rowCol.primary ? (rowCol.cur ? F.accent : "#1d4ed8") : rowCol.cur ? F.panel2 : F.panel
                        border.color: rowCol.cur ? F.focus : F.line
                        border.width: (rowCol.cur ? 3 : 1) * F.u
                        // off: the rest still shows (and changes) what it would do
                        opacity: !page.s.enabled && rowCol.modelData.kind !== "switch" && !rowCol.primary ? 0.55 : 1

                        KindBadge {
                            id: icon
                            visible: rowCol.modelData.kind === "label"
                            x: 22 * F.u; anchors.verticalCenter: parent.verticalCenter
                            kind: rowCol.modelData.icon || "object"
                            size: 46 * F.u
                            fill: F.panel2
                        }
                        Column {
                            anchors { left: parent.left; leftMargin: icon.visible ? 86 * F.u : 28 * F.u; right: side.left; rightMargin: 20 * F.u; verticalCenter: parent.verticalCenter }
                            spacing: 4 * F.u
                            Text { width: parent.width; text: rowCol.modelData.label; color: F.text; font.family: F.font; font.pixelSize: 28 * F.u; font.weight: Font.DemiBold; elide: Text.ElideRight }
                            Text { width: parent.width; visible: !!rowCol.modelData.sub; text: rowCol.modelData.sub || ""; color: rowCol.primary ? "#dbeafe" : F.dim; font.family: F.font; font.pixelSize: 21 * F.u; elide: Text.ElideRight }
                        }
                        Item {
                            id: side
                            anchors { right: parent.right; rightMargin: 28 * F.u; top: parent.top; bottom: parent.bottom }
                            width: rowCol.hasSwitch ? switchPill.width : chooser.width
                            Rectangle {                  // an on/off switch
                                id: switchPill
                                visible: rowCol.hasSwitch
                                anchors.verticalCenter: parent.verticalCenter
                                width: 76 * F.u; height: 42 * F.u; radius: height / 2
                                color: rowCol.modelData.on ? F.accent : F.panel2
                                border.color: rowCol.modelData.on ? F.accent : F.faint; border.width: 2 * F.u
                                Rectangle {
                                    width: parent.height - 10 * F.u; height: width; radius: width / 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: rowCol.modelData.on ? parent.width - width - 5 * F.u : 5 * F.u
                                    color: rowCol.modelData.on ? "white" : F.dim
                                    Behavior on x { NumberAnimation { duration: 120 } }
                                }
                            }
                            Row {                        // a choice: ◀ value ▶ (the arrows while it has focus; their room always, so the value stays put)
                                id: chooser
                                visible: !rowCol.hasSwitch
                                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                spacing: 16 * F.u
                                Text { opacity: rowCol.cur ? 1 : 0; text: "◀"; color: rowCol.primary ? "white" : F.text; font.family: F.font; font.pixelSize: 26 * F.u }
                                Text {
                                    width: Math.min(implicitWidth, rowCol.width * 0.4)
                                    text: rowCol.modelData.value || ""
                                    elide: Text.ElideRight
                                    color: rowCol.primary ? "white" : rowCol.cur ? F.text : F.text2
                                    font.family: F.font; font.pixelSize: 26 * F.u; font.weight: rowCol.primary ? Font.DemiBold : Font.Normal
                                }
                                Text { opacity: rowCol.cur ? 1 : 0; text: "▶"; color: rowCol.primary ? "white" : F.text; font.family: F.font; font.pixelSize: 26 * F.u }
                            }
                        }
                    }
                }
            }
        }
    }
    Text {
        anchors.centerIn: parent
        visible: page.loading
        text: "Loading…"
        color: F.dim; font.family: F.font; font.pixelSize: 30 * F.u
    }
}
