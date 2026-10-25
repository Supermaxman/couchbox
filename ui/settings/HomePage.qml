// Home screen: the order of the apps (OK on one: move, hide, rename), websites as apps,
// clock, weather, theme. Moving: Up/Down carry the app, OK drops it, Back cancels.
import QtQuick

SettingsPage {
    id: p
    title: "Home screen"
    subtitle: "The apps on the home row, left to right. On the home screen itself, press Menu (≡) on an app for the same options."
    property var apps: []
    property string carrying: ""                     // app id being moved
    property int carryFrom: -1
    function refresh() { T.call("apps.list", {}, r => p.apps = r); }
    Component.onCompleted: refresh()
    Connections { target: T; function onEvent(topic) { if (topic === "settings.changed") p.refresh(); } }

    readonly property var onHome: apps.filter(a => a.on_home && a.hideable)
    readonly property var others: apps.filter(a => !a.on_home && a.hideable && a.available)
    readonly property var unavailable: apps.filter(a => !a.available && a.hideable && a.id.indexOf("-web") < 0)

    moving: carrying !== ""
    function move(d) {
        const i = onHome.findIndex(a => a.id === carrying);
        if (d === 0) {                                // Back: put it where it was
            if (carryFrom >= 0 && carryFrom !== i) T.call("home.move", {app: carrying, index: carryFrom}, refresh);
            p.carrying = ""; return true;
        }
        const j = i + d;
        if (j < 0 || j >= onHome.length) return true;
        const a = apps.slice();
        const ai = a.findIndex(x => x.id === onHome[i].id), aj = a.findIndex(x => x.id === onHome[j].id);
        const tmp = a[ai]; a[ai] = a[aj]; a[aj] = tmp;
        p.apps = a;
        list.currentIndex += d;
        return true;
    }
    function drop() {
        const i = onHome.findIndex(a => a.id === carrying);
        T.call("home.move", {app: carrying, index: i}, refresh);
        p.carrying = "";
    }
    function options(a) {
        if (carrying) return drop();
        const o = [];
        if (a.on_home) o.push({label: "Move", value: "move"});
        o.push({label: a.on_home ? "Hide from the home screen" : "Show on the home screen", value: "toggle"});
        o.push({label: "Rename", value: "rename"});
        if (a.id.startsWith("web-")) o.push({label: "Remove this website", value: "remove"});
        T.pick(a.display_name, o, "", v => {
            if (v === "move") { carrying = a.id; p.carryFrom = onHome.findIndex(x => x.id === a.id); }
            else if (v === "toggle") T.call("home.hide", {app: a.id, hidden: a.on_home}, refresh);
            else if (v === "rename") T.askText("Name for " + a.name, a.display_name, false, n => T.call("home.rename", {app: a.id, name: n}, refresh));
            else if (v === "remove") T.call("home.remove_web", {app: a.id}, refresh);
        });
    }
    function appRow(a, i) {
        return {kind: "app", label: a.display_name, value: a.on_home ? (i + 1) + "" : "Hidden",
                help: carrying === a.id ? "Up and Down move it, OK puts it here" : a.unofficial ? "Unofficial app" : "", alwaysHelp: carrying === a.id,
                act: () => p.options(a)};
    }
    rows: {
        T.rev;
        const r = [T.section("On the home row")];
        onHome.forEach((a, i) => r.push(appRow(a, i)));
        if (others.length) {
            r.push(T.section("Hidden"));
            others.forEach(a => r.push(appRow(a, -1)));
        }
        if (unavailable.length) {
            r.push(T.section("Needs setting up"));
            unavailable.forEach(a => r.push(T.info(a.name, "Set up in Apps and media", {help: "Needs: " + a.missing.join(", ")})));
        }
        r.push(T.section("Add"));
        r.push(T.action("Add a website as an app", () => T.askText("Website address", "https://", false, url =>
            T.askText("Name on the home screen", url.replace(/^https?:\/\/(www\.)?/, "").split("/")[0], false, name =>
                T.call("home.add_web", {name: name, url: url}, () => { T.toast(name + " added."); refresh(); })))));
        r.push(T.action("Reset to the default order", () => T.confirm("Reset the home row?", "Every app goes back to its usual place and hidden apps come back.", "Reset",
            () => T.call("home.reset", {}, refresh))));
        r.push(T.section("Look"));
        r.push(T.row("appearance.theme"));
        r.push(T.row("home.clock"));
        r.push(T.row("home.weather", {help: T.settings["location.name"] ? "Weather for " + T.settings["location.name"] : "Set a location in Date, time, location first"}));
        return r;
    }
}
