// Date, time and location: time zone, the place for the weather, units, clock.
import QtQuick

SettingsPage {
    id: p
    title: "Date, time and location"
    property var zones: []
    property var status: ({})
    Component.onCompleted: { T.call("time.zones", {}, z => p.zones = z); T.call("time.status", {}, s => p.status = s); }
    function pickZone() {
        const regions = [...new Set(zones.map(z => z.split("/")[0]))];
        T.pick("Region", regions.map(x => ({label: x.replace(/_/g, " "), value: x})), T.settings["time.timezone"].split("/")[0],
               reg => T.pick("Time zone", zones.filter(z => z.split("/")[0] === reg).map(z => ({label: z.split("/").slice(1).join(" / ").replace(/_/g, " ") || z, value: z})),
                             T.settings["time.timezone"], z => T.set("time.timezone", z)));
    }
    function findPlace() {
        T.askText("City or town", T.settings["location.name"] || "", false, q =>
            T.call("location.search", {name: q}, res => {
                if (!res.length) return T.toast("Nothing found for " + q + ".");
                T.pick("Which one?", res.map((x, i) => ({label: x.name, value: i})), -1, i => {
                    const x = res[i];
                    const c = {"location.name": x.name.split(",").slice(0, 2).join(","), "location.lat": x.lat, "location.lon": x.lon};
                    if (x.timezone && x.timezone !== T.settings["time.timezone"]) c["time.timezone"] = x.timezone;
                    T.setMany(c, () => T.toast("Location set" + (c["time.timezone"] ? ", time zone " + x.timezone : "") + "."));
                });
            }));
    }
    rows: {
        T.rev;
        const s = T.settings;
        return [
            T.info("Now", Qt.formatDateTime(new Date(), "dddd d MMMM, " + (s["home.clock"] === "24h" ? "HH:mm" : "h:mm AP")),
                   {help: status.synced === false ? "The clock isn't synced yet (needs the internet)." : ""}),
            {kind: "choice", label: "Time zone", value: s["time.timezone"], act: pickZone},
            {kind: "text", label: "Location", value: s["location.name"] || "Not set", help: "For the weather on the home screen.", act: findPlace},
            T.row("location.units"),
            T.row("home.clock"),
        ];
    }
}
