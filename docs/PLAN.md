# Couchbox plan

**Status:** M0–M5 and M7 implemented in this repo (see §9); M6 (encryption on hardware) and M8 (fresh-hardware validation) wait for the second set of hardware. Last updated 2026-10-25.

Couchbox is the public, configurable version of a private prototype. That prototype is a Raspberry Pi 5 TV box running Ubuntu 26.10 and KDE Plasma Bigscreen, and it has run a real TV every day since October 2026. It works well, but only for one household: hostnames, servers, keys and the household's own preferences are written into the scripts, and installing it means following nine manual phases over SSH.

This plan turns it into a project that someone else can flash onto a new Pi 5 and set up from the couch. It has to work without any of the prototype's servers.

## 1. Goals

| # | Goal | How we'll know |
|---|---|---|
| G1 | **Works out of the box** on the reference hardware: flash, plug in, set up with a remote | The fresh-hardware test (§6, M8) passes without SSH, a keyboard or a config file |
| G2 | **Everything is set in the UI.** Every prototype setting is in Settings on the TV | No setting needs a file edit; [settings.md](design/settings.md) lists each one with its page |
| G3 | **Nothing external is required.** No AI endpoint, speech-to-text, Jellyfin, Seerr, Tailscale or Tang | CI boots the image with no network services configured, and every feature that isn't set up says so or hides itself |
| G4 | **Optional extras:** Tailscale, disk encryption with Tang (over Wi-Fi too), OpenAI-compatible voice endpoints, media servers | Each turns on and off from Settings, and its tests cover both states |
| G5 | **Real releases:** SemVer, signed GitHub Releases, a changelog | `v0.1.0` and later are cut by CI from a tag, with signed assets and attestations |
| G6 | **Updates on devices:** Automatic by default, or Manual; channels; rollback | Updater tests (unit, container, hardware) cover check, download, install, health check and rollback |
| G7 | **Thorough CI:** lint, unit, UI screenshot, package, image boot and encryption tests on every change or nightly | Every pull request must pass the CI checks (§5) |
| G8 | **Customizable home screen:** reorder, hide, rename, add web apps | Settings → Home screen, and the Menu key on a home tile |

## 2. Non-goals (for 1.0)

- Netflix, Prime Video and Disney+. They need Widevine L1 / HDCP paths the Pi doesn't have.
- 4K output. The target is 1080p60.
- Hardware other than the Raspberry Pi 5. The code stays portable, but only the Pi 5 is tested and supported.
- Languages other than English. Text is kept in one place, so translation can come later.
- Our own remote hardware (the nRF52840 remote). It's on the roadmap, not in 1.0.
- An Ubuntu LTS base. Plasma Bigscreen is packaged only from Ubuntu 26.10 (§7, R1).

## 3. Decisions

These are made. Say so in review to change any of them.

| # | Decision | Why |
|---|---|---|
| D1 | **Name: Couchbox.** Repo `github.com/Supermaxman/couchbox`, public | "OpenTV" is Nagra/Kudelski's set-top-box brand, and they enforce it. No TV product uses "Couchbox" |
| D2 | **Apache-2.0**, with REUSE-style SPDX headers. Files changed from Plasma Bigscreen keep GPL-2.0-or-later / LGPL-2.0-or-later | Permissive. Upstream KDE files can't be relicensed. See [porting.md §Licensing](design/porting.md#licensing) |
| D3 | **Fresh repository** with clean history. The prototype repo stays private and is archived once the prototype box runs Couchbox | The prototype's history contains private hostnames, household notes and personal setup |
| D4 | **Base: Ubuntu 26.10 for Raspberry Pi (arm64)** with KDE Plasma Bigscreen on KWin Wayland | Same stack as the working prototype. Track 27.04, then 28.04 LTS (R1) |
| D5 | **Delivery: a flashable image** (primary), plus `install.sh` for an existing Ubuntu Server 26.10 Pi 5 | Image = out of the box. The installer suits people who already run Ubuntu |
| D6 | **Packaging: Debian packages** (`couchbox`, `couchbox-media`) attached to GitHub Releases. No apt repository in 1.0 | dpkg handles files, config files, dependencies and migrations. Updates arrive only through the Couchbox updater, so the Automatic/Manual setting is the single switch |
| D7 | **One privileged daemon (`couchboxd`)** behind a Unix socket. The TV-session apps never run as root | Settings, Wi-Fi, Tailscale, updates and encryption need root. A socket checks who's calling (`SO_PEERCRED`) and isn't reachable from web pages, unlike a localhost HTTP port |
| D8 | **Settings in one validated JSON file** (`/etc/couchbox/settings.json`, changed keys only) over package defaults. Secrets kept separately (`/var/lib/couchbox/secrets/`, root-only, never shown back) | One schema drives validation, the Settings app and the tests. Defaults can improve in updates |
| D9 | **Releases are signed with an SSH ed25519 key** (`ssh-keygen -Y sign`) over a release manifest that lists every asset's SHA-256, plus GitHub build-provenance attestations | Devices verify with OpenSSH they already have. Attestations let anyone check the build came from CI |
| D10 | **Versioning: SemVer**, tags `vX.Y.Z`. Prereleases `vX.Y.Z-beta.N` form the **beta** channel. Conventional Commits; release-please writes the changelog and release PRs | Standard, automatic changelogs |
| D11 | **Updates: Automatic (default) or Manual.** Automatic installs when no one is watching. Manual shows "Update available" and installs on request | As asked. "Not while watching" is the rule that keeps automatic updates from being annoying |
| D12 | **Encryption: the image's root partition is LUKS2 from the start**, unlocked by a key file in the initrd ("not protected" mode). "Encrypt" in Settings re-encrypts online with a new key, adds your passphrase and optional Tang servers, and removes the key file. No USB stick and no reboot to encrypt | The prototype's in-place encryption needed a USB boot and a keyboard at the console. Online re-encryption of LUKS2 needs neither. **Must be proven on hardware first** (M6a, R2) |
| D13 | **CI runs on GitHub's free arm64 runners** (`ubuntu-24.04-arm`, free for public repos), running Ubuntu 26.10 containers. The runner label is one repository variable | Native arm64 matches the Pi, so image builds need no emulation. Blacksmith needs a GitHub organization; moving there later only changes the variable |
| D14 | **Unofficial clients ship, Twitch ad filter off by default** ("Skip Twitch ads", experimental) | As decided in review. The README says the clients are unofficial and unaffiliated |
| D15 | **Python 3 + PySide6/QML for apps and services, bash only for build glue.** Code goes into a `couchbox` Python package with tests, not loose scripts | The prototype's stack, now importable and testable |
| D16 | **Default device name `couchbox`.** The first-boot wizard offers to change it; mDNS name `couchbox.local` | A predictable address for the phone page and SSH |

## 4. Milestones

Each milestone ends with a tagged prerelease once releases exist (from M5). The order puts the encryption prototype before the image build, because D12 decides the image's partition layout.

| M | Name | Work | Done when |
|---|---|---|---|
| **M0** | Plan | This repo, license, plan and design docs | Reviewed and agreed |
| **M1** | Foundations | Repo layout ([architecture.md §Layout](design/architecture.md#repository-layout)); the `couchbox` Python package; settings schema and store; `couchboxd` with its socket API; `couchbox` CLI; Debian packaging; CI for lint, unit tests, deb build and container install | `couchbox config get/set` works in an Ubuntu 26.10 container. CI passes. The `.deb` installs, upgrades and purges cleanly |
| **M2** | Port the TV | Input mapper, CEC/TV control, home screen (from settings, no fixed list), theme, the native apps, voice (optional modes), phone page (with pairing), memory/cache services, all with personal details removed and settings wired in ([porting.md](design/porting.md)) | `install.sh` on the **prototype box** (or a spare SD card in it) gives today's experience from Couchbox code, with no prototype-specific values left (CI greps for them) |
| **M3** | Settings app | Every page in [settings.md](design/settings.md); home screen customization; Menu key on tiles; on-screen keyboard and phone typing in every field | Every setting changes from the remote. Screenshot tests cover every page |
| **M4** | Image and first boot | Image builder; preseed file; Raspberry Pi Imager repository JSON; first-boot setup wizard; automatic remote pairing in the wizard; Flatpak apps downloading in the background | CI builds the image and boots it in a container (and QEMU for the initrd). On hardware, the wizard reaches the home screen with only the TV remote (CEC) or a Fire TV remote |
| **M5** | Releases and updates | release-please; release workflow (debs, image, manifest, signature, attestations, Imager JSON); `couchbox-updater`; Updates page; rollback | `v0.1.0` published by CI. A device on 0.1.0 updates itself to 0.1.1 automatically while idle, and rolls back when a broken test release fails its health check |
| **M6a** | Encryption prototype | Online LUKS2 re-encryption on the Pi 5 (time, CPU, power-loss resume); key-file initrd; Tang and Wi-Fi in the initrd built from settings | Measured on hardware and written up in [encryption.md](design/encryption.md). **Gate for M4's partition layout:** if it fails, the image ships plain ext4 and encryption keeps an "encrypt at next boot" path (written up there as plan B) |
| **M6b** | Encryption in Settings | Encrypt, add or remove passphrase and Tang, unlock over Wi-Fi, status; recovery documentation | Encrypting a running box from the remote works. Unplugging power mid-way resumes. Tang unlock works over Wi-Fi |
| **M7** | Media builds in CI | Raspberry Pi FFmpeg fork and native Jellyfin Desktop built on arm64 runners into `couchbox-media`, with the source tarballs | Jellyfin plays HEVC with hardware decoding from the CI-built package |
| **M8** | Fresh-hardware validation → **1.0.0** | A second, identical set of hardware, flashed from the release image and set up as a new user would. Run the hardware checklist ([ci-and-testing.md §Hardware](design/ci-and-testing.md#hardware-checklist)). Fix, repeat | The checklist passes with no workarounds. Tag `v1.0.0` |
| **M9** | Move the prototype box over | Flash (or install) Couchbox on the prototype box; import its settings with `couchbox import-mtv`; archive the private repo | The household box runs a stock Couchbox release with its settings in Settings |

M2 and M3 can overlap. M6a can start any time after M1.

## 5. Quality bar (every pull request)

- **Lint:**
  - shellcheck and shfmt;
  - ruff (lint and format);
  - qmllint on every QML file (Qt 6 from Ubuntu 26.10);
  - JSON Schema checks for the settings defaults, app manifests and release manifest;
  - REUSE lint for licenses;
  - gitleaks for secrets;
  - a **"no private values" grep** that fails on prototype hostnames, tailnet names or personal accounts.
- **Unit tests** (pytest): settings, daemon API, updater, input mapping, CEC, home layout, phone pairing, voice routing, service parsers, Twitch ad filter. Every external API is a recorded fixture; CI makes no calls to live services.
- **UI tests:** every QML page and app renders off-screen against stub backends and fixture data, with no QML warnings. The screenshots are compared with reviewed baselines and uploaded to the pull request.
- **Package tests:** build the debs, run lintian, install into a clean Ubuntu 26.10 arm64 container, upgrade from the last release's debs, then purge.
- **Nightly:** build the image; boot it in systemd-nspawn (services, first boot, updater against a fake release server); boot the initrd in QEMU (key-file unlock, Tang unlock with a Tang container, online re-encryption on a loop device); a KWin virtual-session smoke test.

Details: [ci-and-testing.md](design/ci-and-testing.md).

## 6. Fresh-hardware acceptance test (M8)

The person running it gets only the README:
1. Flash the image with Raspberry Pi Imager onto the NVMe drive (USB adapter) or an SD card.
2. Optionally set Wi-Fi and a user in Imager's customisation.
3. Plug in and power on. The TV wakes up and switches to the box over CEC.
4. Go through the wizard with the **TV remote only**:
   - pair the Fire TV remote;
   - set up Wi-Fi;
   - choose the time zone;
   - name the box;
   - choose updates (leave them on Automatic).
5. Watch YouTube at 1080p60, Twitch with chat, and an AirPlay mirror.
6. In Settings, turn on and test each of: Tailscale (QR sign-in), Jellyfin (found on the LAN), Seerr, voice endpoints, encryption with Tang over Wi-Fi.
7. Publish a test release `vX.Y.Z+1`. The box updates itself overnight, with the TV in standby, and shows what's new.
8. Publish a deliberately broken test release. The box rolls back by itself and reports it in Settings → Updates.

## 7. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | **Ubuntu 26.10 support ends in July 2027.** Bigscreen isn't in an LTS until 28.04 | Releases record their base OS. Move to 27.04 and then 28.04 with "base upgrade" releases: tested in CI, installed from Settings with a settings backup first, never automatic. Re-flashing plus settings restore is always a fallback |
| R2 | Online LUKS2 re-encryption on the Pi 5 is slow, or misbehaves under load or power loss | M6a measures it before the image layout is fixed. Plan B is in [encryption.md](design/encryption.md#plan-b) |
| R3 | Unofficial clients break when services change their APIs | Recorded-fixture tests catch our own regressions. A nightly "live canary" job (optional, using test accounts kept in secrets, never on pull requests) catches API changes. Each client can be turned off |
| R4 | Unofficial clients get a takedown | The clients are separate modules, so removing one doesn't touch the rest. No DRM is circumvented; content is the user's own account |
| R5 | GitHub release assets are capped at 2 GB | Flatpak apps install on first boot instead of being baked in. The image (about 1–1.5 GB compressed) stays under the cap |
| R6 | A bad automatic update breaks a family's TV | The box runs a health check after every update and rolls back on failure. Updates never install mid-playback. Beta comes before stable. The previous package is always kept |
| R7 | Fire TV remote models differ (IR tables, mic) | We support the tested model and add others when people report them. The hardware checklist records the model and firmware |
| R8 | Secrets leaking into a public repo | gitleaks plus the private-values grep in CI. Secrets live only on devices, root-only |
| R9 | The phone page lets anyone on the LAN type into the TV | It needs a pairing token from the TV's QR code ([architecture.md §Security](design/architecture.md#security-model)) |
| R10 | GPL obligations for the FFmpeg and Jellyfin builds | Each release attaches the exact source, and NOTICE lists it |

## 8. Open questions (answer whenever; none block M1)

1. Should the box get a `couchbox.dev`-style domain and docs site (GitHub Pages)? For now, the docs live in the repo.
2. Is the Fire TV remote the only remote for 1.0, or should another cheap BLE remote with a mic be supported too?
3. Should the image include an admin user? The plan is no: SSH is off until you turn it on in Settings or set a user in Imager.

## 9. Progress (2026-10-25)

| M | State | Notes |
|---|---|---|
| M0 | Done | This plan |
| M1 | Done | `couchbox` package, settings schema/store, `couchboxd`, CLI, `.deb`, CI (lint, 90 unit tests, package install into clean Ubuntu 26.10) |
| M2 | Done (code), on hardware at M8 | Prototype apps and services ported: personal values removed, wired to settings. Voice has off / dictation / assistant modes. The phone page needs pairing |
| M3 | Done | Settings app (11 sections) and the home row (live order, hold OK on a tile: move, hide). Screenshots of every page in CI |
| M4 | Done (image built in CI), on hardware at M8 | `image/build-image.sh`, the nspawn boot test, the preseed, the Imager repository entry, the setup wizard |
| M5 | Done (first release needs the signing key secret) | release-please, signed `release.json`, attestations, the updater with idle rules and rollback, beta channel |
| M6a | Partly | Online re-encryption is proven on loop devices in CI (`ci/encryption-loop.sh`). The Pi 5 measurement and the LUKS image layout (`build-image.sh --luks`) wait for hardware. The image ships plain ext4 until then |
| M6b | Code done, hardware test pending | Settings → Security flow; `couchbox.encryption` |
| M7 | Done | `media.yml` builds `couchbox-media` natively on arm64 |
| M8 | Waiting for hardware | |
| M9 | `couchbox import-mtv` ready | |

**Changes from the design while building:**
- `debian/` sits at the repository root, and QML apps are under `ui/`.
- Tiles open their options when you **hold OK**, as on Android TV, because Bigscreen keeps Menu for the task switcher. Menu also works where it reaches the home screen.
- The phone page runs as root, like the prototype, because it injects key presses through uinput.
- The Seerr app talks to Seerr through couchbox-voice's proxy with an API key. Seerr's own sign-in is a follow-up.
