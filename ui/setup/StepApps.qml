// The apps (YouTube, Chromium...) download in the background once the box is online; wait
// here. While setup runs from a USB stick or SD card they wait for the end of setup instead
// (couchbox.install_disk.downloads_held): downloading would stall the stick.
import QtQuick
import "../settings"

StepPage {
    id: p
    title: "Getting your apps"
    intro: st.state === "held"
           ? "YouTube and the web browser (about 1.5 GB) download once setup is done: from " + (st.why.indexOf("SD card") >= 0 ? "the SD card" : "the USB stick")
             + ", downloading now would slow setup down."
           : "YouTube and the web browser are downloading (about 1.5 GB). This only happens once."
    property var st: ({state: "waiting", why: ""})
    Component.onCompleted: poll()
    function poll() { T.call("apps.install_status", {}, r => { p.st = r; if (r.state === "done") win.next(); }, () => {}); }
    Timer { interval: 3000; running: p.st.state !== "held"; repeat: true; onTriggered: p.poll() }
    rows: st.state === "held" ? [cont()]
          : [T.info(st.state === "installing" ? "Installing " + st.app : st.state === "done" ? "Done" : "Waiting for the internet…",
                    st.total ? st.done + " of " + st.total : "", {tone: st.state === "done" ? "good" : ""}),
             cont("Continue (they finish in the background)")]
}
