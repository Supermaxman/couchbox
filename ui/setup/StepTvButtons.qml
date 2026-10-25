// The Fire TV remote's Power and Volume buttons control the TV by infrared, once programmed.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "TV buttons"
    intro: "A Fire TV remote's Power, Volume and Mute buttons can control your TV directly. Choose your TV's brand to set them up."
    property var devices: []
    Component.onCompleted: T.call("remote.devices", {}, r => { p.devices = r; if (!r.some(d => d.remote)) win.next(); }, () => win.next())
    rows: [
        T.action("Samsung", () => T.call("remote.ir_program", {brand: "samsung"}, r => T.message("Done", r.message, "", ""))),
        T.info("Other brands", "", {help: "Not yet: the volume buttons control the TV over HDMI-CEC instead."}),
        cont("Continue")]
}
