// The first screen. A Fire TV remote pairs from here on (Main keeps looking), and the phone
// card on the left says when its codes come: without a TV remote over HDMI-CEC, those are the
// two ways to press Start.
import QtQuick
import "../settings"

StepPage {
    title: "Hello"
    intro: "Let's get your TV box ready. It takes a few minutes."
    rows: [win.pairRow(true),
           T.info("Your TV's remote", "", {help: "Its arrows and OK work here if your TV supports HDMI-CEC."}),
           cont("Start")]
}
