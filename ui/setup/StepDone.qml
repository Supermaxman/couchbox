import QtQuick
import "../settings"

StepPage {
    title: "You're set"
    intro: "Home goes to the home screen.\nHold OK on an app to move or hide it.\nSettings is the last tile on the home row."
    rows: [{kind: "action", label: "Go to the home screen", act: () => win.finish()}]
}
