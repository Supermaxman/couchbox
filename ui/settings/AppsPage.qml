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
    readonly property var unofficial: [["dropout", "Dropout"], ["2ndtry", "2nd Try"], ["nebula", "Nebula"], ["twitch", "Twitch"]]
    rows: {
        T.rev;
        const s = T.settings;
        const r = [T.section("Jellyfin"),
            T.row("media.jellyfin.url", {help: "Your Jellyfin server. The Jellyfin tile shows once it's set."}),
            T.action(finding ? "Looking for Jellyfin…" : "Find Jellyfin on my network", findJellyfin),
            T.row("media.jellyfin.client"),
            T.section("Seerr"),
            T.row("media.seerr.url", {help: "Your Seerr server, for requesting movies and shows."}),
            T.secretRow("media.seerr.api_key", {help: "Seerr → Settings → General → API key. The Seerr app and voice requests use it."}),
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
