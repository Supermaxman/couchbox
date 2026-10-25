# Couchbox

**An open-source TV box you own end to end.** Couchbox turns a Raspberry Pi 5 into a TV box you control with a remote. It replaces a Fire TV Stick or Roku. One HDMI cable to the TV carries the picture, the sound and HDMI-CEC, so the TV turns on and off with the box.

> **Status: preview.** The code is ported from a prototype that runs a real TV every day, and CI builds and tests it, including a bootable image. Fresh-hardware validation (milestone M8) comes before 1.0. See [docs/PLAN.md](docs/PLAN.md).

## Install

**→ [The install guide](docs/install.md)**. It takes about 20 minutes, with no keyboard or monitor:
1. Write Couchbox onto a USB stick with Raspberry Pi Imager.
2. Plug the stick into the Pi and the Pi into the TV.
3. Follow the setup on the TV, using the TV's remote, a Fire TV remote or your phone (scan the QR code). The setup copies Couchbox onto the SSD for you.

## What it does

- **Flash and go.** You write the image to a USB stick, plug the box into the TV, and follow the on-screen setup with your TV's remote, a Fire TV remote or your phone. The setup installs Couchbox onto the SSD. You don't need a keyboard, a monitor, SSH or a config file.
- **TV interface:** KDE Plasma Bigscreen on Ubuntu, with a home row you can reorder and hide apps in. It shows a clock and the weather.
- **Apps:**
  - YouTube (VacuumTube, ad-free, with SponsorBlock);
  - Jellyfin (hardware HEVC decoding on the Pi 5);
  - native TV apps for Seerr, Twitch (chat overlay, emotes), Nebula, Dropout and 2nd Try;
  - any website as a remote-friendly web app;
  - AirPlay and FCast receivers.
- **Remotes:**
  - The Fire TV remote pairs over Bluetooth. Its mic and its TV power and volume keys work.
  - The TV's own remote works over CEC.
  - A phone page lets you type and dictate.
- **Settings on the TV for everything:**
  - Wi-Fi, time zone and location, and the home screen layout;
  - media servers (Jellyfin, Seerr);
  - voice (any OpenAI-compatible speech-to-text and model endpoint);
  - Tailscale, SSH, disk encryption (with Tang network unlock, over Wi-Fi too);
  - updates.
- **Customizable home row:** reorder, hide, rename apps, add websites as apps (Settings → Home screen, or hold OK on a tile).
- **Everything optional:** with no AI endpoint, no Jellyfin, no Tailscale and no encryption, it's still a complete TV box. Each of those turns on in Settings when you want it.
- **Updates:** signed releases from GitHub Releases. Updates install automatically when you're not watching, which is the default, or only when you choose (Manual). You can roll back to the previous version.

## Hardware

Couchbox targets the **Raspberry Pi 5 (8 GB recommended)** with an NVMe SSD on the M.2 HAT+ (or an SD card), the Active Cooler, the official 27 W power supply and a micro-HDMI to HDMI cable. The full reference list is in [docs/design/first-boot.md](docs/design/first-boot.md#reference-hardware).

## Docs

| Doc | What |
|---|---|
| [docs/install.md](docs/install.md) | **Install**: USB stick → TV → phone or remote, step by step, with troubleshooting |
| [docs/hardware-test.md](docs/hardware-test.md) | The checklist for testing a release on fresh hardware |
| [docs/PLAN.md](docs/PLAN.md) | The plan: goals, decisions, milestones with done-when criteria, risks, progress |
| [docs/design/architecture.md](docs/design/architecture.md) | Components, processes, privilege and security model, file layout |
| [docs/design/settings.md](docs/design/settings.md) | Every setting, the Settings app, and home screen customization |
| [docs/design/first-boot.md](docs/design/first-boot.md) | From a fresh Pi to a working TV: image, preseed, setup wizard, remote pairing |
| [docs/design/image-and-packaging.md](docs/design/image-and-packaging.md) | Debian packages, the flashable image, the installer for existing Ubuntu |
| [docs/design/updates-and-releases.md](docs/design/updates-and-releases.md) | Versioning, releases, signing, the on-device updater, rollback |
| [docs/design/encryption.md](docs/design/encryption.md) | Optional disk encryption, Tang network unlock, Wi-Fi at boot |
| [docs/design/ci-and-testing.md](docs/design/ci-and-testing.md) | CI/CD pipelines and the test plan, from unit tests to hardware |
| [docs/design/porting.md](docs/design/porting.md) | What moves over from the prototype, what changes, what's dropped; licensing |

## Unofficial clients

Couchbox includes **unofficial** TV clients for services that have no Linux TV app:
- Twitch;
- Nebula;
- Dropout and 2nd Try (Vimeo OTT).

These clients are not affiliated with or endorsed by those services, and they use your own account. Service names and logos belong to their owners and are used only to identify the services.

## License

Apache License 2.0 (see [LICENSE](LICENSE)). The files that change KDE Plasma Bigscreen's home screen keep their upstream GPL-2.0-or-later or LGPL-2.0-or-later license. [NOTICE](NOTICE) lists these and other third-party parts.
