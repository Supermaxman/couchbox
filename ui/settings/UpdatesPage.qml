// Updates: Couchbox's own (signed releases from GitHub), Ubuntu's, and when they install.
import QtQuick

SettingsPage {
    id: p
    title: "Updates"
    property var st: ({history: []})
    property bool checking: false
    function refresh() { T.call("updates.status", {}, r => p.st = r); }
    Component.onCompleted: refresh()
    Timer { interval: 5000; running: p.st.running === true; repeat: true; onTriggered: p.refresh() }
    Connections { target: T; function onEvent(topic, d) { if (topic.startsWith("updates")) p.refresh(); } }
    function when(t) { return t ? Qt.formatDateTime(new Date(t * 1000), "d MMM, h:mm AP") : "never"; }
    rows: {
        T.rev;
        const s = T.settings;
        const r = [T.section("Couchbox"),
            T.info("Version " + (st.version || ""), st.available ? "Update available: " + st.available : st.running ? "Updating…" : "Up to date",
                   {tone: st.available ? "warn" : "good",
                    help: (st.last_error ? "Last check failed: " + st.last_error : "Checked " + when(st.last_check)) + (st.waiting ? ". Waiting: " + st.waiting : "")})];
        r.push(T.action(checking ? "Checking…" : "Check now", () => { p.checking = true;
            T.call("updates.check", {}, rr => { p.checking = false; p.st = rr; T.toast(rr.available ? "Update available: " + rr.available : "Up to date."); },
                   e => { p.checking = false; T.toast(e); }); }));
        if (st.available) {
            r.push(T.action("What's new in " + st.available, () => T.message("Couchbox " + st.available, st.notes_md || "No notes.", "", "")));
            r.push(T.action("Install now", () => T.confirm("Install Couchbox " + st.available + "?", "The home screen restarts when it's done (a minute or two).", "Install",
                () => T.call("updates.install", {}, () => { T.toast("Installing…"); refresh(); }))));
        }
        if (st.can_rollback)
            r.push(T.action("Go back to the previous version", () => T.confirm("Roll back?", "The previous version is reinstalled.", "Roll back",
                () => T.call("updates.rollback", {}, () => T.toast("Rolling back…"))), {danger: true}));
        r.push(T.row("updates.mode", {help: s["updates.mode"] === "automatic" ? "Installs when nobody's watching (TV off or no remote use for 30 minutes), during the install hours."
                                                                         : "Settings shows when there's an update; you install it."}));
        r.push(T.row("updates.channel", {help: "Beta gets new versions first, with more risk."}));
        r.push({kind: "choice", label: T.label("updates.window"), value: s["updates.window"],
                act: () => T.pick("Install hours", ["02:00-06:00", "00:00-06:00", "03:00-05:00", "09:00-17:00", "00:00-23:59"].map(x => ({label: x.replace("-", " to "), value: x})),
                                  s["updates.window"], x => T.set("updates.window", x))});
        r.push(T.section("Ubuntu and apps"));
        r.push(T.row("updates.os", {help: "Ubuntu updates install by themselves; the apps (YouTube, Chromium…) update weekly."}));
        if (st.history && st.history.length) {
            r.push(T.section("History"));
            for (const h of st.history.slice().reverse().slice(0, 6))
                r.push(T.info(h.event === "installed" ? "Updated to " + h.version : h.event === "rolled_back" ? "Rolled back to " + h.to : h.event === "failed" ? h.version + " failed its checks" : h.event,
                              when(h.t), {tone: h.event === "installed" ? "good" : "bad", help: h.reason || (h.problems || []).join("; ")}));
        }
        return r;
    }
}
