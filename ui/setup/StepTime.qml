// Where the box is: the time zone, and the place for the weather (optional).
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Where are you?"
    intro: "For the clock and the weather on the home screen. Search for your city: the time zone comes with it."
    function findPlace() {
        T.askText("Your city or town", T.settings["location.name"] || "", false, q =>
            T.call("location.search", {name: q}, res => {
                if (!res.length) return T.toast("Nothing found for " + q + ".");
                T.pick("Which one?", res.map((x, i) => ({label: x.name, value: i})), -1, i => {
                    const x = res[i];
                    const c = {"location.name": x.name.split(",").slice(0, 2).join(","), "location.lat": x.lat, "location.lon": x.lon};
                    if (x.timezone) c["time.timezone"] = x.timezone;
                    if (x.country && x.country.length === 2) c["network.wifi_country"] = x.country;
                    T.setMany(c);
                });
            }, e => T.toast(e)));
    }
    rows: {
        T.rev;
        const s = T.settings;
        return [{kind: "text", label: "City", value: s["location.name"] || "Not set", act: findPlace},
                T.info("Time zone", s["time.timezone"] || ""),
                T.row("location.units"),
                T.row("home.clock"),
                cont()];
    }
}
