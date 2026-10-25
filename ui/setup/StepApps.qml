// The apps (YouTube, Chromium...) download in the background from the start; wait here.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Getting your apps"
    intro: "YouTube and the web browser are downloading (about 1.5 GB). This only happens once."
    property var st: ({state: "waiting"})
    Component.onCompleted: poll()
    function poll() { T.call("apps.install_status", {}, r => { p.st = r; if (r.state === "done") win.next(); }, () => {}); }
    Timer { interval: 3000; running: true; repeat: true; onTriggered: p.poll() }
    rows: [T.info(st.state === "installing" ? "Installing " + st.app : st.state === "done" ? "Done" : "Waiting for the internet…",
                  st.total ? st.done + " of " + st.total : "", {tone: st.state === "done" ? "good" : ""}),
           cont("Continue (they finish in the background)")]
}
