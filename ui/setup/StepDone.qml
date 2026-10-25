import QtQuick
import "../settings"

StepPage {
    title: "You're set"
    intro: "Home goes to the home screen.\nMenu (≡) on an app moves or hides it.\nSettings is the last tile on the home row."
    rows: [{kind: "action", label: "Go to the home screen", act: () => win.finish()}]
}
