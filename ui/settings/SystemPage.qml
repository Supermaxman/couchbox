// System: about this box, checks, memory, restart, setup again, factory reset, licenses.
import QtQuick

SettingsPage {
    id: p
    title: "System"
    property var info: ({})
    Component.onCompleted: T.call("system.info", {}, r => p.info = r)
    function doctor() {
        T.toast("Checking…");
        T.call("system.doctor", {}, r => T.message(r.status === "ok" ? "Everything looks fine" : "Some checks need a look",
            r.checks.map(c => (c.status === "ok" ? "✓ " : c.status === "warn" ? "! " : "✗ ") + c.name + ": " + c.detail).join("\n"), "", ""));
    }
    function factoryReset() {
        T.confirm("Reset Couchbox?", "Every setting, app sign-in and saved key is erased, then the box restarts into setup. Disk encryption stays as it is.", "Reset",
                  () => T.confirm("Really reset?", "This can't be undone.", "Reset everything",
                                  () => T.call("system.factory_reset", {confirm: "RESET", keep_wifi: true}, () => T.toast("Resetting…"))));
    }
    function choices(key, values, fmt) {
        return {kind: "choice", label: T.label(key), value: fmt(T.settings[key]), help: T.spec(key).help || "",
                act: () => T.pick(T.label(key), values.map(v => ({label: fmt(v), value: v})), T.settings[key], v => T.set(key, v))};
    }
    rows: {
        T.rev;
        return [
            T.section("About"),
            T.info("Couchbox " + (info.version || ""), info.os || ""),
            T.info("Hardware", info.model || ""),
            T.info("Temperature", info.temp_c ? info.temp_c + " °C" : "", {tone: info.temp_c > 80 ? "bad" : "", help: info.throttled && info.throttled !== "0x0" ? "Throttled (" + info.throttled + "): check the cooler and power supply" : ""}),
            T.info("Memory", info.mem_total_mb ? Math.round(info.mem_free_mb / 1024 * 10) / 10 + " GB free of " + Math.round(info.mem_total_mb / 1024) + " GB" : ""),
            T.info("Storage", info.disk_total_gb ? info.disk_free_gb + " GB free of " + info.disk_total_gb + " GB" : ""),
            T.action("Run checks", doctor),
            T.section("Memory and storage"),
            choices("apps.idle_minutes", [30, 60, 120, 240, 1440], v => v >= 60 ? (v / 60) + " hour" + (v > 60 ? "s" : "") : v + " minutes"),
            choices("apps.web_cache_mb", [128, 256, 512, 1024], v => v + " MB"),
            choices("system.swap_gb", [0, 2, 4, 8, 16], v => v ? v + " GB" : "Automatic"),
            choices("system.logs_mb", [100, 200, 500, 1000], v => v + " MB"),
            T.section("Restart"),
            T.action("Restart the home screen", () => T.call("system.restart_ui", {}, () => {})),
            T.action("Restart the box", () => T.confirm("Restart now?", "It's back in about a minute.", "Restart", () => T.call("system.reboot", {}, () => {}))),
            T.action("Run the setup again", () => T.call("setup.save", {step: 0, done: false}, () => backend.launch("couchbox-setup"))),
            T.action("Reset everything", p.factoryReset, {danger: true}),
            T.section("About Couchbox"),
            T.action("Open-source licenses", () => T.message("Open source", "Couchbox is free software under the Apache License 2.0. Parts of the home screen come from KDE Plasma Bigscreen (GPL-2.0-or-later). It runs on Ubuntu, KDE Plasma, Qt, mpv and many other projects.\n\nUnofficial apps (Dropout, 2nd Try, Nebula, Twitch) aren't made or endorsed by those services.", "", "github.com/Supermaxman/couchbox")),
        ];
    }
}
