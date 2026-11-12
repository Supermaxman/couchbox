# Boot screen

From power-on to Home the TV shows the Couchbox logo, a progress bar and one line saying what
the box is doing, instead of scrolling console text. It has to start in the initrd, because a
box that unlocks its disk over the network spends most of its boot there.

## What it shows

| Step | Line | Ends when |
|---|---|---|
| Joining Wi-Fi (network unlock only) | Joining Wi-Fi… | Ethernet or Wi-Fi has a DHCP lease |
| Unlocking | Unlocking… | the disk is unlocked (`cryptsetup.target`) |
| Starting | Starting Couchbox… | the TV session starts; the Plasma splash carries on to Home |

- **The bar** gives each step the share of the bar it took on recent boots, fills at that
  pace, and slows to a stop short of the step's end while it waits. It never runs ahead of
  the boot. Plymouth draws up to 85 %; the Plasma splash (`org.couchbox.boot`, the same logo,
  bar and line in the same places) fills the rest as Plasma starts, so the hand-over doesn't show.
- **The log panel** slides up over the bottom third with the last lines of the journal. It
  opens by itself when a step takes more than twice as long as usual (at least 12 s more),
  or when the unlock is stuck. Any key on a USB keyboard shows or hides it, except while the
  passphrase is being asked for (keys type it then; Esc still switches to Plymouth's full
  text log).
- **When the network unlock can't finish** (no DHCP lease within 45 s, or no unlock after
  twice the usual time and at least 50 s), the bar turns amber and the line says why: "Can't
  join Wi-Fi" or "Can't reach the unlock server", then "Still trying. To unlock now, type the
  disk passphrase on a USB keyboard." with the passphrase field. Clevis keeps trying meanwhile,
  so a server that comes back still unlocks the box.
- **Passphrase-only boxes** see "Type the disk passphrase on a USB keyboard" at once.

## How it's built

- `system/plymouth/couchbox/`: the Plymouth script theme. Laid out at 3840x2160 and scaled.
  Text is drawn with Inter through Plymouth's pango label plugin (`plymouth-label`); the
  images come from `system/plymouth/make-images.sh`.
- `bin/couchbox-boot-status`: tells the theme where the boot is (`plymouth update
  --status=cb:…`), feeds it the journal (`display-message`), and at the hand-over saves how
  long each step took to `/var/lib/couchbox/boot-pace`.
- `system/dracut/89couchbox-boot/`: puts the helper, the pace, the fonts and its units into
  every initrd. Plymouth's own dracut module brings the theme.
- `plymouth-quit.service.d/couchbox.conf`: saves the pace and quits with `--retain-splash`,
  so the last frame stays until the TV session draws.
- The kernel command line gets `quiet splash loglevel=3 vt.global_cursor_default=0
  plymouth.ignore-serial-consoles rd.driver.export` and `video=<output>:<display.mode>`: the
  boot uses the TV session's resolution, so the TV doesn't switch modes (and go black) at the
  hand-over. (`rd.driver.export` is what Ubuntu's dracut does anyway; said outright, it stops
  a deprecation warning being printed on the TV.)
- `/etc/plymouth/plymouthd.conf` gets `DeviceTimeout=2`: a Pi's initrd has no DRM device, only
  the firmware's framebuffer, and Plymouth waits that long for one before drawing on it
  (Ubuntu's 8 s left the TV black for the first 10 s).
- The real system's log feeder must not `Conflicts=` with `plymouth-quit.service`: both start
  in the same boot transaction and systemd drops one of them, which left the boot screen up
  over the TV session in testing.

## Installing it safely

`couchbox boot-screen apply` (run by the package's postinst) makes `couchbox` Plymouth's
theme. When the theme or its initrd side changed, it builds a new initrd and installs it as a
test boot: flash-kernel writes `/boot/firmware/new`, the box tries it once at its next restart
(`piboot-try`), and keeps it only if that boot gets to the real system; otherwise it falls back
to the current boot. The splash arguments go on the test boot's command line only.

The pace in the initrd is the one from when it was last built (a kernel update or a change
here rebuilds it); the system's copy is updated at every boot.
