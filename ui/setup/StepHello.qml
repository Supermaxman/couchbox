import QtQuick
import "../settings"

StepPage {
    title: "Hello"
    intro: "Let's get your TV box ready. It takes a few minutes.\n\nUse your TV's remote: the arrows and OK work here. Or use your phone as the remote: scan the code below with its camera."
    rows: [T.info("You'll set up", "", {help: "A remote · Wi-Fi · time zone · a name · updates · optional extras"}), cont("Start")]
}
