# Couchbox

**An open-source TV box you own end to end.** Couchbox turns a Raspberry Pi 5 into a TV box you control with a remote. It replaces a Fire TV Stick or Roku. One HDMI cable to the TV carries the picture, the sound and HDMI-CEC, so the TV turns on and off with the box.

> **Status: planning.** This repo holds the plan and design ([docs/PLAN.md](docs/PLAN.md)). The code is being ported from a private prototype that runs on a real TV today. Nothing here is installable yet. The first preview release will be `v0.1.0`.

## What it does

- **Flash and go.** You write an image to an SSD or SD card, plug the box into the TV, and follow the on-screen setup with your TV's remote or a Fire TV remote. You don't need a keyboard, SSH or a config file.
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
- **Everything optional:** with no AI endpoint, no Jellyfin, no Tailscale and no encryption, it's still a complete TV box. Each of those turns on in Settings when you want it.
- **Updates:** signed releases from GitHub Releases. Updates install automatically when you're not watching, which is the default, or only when you choose (Manual). You can roll back to the previous version.

## Hardware

Couchbox targets the **Raspberry Pi 5 (8 GB recommended)** with an NVMe SSD on the M.2 HAT+ (or an SD card), the Active Cooler, the official 27 W power supply and a micro-HDMI to HDMI cable. The full reference list is in [docs/design/first-boot.md](docs/design/first-boot.md#reference-hardware).

## Docs

| Doc | What |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The plan: goals, decisions, milestones with done-when criteria, risks |
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
