// Couchbox Settings: shared state and look. Every change goes through couchboxd (backend.call),
// which validates it and makes it take effect; events from it keep this in step.
pragma Singleton
import QtQuick

QtObject {
    id: t

    property real u: 1                                   // Main sets height / 1080
    // the graphite look of the home screen
    readonly property color bg: "#0b0d12"
    readonly property color side: "#10131a"
    readonly property color panel: "#151922"
    readonly property color panel2: "#1d2230"
    readonly property color line: "#2a3040"
    readonly property color text: "#f2f4f7"
    readonly property color dim: "#8b93a3"
    readonly property color accent: "#7aa2ff"
    readonly property color accentInk: "#0b0d12"
    readonly property color good: "#4ade80"
    readonly property color warn: "#fbbf24"
    readonly property color bad: "#f87171"
    readonly property string font: "Inter"
    readonly property real edge: 64 * u

    property var settings: ({})                          // every setting's value
    property var schema: ({settings: {}, secrets: {}, pages: {}})
    property var secrets: ({})                           // name -> set?
    property int rev: 0                                  // bumps on any change: pages re-read

    signal askText(string title, string text, bool password, var done)
    signal pick(string title, var options, var current, var done)
    signal confirm(string title, string text, string yes, var done)
    signal message(string title, string text, string qr, string extra)
    signal closeMessage()
    signal toast(string text)
    signal event(string topic, var data)

    // couchboxd: call("settings.set", {changes: {...}}, done, fail)
    property int nextId: 1
    property var pending: ({})
    function call(method, params, done, fail) {
        const id = nextId++;
        pending[id] = {done: done, fail: fail};
        const body = JSON.stringify(params || {});
        // sent after the window has finished loading, so the reply's receiver is connected
        Qt.callLater(() => backend.call(id, method, body));
    }
    function reply(id, json) {
        if (Qt.application.arguments.indexOf("--debug") >= 0) console.log("reply", id, json.slice(0, 120));
        const p = pending[id];
        delete pending[id];
        if (!p) return;
        const r = JSON.parse(json);
        try {
            if (r.error !== undefined) {
                if (p.fail) p.fail(r.error); else toast(r.error);
            } else if (p.done) p.done(r.result);
        } catch (e) {
            // the page that asked was closed meanwhile: nothing to update
        }
    }

    function load() {
        call("settings.schema", {}, r => { schema = r; rev++; });
        call("settings.get", {}, r => { settings = r; rev++; });
        call("secrets.status", {}, r => { secrets = r; rev++; });
    }
    function set(key, value, done) {
        const c = {}; c[key] = value;
        setMany(c, done);
    }
    function setMany(changes, done) {
        call("settings.set", {changes: changes}, r => {
            const s = Object.assign({}, settings);
            for (const k in r.changed) s[k] = r.changed[k];
            for (const k in changes) if (!(k in r.changed)) s[k] = changes[k];
            settings = s; rev++;
            for (const n of r.notes || []) toast(n);
            if (done) done(r);
        });
    }
    function setSecret(name, value, done) {
        call("secrets.set", {name: name, value: value}, r => {
            const s = Object.assign({}, secrets); s[name] = r[name]; secrets = s; rev++;
            toast(value ? "Saved." : "Removed.");
            if (done) done();
        });
    }
    function onEvent(topic, json) {
        const d = JSON.parse(json);
        if (topic === "settings.changed") {
            const s = Object.assign({}, settings);
            for (const k in d) s[k] = d[k];
            settings = s; rev++;
        } else if (topic === "secrets.changed") {
            const s = Object.assign({}, secrets);
            for (const k in d) s[k] = d[k];
            secrets = s; rev++;
        }
        event(topic, d);
    }

    // ------------------------------------------------------------------ display helpers
    function spec(key) { return schema.settings[key] || {}; }
    function label(key) { return spec(key).label || key; }
    readonly property var names: ({
        "off": "Off", "on": "On", "auto": "Automatic", "12h": "12-hour", "24h": "24-hour",
        "dictation": "Dictation and simple commands", "assistant": "Assistant",
        "native": "Native (hardware HEVC)", "web": "Web app", "overlay": "Over the video", "side": "Beside the video",
        "tv": "The TV's volume", "box": "This box's volume", "automatic": "Automatic", "manual": "Manual",
        "stable": "Stable", "beta": "Beta", "security": "Security updates", "all": "All updates",
        "imperial": "°F, miles", "metric": "°C, km", "graphite": "Graphite", "neon": "Neon", "amber": "Amber",
        "sakura": "Sakura", "matrix": "Matrix"})
    function nice(v) {
        if (v === true) return "On";
        if (v === false) return "Off";
        if (v === "" || v === undefined || v === null) return "Not set";
        if (Array.isArray(v)) return v.length ? v.join(", ") : "None";
        return names[v] !== undefined ? names[v] : String(v);
    }
    function value(key) { return settings[key]; }

    // A row for one setting: toggles flip, choices open a list, text opens the keyboard.
    function row(key, extra) {
        const s = spec(key);
        const v = settings[key];
        const r = {key: key, label: s.label || key, help: s.help || "", value: nice(v)};
        if (s.type === "bool") {
            r.kind = "toggle"; r.on = !!v; r.value = "";
            r.act = () => set(key, !settings[key]);
        } else if (s.type === "enum") {
            r.kind = "choice";
            r.act = () => pick(r.label, s.values.map(x => ({label: nice(x), value: x})), v, x => set(key, x));
        } else if (s.type === "int" || s.type === "number") {
            r.kind = "text";
            r.act = () => askText(r.label, String(v), false, x => set(key, s.type === "int" ? parseInt(x) : parseFloat(x)));
        } else if (s.type === "list") {
            r.kind = "text";
            r.act = () => askText(r.label + " (separate with spaces)", (v || []).join(" "), false,
                                  x => set(key, x.split(/[\s,]+/).filter(y => y)));
        } else {
            r.kind = "text";
            r.value = v ? (s.type === "text" ? v.split("\n")[0] + (v.indexOf("\n") >= 0 ? " …" : "") : v) : "Not set";
            r.act = () => askText(r.label, v || "", false, x => set(key, x));
        }
        return Object.assign(r, extra || {});
    }
    function secretRow(name, extra) {
        const s = schema.secrets[name] || {};
        return Object.assign({key: name, label: s.label || name, help: s.help || "", kind: "text",
                              value: secrets[name] ? "Set ••••" : "Not set",
                              act: () => askText(s.label || name, "", true, x => setSecret(name, x))}, extra || {});
    }
    function section(title) { return {kind: "section", label: title}; }
    function info(label, value, extra) { return Object.assign({kind: "info", label: label, value: value}, extra || {}); }
    function action(label, act, extra) { return Object.assign({kind: "action", label: label, act: act}, extra || {}); }
}
