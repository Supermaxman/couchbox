// Apps and media: media servers (Jellyfin, Seerr), the apps' own options, casting.
import QtQuick

SettingsPage {
    id: p
    title: "Apps and media"
    property bool finding: false
    function findJellyfin() {
        finding = true;
        T.call("media.jellyfin_discover", {}, servers => {
            p.finding = false;
            if (!servers.length)
                return T.message("No Jellyfin server found", "None answered on this network. Type its address instead, e.g. http://192.168.1.20:8096", "", "");
            T.pick("Jellyfin servers on your network", servers.map(s => ({label: s.name + "  ·  " + s.url, value: s.url})), "",
                   url => T.set("media.jellyfin.url", url));
        }, e => { p.finding = false; T.toast(e); });
    }
    // the YouTube tile's app ("native" means hardware HEVC elsewhere on this page)
    readonly property var ytApps: ({native: "Couchbox's own", vacuumtube: "VacuumTube"})
    // quiet hours: "22:00-07:00" as the clock shows it ("10 PM to 7 AM"), or none
    readonly property var quietChoices: ["", "21:00-07:00", "22:00-07:00", "22:00-08:00", "23:00-07:00", "00:00-07:00"]
    function hhmm(t) {
        const h = parseInt(t.slice(0, 2)), m = t.slice(3);
        if (T.settings["home.clock"] === "24h") return t;
        return (h % 12 || 12) + (m === "00" ? "" : ":" + m) + (h < 12 ? " AM" : " PM");
    }
    function quietName(v) { return v ? (v.slice(0, 5) === "00:00" ? "Midnight" : hhmm(v.slice(0, 5))) + " to " + hhmm(v.slice(6)) : "None"; }
    function quietRow(key) {
        const v = T.settings[key];
        return T.row(key, {kind: "choice", value: quietName(v),
                           act: () => T.pick(T.label(key), quietChoices.map(x => ({label: quietName(x), value: x})), v, x => T.set(key, x))});
    }
    readonly property bool place: !!(T.settings["location.name"] || T.settings["location.lat"] || T.settings["location.lon"])
    readonly property var unofficial: [["dropout", "Dropout"], ["2ndtry", "2nd Try"], ["nebula", "Nebula"], ["twitch", "Twitch"]]
    rows: {
        T.rev;
        const s = T.settings;
        const r = [T.section("Jellyfin"),
            T.row("media.jellyfin.url", {help: "Your Jellyfin server. The Jellyfin tile shows once it's set."}),
            T.action(finding ? "Looking for Jellyfin…" : "Find Jellyfin on my network", findJellyfin),
            T.row("media.jellyfin.client"),
            T.section("YouTube"),
            T.row("media.youtube.client", {value: ytApps[s["media.youtube.client"]] || "",
                                           act: () => T.pick("YouTube app", Object.keys(ytApps).map(x => ({label: ytApps[x], value: x})),
                                                             s["media.youtube.client"], x => T.set("media.youtube.client", x))}),
            T.section("Seerr"),
            T.row("media.seerr.url", {help: "Your Seerr server, for requesting movies and shows."}),
            T.secretRow("media.seerr.api_key", {help: "Seerr → Settings → General → API key. The Seerr app and voice requests use it."}),
            T.section("Frigate"),
            T.row("media.frigate.url", {help: "Your Frigate server (cameras), e.g. https://frigate.example.ts.net or http://192.168.1.20:8971. The Frigate tile shows once it's set; sign in from the app."}),
            T.row("media.frigate.popup.enabled"),
            T.section("Weather pop-ups"),
            T.row("weather.popup.rain", {help: place ? T.spec("weather.popup.rain").help : "Set your town in Settings → Time first."}),
            quietRow("weather.popup.rain_quiet"),
            T.row("weather.popup.warnings"),
            quietRow("weather.popup.warnings_quiet"),
            T.action("Show a test pop-up", () => T.pick("Test pop-up", [{label: "Rain soon", value: "rain"}, {label: "Weather warning", value: "warning"}], "",
                                                      k => T.call("weather.popup_test", {kind: k}, () => T.toast("Showing a test pop-up."), e => T.toast(e)))),
            T.section("Search"),
            T.row("apps.search.ai_answer", {help: s["voice.llm.url"] ? "A short answer written by the assistant's model from Google's results, shown above them and labelled AI. Summarize and Ask work on any page either way."
                                                                   : "Needs the voice assistant's model (Settings → Voice). Then Search can also summarize pages."}),
            T.section("Maps and Weather"),
            T.secretRow("apps.maps.google_api_key", {help: "Optional. With a Google Maps Platform key, Maps uses Google: drive times with traffic, transit, Google's places and map; and Weather shows Google's air quality and pollen. Without one Maps uses OpenStreetMap (no traffic or transit) and Weather Open-Meteo's air quality (pollen only in Europe). Make the key in the Google Cloud console with the Routes, Places (New), Map Tiles, Air Quality and Pollen APIs on; typing it is easiest from the phone page."}),
            T.section("Movies & TV"),
            T.info("Looks up movies, shows and people. With Seerr set up it uses Seerr; without, add a free TMDB key.", ""),
            T.secretRow("media.tmdb.token", {help: "Only without Seerr: themoviedb.org → Settings → API → API Read Access Token. IMDb ratings download once a day by themselves."}),
            T.section("Watching"),
            T.row("apps.player.captions"),
            {kind: "choice", label: T.label("apps.youtube.captions"), value: s["apps.youtube.captions"] ? s["apps.youtube.captions"] : "Off",
             act: () => T.pick("YouTube captions", [{label: "Off", value: ""}, {label: "English", value: "en"}, {label: "Spanish", value: "es"},
                                                    {label: "French", value: "fr"}, {label: "German", value: "de"}, {label: "Portuguese", value: "pt"},
                                                    {label: "Japanese", value: "ja"}], s["apps.youtube.captions"], v => T.set("apps.youtube.captions", v))},
            T.row("apps.twitch.chat"),
            T.row("apps.twitch.skip_ads"),
            T.section("Unofficial apps"),
            T.info("These apps aren't made or endorsed by the services. They use your own account.", "")];
        for (const [id, name] of unofficial) {
            const off = (s["apps.disabled"] || []).indexOf(id) >= 0;
            r.push({kind: "toggle", label: name, on: !off, act: () => {
                const d = (s["apps.disabled"] || []).filter(x => x !== id);
                if (!off) d.push(id);
                T.set("apps.disabled", d);
            }});
        }
        r.push(T.section("Casting"));
        r.push(T.row("apps.airplay.enabled"));
        r.push(T.row("apps.airplay.name"));
        r.push(T.row("apps.airplay.pin", {help: "4 digits shown on your iPhone's screen to type. Empty: no PIN."}));
        r.push(T.row("apps.fcast.enabled"));
        return r;
    }
}
