# Packages, image and installer

## Packages

| Package | Arch | Contents | Built by |
|---|---|---|---|
| `couchbox` | all | The Python package, apps (QML), the home-screen overlay, system files (units, udev, dracut module, config snippets), app manifests, defaults and schema, the release-signing public key | `ci.yml` / `release.yml` on every change and tag |
| `couchbox-media` | arm64 | `/opt/couchbox/ffmpeg-rpi` (Raspberry Pi FFmpeg fork, the same FFmpeg version as Ubuntu's libav*, so it's an ABI drop-in) and `/opt/couchbox/jellyfin-desktop` (native build, hardware decode first) | `media.yml`. Rebuilt only when `media/` or the Ubuntu FFmpeg version changes (cache key = recipe hash + `libavcodec` version), otherwise carried forward |

`couchbox` declares `Depends:` on everything it uses from Ubuntu:
- `plasma-bigscreen`, `kwin-wayland`, `sddm`, `network-manager`, `bluez`, `pipewire-pulse`;
- `python3-pyside6.qtquick`, `python3-pyside6.qtdbus`, `python3-mpv`, `python3-dbus-fast`, `python3-evdev`, `python3-websocket`;
- `uxplay`, `cec-utils`, `flatpak`, `qrencode`, `cryptsetup`, `clevis-luks`, `clevis-dracut`, `dracut`, `wpasupplicant`.

It `Recommends: couchbox-media, tailscale`. Tailscale comes from Tailscale's own apt repository, which the image and the installer add; it stays disabled until Settings turns it on.

### Where files go (no `/usr/local`, few conffiles)

| What | Path |
|---|---|
| Python package | `/usr/lib/python3/dist-packages/couchbox` |
| Commands | `/usr/bin/couchbox`, `/usr/bin/couchbox-app` (app launcher) |
| Services, apps, QML, tiles, schema, defaults | `/usr/share/couchbox/` |
| systemd units, presets | `/usr/lib/systemd/system/`, `/usr/lib/systemd/user/`, `/usr/lib/systemd/system-preset/` |
| udev, sysctl, logind, journald snippets | `/usr/lib/udev/rules.d/`, `/usr/lib/sysctl.d/`, `/usr/lib/systemd/{logind,journald}.conf.d/` |
| SDDM auto-login | `/usr/lib/sddm/sddm.conf.d/50-couchbox.conf` |
| KDE defaults for the TV user: no lock screen, no blanking, no KWallet | `/usr/share/couchbox/xdg/`, prepended to `XDG_CONFIG_DIRS` for the session via `/usr/lib/environment.d/`. **To verify (M2):** Plasma reads them, since the prototype wrote them into `~tv/.config` |
| Home-screen overlay | Built at run time into `/var/lib/couchbox/plasma/plasmoids/org.kde.bigscreen.homescreen` (stock Bigscreen copy + our files), prepended to `XDG_DATA_DIRS`. A dpkg trigger on `plasma-bigscreen` rebuilds it. A Bigscreen version we haven't tested falls back to the stock home screen with our app list |
| dracut module | `/usr/lib/dracut/modules.d/90couchbox/` |
| Chromium policy | the Flatpak policy extension path, written by postinst |

**Home row data:** the home QML reads `/run/couchbox/home.json`, which couchboxd writes from settings and the app manifests. The home QML watches the file, so reordering in Settings shows up at once, with no shell restart. The prototype instead regenerated a JS file and reloaded the shell.

### Maintainer scripts

| When | Steps |
|---|---|
| `postinst configure` | Create the `tv`, `couchbox` (group) and `couchbox-phone` users. Migrate `settings.json` to the current schema version (migrations in `couchbox.settings.migrations`). Write the env view. Reload udev and systemd. Rebuild the home overlay. Restart services whose files changed (never the TV session mid-playback; the updater handles timing) |
| `couchbox-apps.service` | Runs the first time the network is up, and after updates that add apps. Installs the Flatpaks (`rocks.shy.VacuumTube`, `org.chromium.Chromium`, `org.jellyfin.JellyfinDesktop` when the web client is chosen, `org.fcast.Receiver`) with progress events for the wizard. Not done in postinst, so installs stay fast and offline-safe |
| `prerm` / `postrm purge` | Stop services. On purge, remove `/etc/couchbox` and `/var/lib/couchbox`, but **never** touch LUKS keyslots or the disk |
| In the image build (chroot) | Detected with `systemd-detect-virt --chroot` or `COUCHBOX_IMAGE_BUILD=1`: no service starts, no user-session changes |

Lintian runs in CI, and overrides are allowed only with a comment.

## Image

`image/build-image.sh <version>` runs on an arm64 runner, natively, with no emulation:

1. **Base:** download `ubuntu-26.10-preinstalled-server-arm64+raspi.img.xz` from cdimage.ubuntu.com, pinned by SHA-256 in `image/base.lock`. A Renovate-style job proposes updates to the pin.
2. **Re-layout** into a fresh image file, about 8 GB, attached with `losetup -P`:
   - p1 is the FAT `system-boot` partition, copied from the base.
   - p2 becomes **LUKS2** (`aes-xts-plain64`, argon2id), opened with the image key file, holding ext4 `writable`. The base root files are copied in with `rsync -aHAX`.
   - If M6a's gate fails, p2 stays plain ext4 instead ([encryption.md](encryption.md#plan-b)).
3. **chroot** (systemd-nspawn, no boot):
   - Add the apt suites (`-updates`, `-backports`) and Tailscale's repo.
   - `apt-get install ./couchbox_*.deb ./couchbox-media_*.deb`.
   - Write `crypttab` and `fstab` and build the dracut initrd with the key-file unlock.
   - Set the kernel command line (`root=/dev/mapper/root rd.luks.*`), the CMA size for HEVC, and `cfg80211` regdom from settings at first boot.
   - Clean `/etc/machine-id`, SSH host keys and apt lists.
   - Leave cloud-init on for first boot only.
4. **Shrink:** `e2fsck`, `resize2fs -M`, shrink LUKS and the partition, truncate. Root grows back at first boot (cloud-init `growpart`, then `cryptsetup resize` and `resize2fs`).
5. **Compress and publish:**
   - Compress with `xz -T0 -9`. The target is under 1.5 GB, inside GitHub's 2 GB asset limit.
   - Write `.sha256` and the `rpi-imager.json` entry (name, description, icon, URL, `extract_size`, `extract_sha256`, `image_download_size`, `release_date`, `init_format: "cloudinit"`, `devices: ["pi5-64bit"]`).
6. **Smoke test** ([ci-and-testing.md](ci-and-testing.md#image-tests)).

The image is the base plus our packages, nothing hand-made. Anything the image does that the installer doesn't is a bug, and CI compares the two paths' `couchbox doctor` output.

## Installer

`install.sh`, attached to each release, is for an existing Ubuntu Server 26.10 Pi 5:
1. Check the system: Pi 5, arm64, Ubuntu 26.10, at least 8 GB free, not running a desktop already.
2. Download `release.json`, verify it with the embedded public key, then download and hash-check the debs.
3. Fix the apt suites (the prototype found `-updates` missing after a 26.04 → 26.10 upgrade), add Tailscale's repo, `apt-get install ./couchbox*.deb`.
4. Hand networking to NetworkManager, effective at reboot so SSH doesn't drop mid-install.
5. Print: "Reboot. The TV will show the Couchbox setup."

The disk is not converted to LUKS. Encryption on installer systems uses the plan-B path ([encryption.md](encryption.md#installer-systems)).
