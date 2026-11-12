// Moments: things the household taught the TV by showing it ("remember this as pet music" while
// it plays). Each one's settings, starting it, and renaming or deleting it. couchboxd keeps them
// (moments.*); the voice service plays them.
import QtQuick

SettingsPage {
    id: p
    title: "Moments"
    subtitle: "While something plays, hold the mic and say “remember this as …”. Start one by saying its name, from its tile on the home screen, or from the phone page."
    property var items: []
    property string active: ""
    readonly property var appNames: ({youtube: "YouTube", jellyfin: "Jellyfin", dropout: "Dropout", "2ndtry": "2nd Try", nebula: "Nebula", twitch: "Twitch"})
    function refresh() {
        T.call("moments.list", {}, r => {                  // (unchanged: the rows aren't rebuilt under the cursor)
            if (JSON.stringify(r.moments) !== JSON.stringify(p.items)) p.items = r.moments;
            if ((r.active || "") !== p.active) p.active = r.active || "";
        });
    }
    Component.onCompleted: refresh()
    Connections { target: T; function onEvent(topic) { if (topic === "settings.changed") p.refresh(); } }
    Timer { interval: 3000; repeat: true; running: p.visible; onTriggered: p.refresh() }    // started or stopped elsewhere

    function change(m, changes) { T.call("moments.update", {id: m.id, changes: changes}, p.refresh); }
    function start(m) {
        T.toast("Starting " + m.name + "…");
        T.call("moments.start", {id: m.id}, r => { T.toast(r.result); p.refresh(); });
    }
    function stop() { T.call("moments.stop", {}, r => { T.toast(r.result); p.refresh(); }); }
    function plays(m) { return (m.title ? "“" + m.title + "” on " : "") + appNames[m.app]; }
    function volumes(m) {
        const v = [100, 80, 60, 40, 20];
        if (v.indexOf(m.volume) < 0) v.push(m.volume);
        return v.sort((a, b) => b - a).map(x => ({label: x === 100 ? "As it is (100%)" : x + "%", value: x}));
    }
    function rowsOf(m) {
        const on = m.id === p.active;
        return [
            T.section(m.name),
            {kind: "choice", label: "Plays", value: plays(m), help: "OK: play what's on now instead.",
             act: () => T.confirm("Change what " + m.name + " plays?", "It plays what's on the TV now instead. Its name and settings stay.", "Change",
                                  () => T.call("moments.capture", {id: m.id}, () => { T.toast(m.name + " plays what's on now."); p.refresh(); }))},
            {kind: "choice", label: "Volume", value: m.volume === 100 ? "As it is" : m.volume + "%",
             help: "The box's own sound level while it plays, under the TV's volume. It goes back when the Moment stops.",
             act: () => T.pick("Volume for " + m.name, volumes(m), m.volume, v => p.change(m, {volume: v}))},
            {kind: "toggle", label: "Repeat", on: m.repeat, help: "Starts again from the beginning when it ends.", act: () => p.change(m, {repeat: !m.repeat})},
            {kind: "toggle", label: "Picture dark", on: m.dark, help: "The screen goes black while the sound plays on. Any button brings the picture back.",
             act: () => p.change(m, {dark: !m.dark})},
            {kind: "toggle", label: "Played when leaving the house", on: m.leaving, help: "The box notes when it starts, as the time you left.",
             act: () => p.change(m, {leaving: !m.leaving})},
            on ? T.action("Stop", p.stop, {value: "Playing now", tone: "good"}) : T.action("Start now", () => p.start(m)),
            T.action("Rename", () => T.askText("Name for " + m.name, m.name, false, n => p.change(m, {name: n}))),
            T.action("Delete", () => T.confirm("Delete " + m.name + "?", "Its tile goes from the home screen and saying its name won't start it.", "Delete",
                                              () => T.call("moments.delete", {id: m.id}, p.refresh)), {danger: true}),
        ];
    }
    rows: {
        T.rev;
        if (!p.items.length)
            return [T.info("No Moments yet", "", {help: "Play something, then hold the mic and say “remember this as pet music”."})];
        let r = [];
        for (const m of p.items) r = r.concat(rowsOf(m));
        return r;
    }
}
