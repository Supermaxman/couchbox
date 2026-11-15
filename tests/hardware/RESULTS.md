# Fresh-hardware test results

One section per run of [the run sheet](../../docs/hardware-test.md), newest first.

## 2026-11-15 · v0.28.0
Board: Pi 5 8 GB · SSD: Samsung PM9C1a 256 GB on the M.2 HAT+ · TV: a PC monitor (no HDMI-CEC) · stick: Kingston DataTraveler 3.0 · remote: Fire TV
| Row | Result | Notes |
|---|---|---|
| A3 | fail | The first power-on of the freshly written stick looped in the bootloader ("Failed to open partition 5"; tried NVMe, then USB, then again). The second power-on of the same, unchanged stick booted. Cause unknown; watch for it on the next run. Then kernel text instead of the boot screen, and setup didn't open (fixed in #148) |
| A4 | fail | Nothing on Hello about the Fire TV remote, though it was already listening for one. No phone code for about a minute (the setup Wi-Fi opened at 127 s of uptime) and no word that one was coming. Fixed: Hello says how to pair and shows its status; the phone card says when its codes come |
| A5 | fail | Once online, the box downloaded its apps (Flatpak, about 1.5 GB) and apt updates onto the stick: I/O pressure "full" at 98% for 20 minutes, everything stalled. bluetoothd connected to the remote 3 times but never sent a pairing request in time, and the remote dropped each time. With the downloads stopped, it paired on the first try. Nothing in the journal traced the pairing. Fixed: no downloads while setup runs from a stick or SD card; each pairing step is logged |
| A6 | fail | The screen never got a progress update and never offered Restart now, although the copy finished (the setup app wasn't subscribed to the install's events). It sat at 0% for good; the box was restarted over SSH. Fixed: the app subscribes to them, and the screen also asks every 3 s. Also now: an overall bar, and each step's own (formatting with mkfs's progress, GB copied) |
| A9 | n/a | No HDMI-CEC on a PC monitor |
| B1 | fail | (No Ethernet or Wi-Fi in this run.) Setup Wi-Fi came up, but the Wi-Fi region stayed unset (`country 00`) although the time zone was set. Fixed: the region comes from the time zone |
| B2 | fail | iPhone: "Unable to join the network". With Wi-Fi power save on (the image's default) it neither listed nor joined it; with power save off it joined at once (one A/B test). Fixed: power save off on the setup Wi-Fi |

<!--
## YYYY-MM-DD · vX.Y.Z
Board: Pi 5 8 GB · bootloader: … · SSD: … · TV: … · remote: Fire TV …
| Row | Result | Notes |
|---|---|---|
| A1 | pass | |
-->
