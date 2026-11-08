# A dev box

A dev box is a second Couchbox that stays on all the time for development. You push changed files onto it from a checkout over SSH, run the box checks against it, and capture its screen, with nobody at it. It's also the box for the fresh-hardware test ([hardware-test.md](hardware-test.md), milestone M8).

Keep it separate from the box your household watches. Pushed files and scripted remote presses don't belong on a TV someone is using.

- [Hardware](#hardware)
- [Set it up](#set-it-up)
- [The accounts on the box](#the-accounts-on-the-box)
- [The dev loop](#the-dev-loop)
- [Screenshots and recordings](#screenshots-and-recordings)
- [Running all the time](#running-all-the-time)

## Hardware

Use the [reference hardware](design/first-boot.md#reference-hardware), so that what passes on the dev box passes on a user's box. On a box that never turns off, these parts matter:
- **The official 27 W power supply.** Weaker supplies cause undervoltage under load, and the Pi slows itself down.
- **The Active Cooler.** Without it, long playback throttles.
- **Ethernet.** SSH and pushes don't depend on Wi-Fi.

A PC monitor works as its screen. It has no HDMI-CEC, so the TV-remote and TV power checks (CEC) need a real TV.

## Set it up

1. **Install it the way a user would**, from the latest release image: follow [the install guide](install.md). Don't build your own image. The release image is what users get, and anything not released yet gets pushed over SSH.
2. **Updates: Manual.** Settings → Updates → Updates: Manual. The automatic updater installs every new release when the box is idle, and a dev box is idle most of the time. That would overwrite the files you pushed. With Manual, Settings → Updates shows "Update available" and you install it when you're ready.
   - **Channel: beta**, if the box should also get prereleases (`vX.Y.Z-beta.N`, from the Beta release workflow) to test before a stable release. They show up as available too, and wait for you.
3. **SSH.** Settings → Remote access → SSH: on. Then add your key there, from either of:
   - **Add keys from GitHub**, with your GitHub user name;
   - **Add a key**, pasting the public key (`ssh-ed25519 …`). Open the phone page to paste it from a computer or phone.

   You log in as **admin**: `ssh admin@<name>.local`. It takes keys only, never a password.
4. **Tailscale (optional)**, to reach it from outside your network: Settings → Remote access → Tailscale, then sign in with the QR code. SSH then works on its Tailscale name too.
5. **A short name for it** in `~/.ssh/config` on your computer, so the scripts can use it:
   ```
   Host couchbox-dev
       HostName <name>.local
       User admin
   ```
6. **YouTube: sign in with a test Google account**, not your own. The box check signs in by default (YouTube bot-checks a box that starts many guest streams), it fills that account's History with test plays, and `--menu-test` saves to and removes from its Watch later. `--profile guest` runs without an account.

## The accounts on the box

| Account | What it's for |
|---|---|
| `tv` | The TV session: Plasma, the apps, PipeWire. Logs in by itself. Its user ID differs between boxes: `id -u tv` |
| `admin` | SSH. Keys only (its password is locked), and sudo without a password |
| (Imager's user) | Only if you set a user name in Raspberry Pi Imager. Couchbox doesn't use it |

To run something in the TV session, as `tv`, with its session bus and display:

```sh
u=$(id -u tv)
sudo -u tv env XDG_RUNTIME_DIR=/run/user/$u DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$u/bus WAYLAND_DISPLAY=wayland-0 <command>
```

The remote and the screen tools need no wrapper: `/usr/lib/couchbox/bin/couchbox-remote down ok`.

## The dev loop

No package and no CI run for each change. Push files from a checkout, run the check on the box, and release once at the end.

```sh
ci/box-push.sh couchbox-dev          # this checkout onto the box
ci/box-check.sh couchbox-dev         # the YouTube app's box check; results in build/box-check/
ci/box-check.sh couchbox-dev --perf  # any ci/yt-box-check.py arguments pass through
```

- **`ci/box-push.sh HOST [CHECKOUT]`** copies the Python package (`src/couchbox`), the YouTube app (`ui/youtube`, `bin/couchbox-yt`, its cast service), CouchKit and the settings schema over the installed ones. The next launch of the app picks them up. It records the commit in `/var/lib/couchbox/state/yt-dev`.
- **`ci/box-check.sh HOST [ARGS…]`** copies `ci/yt-box-check.py` to the box and runs it there, muted, then pulls the screenshots and results to `build/box-check/HOST-<time>/` (or `$OUT`). It refuses (exit 3) while someone is using the box: a remote press in the last 10 minutes, an app in front other than the home screen or YouTube, sound playing, or a Frigate pop-up. `FORCE=1` skips the 10 minutes.
- **Push a checkout that has everything already on the box.** A push replaces whole files, so pushing a branch without another branch's changes that you pushed earlier takes those changes off the box.
- **Undo a push** by reinstalling the release's package, then checking that nothing differs from it:
  ```sh
  v=$(couchbox version)
  curl -fLO https://github.com/Supermaxman/couchbox/releases/download/v$v/couchbox_${v}_arm64.deb
  sudo apt install --reinstall ./couchbox_${v}_arm64.deb
  sudo rm -f /var/lib/couchbox/state/yt-dev
  dpkg --verify couchbox   # no output: the box runs the release as shipped
  ```
- **Releases:** with updates on Manual, a new release never lands on the box by itself. Install it from Settings → Updates (or `couchbox update install`) when you're ready. It replaces everything you pushed.

## Screenshots and recordings

```sh
ssh couchbox-dev /usr/lib/couchbox/bin/couchbox-screenshot --width 960 /tmp/shot.png
scp couchbox-dev:/tmp/shot.png .
ssh couchbox-dev /usr/lib/couchbox/bin/couchbox-record start --remote "wait:1 down ok wait:3"
```

The recipes for clips, and the limits, are in [recording.md](recording.md). The remote's buttons are in [ci-and-testing.md](design/ci-and-testing.md#on-the-box-the-remote-screenshots-and-recordings).

## Running all the time

- **Temperature and power:** `vcgencmd get_throttled` should say `throttled=0x0`. Anything else means undervoltage or overheating since the last start. `vcgencmd measure_temp` shows the chip's temperature. Settings → System → Fan: Quiet (the default) lets the chip reach about 80 °C before the fan speeds up. Normal is the Pi's own, cooler curve.
- **Logs:** the journal is kept across restarts, up to Settings → System → Log space (200 MB by default). Raise it for a dev box, to keep a few weeks: `sudo couchbox config set system.logs_mb 1000`. Then `journalctl -b -1 -u 'couchbox*'` shows the previous start.
- **Health:** `couchbox doctor` checks the whole box. Settings → System → Run checks shows the same.
- **The screen stays on.** Couchbox never blanks it, so screenshots and recordings always have a picture. Apps close by themselves after an hour unused (Settings → System).
