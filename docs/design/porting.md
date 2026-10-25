# Porting from the prototype

The prototype is a private repository with about 17,000 lines across 183 files. Every file is listed below with where it goes and what has to change. Three changes apply everywhere:

- **Rename:**
  - `mtv-*` becomes `couchbox-*`;
  - `/etc/mtv` and `/usr/local/lib/mtv-*` become the paths in [image-and-packaging.md](image-and-packaging.md);
  - `MTV_*` settings become schema keys ([settings.md](settings.md)).
- **Personal values come out:**
  - Every prototype-specific host, tailnet name, LAN address, account and household note is removed, with no replacement default.
  - The feature reads its setting, or stays off until it's set.
  - CI's private-values guard enforces this ([ci-and-testing.md](ci-and-testing.md#private-values-guard-no-private-values)).
- **Tests come with the code:** each ported module arrives with its unit or screenshot tests in the same PR.

## File map

### Install and system phases
| Prototype | Couchbox | Change |
|---|---|---|
| `image/1-network.sh`, `2-upgrade.sh` | — | Dropped: the image starts on 26.10 with NetworkManager. The installer's apt-suite fix keeps the useful part |
| Phase 3 (Tang server setup, run on the home server) | `docs/tang-server.md` | Becomes a guide for running Tang on any LAN machine |
| Phases 4–6 (USB stick writer, `5a-prepare-encrypt.sh`, `encrypt/5b-encrypt-from-usb.sh`, `6-bind-tang.sh`) | `src/couchbox/daemon/encryption.py` + `system/dracut/90couchbox/` | Replaced by online re-keying ([encryption.md](encryption.md)). The test-boot (`piboot-try`) and initrd content checks are kept |
| `encrypt/dracut/90mtv-wifi/*` | `system/dracut/90couchbox/` | Credentials come from the NetworkManager connection. Country from settings, not `US` |
| `7-tv-setup.sh`, `bootstrap.sh` | `packaging/debian/*` (postinst), `image/build-image.sh`, `installer/install.sh` | Split: the system state becomes package files, and the one-time steps go into the image or the installer. Hostname, time zone, Tailscale and SSH become couchboxd actions |
| `8-shell.sh` (personal shell setup), `shell/shell-env.sh`, `shell/tmux-save.service`, `local/` | — | Dropped (a personal dev environment) |
| `9-jellyfin-hevc.sh`, `hevc/*` | `media/` + `couchbox-media` package | Built natively on CI arm64 (no x86 cross-build). The CMA setting moves to the image's boot config |
| `sudo-nopasswd.sh`, `secrets/` | — | Dropped. Secrets go through couchboxd |
| `mtv.conf` | `src/couchbox/settings/schema.json` + `defaults.json` | Every key mapped in [settings.md](settings.md) |
| `input.toml` | `/usr/share/couchbox/input/default.toml` | `run:mtv-*` actions become couchbox actions. Volume mode from settings |
| `home.tsv`, `apps.tsv` | app manifests + `home.*` settings | Jellyfin and Seerr URLs become settings. The web versions of the native apps are optional manifests, hidden by default |
| `voice-notes.md` | `voice.notes` setting | **Contents not ported** (household notes). Ships empty |
| `udev/61-mtv-input.rules` | `system/udev/` | Rename |
| `systemd/*`, `user/*` | `system/systemd/` | Rename. `mtv-btlog` becomes an opt-in debug unit. `mtv-flatpak-update` goes into the updater's OS/app step |
| `chromium/policies.json`, `web-extension/*` | `system/chromium/`, `system/web-extension/` | As is |

### Commands (`image/bin`)
| Prototype | Couchbox | Change |
|---|---|---|
| `mtv-input` | `couchbox.input` (+ unit) | Keymap path; actions by name; `/run/mtv-last-key` becomes `/run/couchbox/last-key` |
| `mtv-tv`, `mtv-remote-ir` | `couchbox.cec`, `couchbox.remote.ir` | IR tables by brand. **Only Samsung is verified.** Other brands use codes from an open IR database (license checked before import), marked "untested" in the UI until someone reports them working |
| `mtv-pair-remote` | `couchbox.remote.pair` (couchboxd) | Event stream for the wizard; no CLI-only flow |
| `mtv-voice`, `voice/*` | `couchbox.voice` | `off`/`dictation`/`assistant` modes. URLs, models and keys from settings. The Seerr tool needs `media.seerr.*`, and the Jellyfin tool needs `media.jellyfin.url`; a tool is disabled when its setting is unset. `prompt.md` is made generic |
| `mtv-type` | `couchbox.phone` | Pairing token. Host name from settings. Tailscale optional; falls back to `http://<name>.local:8791` |
| `mtv-memory`, `mtv-swap`, `mtv-clean-caches` | `couchbox.memory` | Settings keys; swap size by disk type |
| `mtv-home`, `mtv-theme`, `mtv-web-apps` | `couchbox.home` (couchboxd) | home.json instead of a regenerated JS file. Overlay path per the packaging doc |
| `mtv-display`, `mtv-audio` | `couchbox.display`, `couchbox.audio` | Settings keys |
| `mtv-youtube`, `mtv-jellyfin*`, `mtv-pause-all` | `couchbox.apps.launch`, `couchbox.media` | `mtv-jellyfin-debug` and `mtv-jellyfin-stats` become `couchbox doctor` subcommands |
| `mtv-check` | `couchbox doctor` | Machine-readable output (used by the health check and CI) |
| `mtv-update` | `couchbox-updater` | Replaced ([updates-and-releases.md](updates-and-releases.md)) |
| `mtv-seerr`, `seerr/*` | `apps/seerr/` | The server URL comes from settings: two avatar URLs are hard-coded in QML today |
| `mtv-dropout`, `mtv-2ndtry`, `mtv-nebula`, `mtv-twitch`, `dropout/*` | `apps/streaming/` + `src/couchbox/services/` | `browser_cookies()` import from Chromium becomes a fallback only. The ad filter defaults to `apps.twitch.skip_ads=off` |
| `tvkit/MtvKit` | `apps/CouchKit` | Rename |
| `theme/*` | `shell/` | Weather location and units from settings. Clock 12/24 h. Menu-key tile options are new |

### Docs
| Prototype | Couchbox |
|---|---|
| `DESIGN.md` | Folded into these design docs. The prototype's decisions and research findings that still matter are carried over |
| `SETUP.md` | `docs/install.md` (user guide: image, Imager, wizard) and `docs/troubleshooting.md` |
| `HARDWARE-POC.md`, `poc-results.md` | `first-boot.md#reference-hardware` and `tests/hardware/RESULTS.md` |
| `apps.md`, `voice.md`, `remote-ir.md` | `docs/apps.md`, `docs/voice.md`, `docs/remote-ir.md`, with the prototype's own servers removed |

### Not in either repo
`.firetv-re/` in the prototype's working directory holds Fire OS firmware dumps used to work out the remote's IR protocol. It was never committed. It **must never be published**: it's Amazon's copyrighted code. Only our own protocol notes (`remote-ir.md`) are ported.

## Licensing

| Part | License | Why |
|---|---|---|
| Everything we wrote | Apache-2.0 | Project license |
| `shell/home/HomeHeader.qml`, `HomeScreen.qml`, `indicators/AbstractIndicator.qml` | GPL-2.0-or-later (upstream headers kept, our changes noted) | Modified from Plasma Bigscreen |
| `shell/home/launcher/StartupFeedbackWindow.qml` | LGPL-2.0-or-later | Same |
| Our new home files (`Home.qml`, `AppTile.qml`, `Style.qml`, `Weather.qml`) | Apache-2.0 | New files. They're loaded by plasmashell as separate QML files, not linked into GPL code |
| Jellyfin logo SVG | as published by the Jellyfin project (its file header) | Nominative use |
| Other service logos (`theme/tiles/logos/*`) | **To check one by one before publishing.** Use the official press-kit files, or replace them with text tiles | Trademark and copyright of each service |

- `REUSE.toml` records all of this, and `reuse lint` enforces it.
- **Contributions:** they're accepted under Apache-2.0 (inbound = outbound) with a DCO sign-off (`Signed-off-by`), checked by CI.

## Moving the prototype box over (M9)

1. `couchbox import-mtv` reads `/etc/mtv/mtv.conf`, `/etc/mtv/secrets/*`, `home.tsv` and `apps.tsv`, and writes Couchbox settings and secrets. Its tests use a scrubbed sample.
2. Install with `install.sh`. The box is already LUKS2 + Tang, so it shows up as "Encrypted (set up before Couchbox)".
3. App logins stay where they are (`~tv`). The native apps' data directory moves from `~tv/.local/share/mtv` to `~tv/.local/share/couchbox` by a one-time migration.
4. Archive the private repo.
