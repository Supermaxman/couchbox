// Optional: media servers, voice, Tailscale, encryption. All can wait for Settings.
import QtQuick
import "../settings"

StepPage {
    title: "Extras"
    intro: "All optional, and all in Settings later. Set up what you use now, or continue."
    rows: {
        T.rev;
        const s = T.settings;
        return [
            T.section("Your media"),
            T.row("media.jellyfin.url", {help: "Your Jellyfin server, e.g. http://192.168.1.20:8096"}),
            T.action("Find Jellyfin on my network", () => T.call("media.jellyfin_discover", {}, sv => sv.length
                ? T.pick("Jellyfin servers", sv.map(x => ({label: x.name + " · " + x.url, value: x.url})), "", u => T.set("media.jellyfin.url", u))
                : T.toast("No Jellyfin server answered."))),
            T.row("media.seerr.url"),
            T.section("Voice"),
            T.row("voice.mode"),
            T.row("voice.stt.url", {help: "An OpenAI-compatible speech-to-text server (e.g. faster-whisper, speaches)"}),
            T.section("More"),
            T.action("Remote access, encryption, SSH…", () => backend.launch("couchbox-settings"), {help: "Opens Settings"}),
            cont()];
    }
}
