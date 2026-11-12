// Home screen: the order of the apps (OK on one: move, hide, rename), websites as apps,
// clock, weather, theme. Moving: Up/Down carry the app, OK drops it, Back cancels.
import QtQuick

SettingsPage {
    id: p
    title: "Home screen"
    subtitle: "The apps on the home row, left to right. On the home screen itself, hold OK on an app for the same options."
    property var apps: []
    property string carrying: ""                     // app id being moved
    property int carryFrom: -1
    function refresh() { T.call("apps.list", {}, r => p.apps = r); }
    Component.onCompleted: { refresh(); readCameras(); }
    // The morning show's camera: the outside cameras couchbox-morning last saw (in its show file)
    property var showCams: []
    function readFile(path, done) {
        const x = new XMLHttpRequest();
        x.onreadystatechange = () => { if (x.readyState === XMLHttpRequest.DONE) { try { done(JSON.parse(x.responseText || "null")); } catch (e) { done(null); } } };
        x.open("GET", "file://" + path);
        x.send();
    }
    function readCameras() {
        readFile("/var/lib/couchbox/home/home.json", h => {
            if (h && h.morning && h.morning.file) readFile(h.morning.file, s => p.showCams = s && s.cameras ? s.cameras : []);
        });
    }
    function cameraRow() {
        const v = T.settings["home.morning_camera"] || "";
        const known = p.showCams.find(c => c.name === v);
        const auto = (p.showCams.find(c => !!c.auto) || {}).label;
        return T.row("home.morning_camera", {
            value: v ? (known ? known.label : v) : "Automatic" + (auto ? " (" + auto + ")" : ""),
            act: p.showCams.length
                ? () => T.pick("Morning show camera", [{label: "Automatic", value: ""}].concat(p.showCams.map(c => ({label: c.label, value: c.name}))),
                               v, x => T.set("home.morning_camera", x))
                : () => T.askText("Morning show camera (a Frigate camera name)", v, false, x => T.set("home.morning_camera", x.trim()))
        });
    }
    // Today at home's hours: a pick of the hours of the day
    function hourName(h) {
        if (T.settings["home.clock"] === "24h") return String(h % 24).padStart(2, "0") + ":00";
        return h === 0 || h === 24 ? "Midnight" : h === 12 ? "Noon" : (h % 12) + (h < 12 ? " am" : " pm");
    }
    function hourRow(key, first, last) {
        const v = T.settings[key];
        const hours = [];
        for (let h = first; h <= last; h++) hours.push({label: hourName(h), value: h});
        return T.row(key, {value: hourName(v), act: () => T.pick(T.label(key), hours, v, x => T.set(key, x))});
    }
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
        r.push(T.row("home.continue"));
        if (T.settings["media.frigate.url"]) r.push(T.row("home.away"));
        if (T.settings["media.frigate.url"]) r.push(T.row("home.day"));
        if (T.settings["media.frigate.url"] && T.settings["home.day"]) r.push(hourRow("home.day_from", 0, 23), hourRow("home.day_to", 1, 24));
        r.push(T.row("home.morning"));
        if (T.settings["home.morning"] && T.settings["media.frigate.url"]) r.push(cameraRow());
        return r;
    }
}
