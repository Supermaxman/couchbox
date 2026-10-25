# Fresh-hardware test

The run sheet for testing a release on a new, never-used box (milestone M8 in the [plan](PLAN.md#6-fresh-hardware-acceptance-test-m8)). Follow [the install guide](install.md) the way a new user would. Use only what it says: no SSH fixes and no config files typed by hand. Note anything that's unclear in the guide as a failure too.

Record each run in `tests/hardware/RESULTS.md`: date, release, board RAM, bootloader version (Settings → System), SSD, TV model, and pass/fail per row with notes.

## Before you start

- [ ] A Raspberry Pi 5 that has never run Couchbox, with the SSD on the M.2 HAT+ and **no SD card**.
- [ ] A USB stick (16 GB+), Raspberry Pi Imager on a computer, the Fire TV remote, a phone.
- [ ] For debugging only: add your SSH public key in Imager's customisation. You don't need it for the test itself. If something fails, you can then run `ssh <user>@<hostname>.local` and `couchbox doctor`.

## A. Install

| # | Check | Expect |
|---|---|---|
| A1 | Imager with the Couchbox repository URL | Couchbox shows under Raspberry Pi 5; customisation is offered |
| A2 | Write to the stick, with Wi-Fi set in Imager | Writes and verifies |
| A3 | First power-on, stick in a blue port, HDMI 0 | Picture within 3 minutes. CEC wakes the TV and switches input |
| A4 | Setup, Hello | Phone QR in the corner: it opens the phone remote, and its arrows and OK move the setup |
| A5 | Your remote: hold Home 10 s on the Fire TV remote (Fire TV Stick unplugged) | "Paired AR…" within about 20 s. The remote's arrows and OK work |
| A6 | Install to the SSD | Offered with the SSD's name. Progress climbs to 100% in under about 10 minutes |
| A7 | Restart now | Boots from the SSD, with the stick still in. Setup carries on at Internet. The remote and Wi-Fi still work |
| A8 | Unplug the stick, restart from Settings → System | Still boots, from the SSD |
| A9 | Rest of the setup, TV remote only (CEC) | Time zone, name, TV buttons (the Fire remote's power and volume work the TV), updates, extras, apps download |

## B. No Wi-Fi set (a second run: write the stick again)

| # | Check | Expect |
|---|---|---|
| B1 | Write the stick **without** Imager's Wi-Fi, no Ethernet | Setup starts. After about 30 s the corner shows two codes, and a Couchbox-XXXX Wi-Fi exists |
| B2 | Scan code 1, then code 2 | The phone joins it and opens the remote. The arrows work |
| B3 | Internet step: pick home Wi-Fi, type the password on the phone | Joins. The setup Wi-Fi closes. The corner shows a new code on the home network |
| B4 | Wrong password once | "Wrong password". The setup Wi-Fi comes back, and the phone can rejoin it |

## C. Daily use

| # | Check | Expect |
|---|---|---|
| C1 | YouTube 1080p60 for 10 min | No dropped frames (stats for nerds) |
| C2 | Twitch, with chat | Plays. Chat shows |
| C3 | Jellyfin (if you have one): found on the LAN in Settings, HEVC plays | Hardware decoding, no stutter |
| C4 | AirPlay from a phone | Mirrors |
| C5 | Home: move, hide, rename a tile; add a website | Takes effect at once, and survives a restart |
| C6 | TV off with its remote, then on | The box sleeps and wakes with the TV |
| C7 | Settings → Remote access → phone page | Pairs by QR. Typing works in YouTube search |

## D. Options

| # | Check | Expect |
|---|---|---|
| D1 | Tailscale: sign in by QR | Joins the tailnet. The phone page works over HTTPS |
| D2 | Voice: dictation with a speech-to-text endpoint | The mic button types into YouTube search |
| D3 | Encryption, with a passphrase | Re-encrypts while you watch. A restart asks for the passphrase on the TV |
| D4 | Encryption with Tang, over Wi-Fi | A restart unlocks with no prompt |

## E. Updates

| # | Check | Expect |
|---|---|---|
| E1 | Settings → Updates → Check now | Up to date, or the next release is found |
| E2 | Next release published while the box is in standby overnight | Installed by morning. "What's new" in Settings → Updates |
| E3 | Manual mode | Notifies only |

## What to send when something fails

- The row number and what you saw. A phone photo of the TV helps.
- `couchbox doctor` output (Settings → System → Run checks shows the same).
- Logs: `journalctl -b -u 'couchbox*' > couchbox.log` over SSH. Install-to-SSD and setup Wi-Fi problems are in `journalctl -b -u couchboxd`.
