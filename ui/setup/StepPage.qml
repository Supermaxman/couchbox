// One setup step: SettingsPage plus an intro for the left side. Left arrow doesn't leave
// (there's no sidebar); Back goes to the previous step.
import QtQuick
import "../settings"

SettingsPage {
    property string intro: ""
    showHeading: false
    function cont(label, act) { return {kind: "action", label: label || "Continue", act: act || (() => win.next()), primary: true}; }
}
