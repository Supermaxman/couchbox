import QtQuick
import "../settings"

StepPage {
    title: "Name this box"
    intro: "The name shows in your TV's input list, in AirPlay on your iPhone, and on your network."
    rows: {
        T.rev;
        return [T.row("network.hostname", {label: "Name", help: "Lowercase letters, numbers and dashes, like livingroom"}),
                T.action("Use “livingroom”", () => T.set("network.hostname", "livingroom")),
                T.action("Use “bedroom”", () => T.set("network.hostname", "bedroom")),
                cont()];
    }
}
