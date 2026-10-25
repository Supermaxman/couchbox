# Architecture

## Overview

```
┌──────────────────────────────── TV ─────────────────────────────────┐
│  HDMI ◄── one cable: 1080p60 picture + sound + CEC     IR ◄── remote │
└──────────────────────────────────────────────────────────────────────┘
                ▲ micro-HDMI → HDMI (CEC: /dev/cec0)
┌───────────────┴──────────────── Couchbox (Raspberry Pi 5) ──────────────────────────┐
│ Ubuntu 26.10 arm64 · KWin Wayland · SDDM auto-login "tv" · Plasma Bigscreen         │
│                                                                                     │
│ TV session (user "tv", unprivileged)                                                │
│  ├─ Bigscreen shell + Couchbox home (shell/home: clock, weather, home row from      │
│  │                                   settings, Menu-key tile options)               │
│  ├─ couchbox-setup ...... first-boot wizard (QML), then never again                 │
│  ├─ couchbox-settings ... Settings app (QML)                                        │
│  ├─ native apps ......... Seerr, Twitch, Nebula, Dropout, 2nd Try (QML + libmpv)    │
│  ├─ Flatpak apps ........ YouTube (VacuumTube), Chromium web apps, Jellyfin, FCast  │
│  ├─ couchbox-airplay .... UxPlay                                                    │
│  └─ voice overlay ....... the pill at the bottom of the screen (layer-shell QML)    │
│                │  Unix socket /run/couchbox/couchboxd.sock (group couchbox)         │
│                ▼                                                                    │
│ System services (root unless noted)                                                 │
│  ├─ couchboxd ........... settings, secrets, Wi-Fi, Tailscale, SSH, time, encryption│
│  │                        remote pairing, update control: the only privileged API   │
│  ├─ couchbox-input ...... BT remotes + CEC keys → actions (evdev → uinput)          │
│  ├─ couchbox-cec ........ TV power, input and volume over CEC; IR tables on the remote │
│  ├─ couchbox-voice ...... remote mic → STT → dictation or assistant (optional)      │
│  ├─ couchbox-phone ...... phone typing/remote page, :8791 (user couchbox-phone)     │
│  ├─ couchbox-updater .... timer: check, download, verify, install when idle, roll back │
│  ├─ couchbox-memory ..... closes idle apps, swap file, cache caps                   │
│  └─ tailscaled (opt) .... only when turned on in Settings                           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Language | Runs as | Purpose | Prototype origin |
|---|---|---|---|---|
| `couchbox` Python package | Python 3 | — | Shared code: settings, IPC client, CEC, apps registry, logging | `voice/`, `dropout/`, bin scripts |
| `couchboxd` | Python | root | The privileged API (below) | new (some of `bootstrap.sh` and `mtv-update` at run time) |
| `couchbox` CLI | Python | any (privileged commands go through couchboxd) | `config`, `doctor`, `update`, `pair-remote`, `tv`, `logs`, `import-mtv` | `mtv-check`, `mtv-pair-remote`, `mtv-tv`, `mtv-update` |
| `couchbox-input` | Python | root | Grabs remotes, maps keys per focused app, emits uinput | `mtv-input` |
| `couchbox-cec` | Python | root | TV on/standby, active source, volume, input cycling; Fire remote IR programming | `mtv-tv`, `mtv-remote-ir` |
| `couchbox-voice` | Python | root (hidraw) | Mic capture, STT, dictation, assistant tools | `mtv-voice`, `voice/` |
| `couchbox-phone` | Python | own user | Phone typing and remote page, QR | `mtv-type` |
| `couchbox-updater` | Python | root | [updates-and-releases.md](updates-and-releases.md) | `mtv-update` (manual) |
| `couchbox-memory` | Python | root | Idle app shutdown, swap, caches | `mtv-memory`, `mtv-swap`, `mtv-clean-caches` |
| Home screen | QML (GPL files) | tv | Bigscreen home overrides, built from settings | `theme/home` |
| `couchbox-settings`, `couchbox-setup` | QML + PySide6 | tv | Settings app and first-boot wizard | new |
| Native apps | QML + PySide6 + libmpv | tv | Seerr, Twitch, Nebula, Dropout, 2nd Try | `mtv-seerr`, `mtv-dropout` + `dropout/` |
| `CouchKit` QML module | QML | tv | Shared TV controls: keyboard popup with QR, buttons, pages | `tvkit/MtvKit` |

### Voice assistant

The assistant mode of `couchbox-voice` sends the transcript to an OpenAI-compatible model with tools (`src/couchbox/voice/`).

- **Tools follow the home row.** Each app's tool is offered only while its tile is shown, so hiding Dropout removes the `dropout` tool. Jellyfin and Seerr also need their servers set. `open_app` lists only the visible apps.
- **The tools:**
  - `youtube`: VacuumTube over DevTools.
  - `jellyfin`: the web client's API over DevTools.
  - `seerr`: its API.
  - `dropout`, `second_try`, `nebula`, `twitch`: the native apps, through their control socket.
  - `page`: web apps.
  - `media`, `remote`, `tv` and `say`.
- **The native apps' control socket** (`couchbox.appctl`) is `$XDG_RUNTIME_DIR/couchbox/app-<site>.sock`, mode 0600. It runs inside `couchbox-streaming`:
  - Back-end calls run with the app's own sign-in: search, Continue Watching, a show's seasons and episodes.
  - The assistant can open things in the app, control its player, and read what the app shows.
  - Starting a second copy of the app hands its `--open` to the running one.
- **The app in front** comes from KWin (`couchbox-active-window`: a one-off KWin script reports `workspace.activeWindow` over D-Bus), so it works for every app, native or web. Each request carries one bracketed line after the user's words, e.g. `[Screen: Dropout in front: Game Changer S7E3 "…" playing at 1:15 of 40:00. Now: Sat Oct 25, 4:10 PM.]`. "Play the newest one" then means the app in front.
- **Prompt caching:**
  - The system prompt holds only stable text: the short rules (`prompt.md`), the household notes, and a summary after compaction.
  - The tool list stays fixed for a whole request.
  - The screen and the time go in the user message.
  - Measured on llama.cpp (Qwen3.8-27B): after the first request, about 1,740 of 1,780 prompt tokens come from cache.
  - The descriptions are short: each tool's own text says what its actions do, so the prompt doesn't repeat it.

## couchboxd API

- **Transport:** JSON-RPC 2.0 over `/run/couchbox/couchboxd.sock`.
  - The socket is mode 0660, group `couchbox`. The `tv` user is in that group.
  - Every call checks the caller with `SO_PEERCRED`.
  - Calls that change the system, such as Wi-Fi or encryption, are allowed only from members of `couchbox` or from root.
  - Read-only status calls are allowed for any local user.
- **No HTTP.** Web pages in Chromium can reach `localhost` ports, but they can't reach a Unix socket.

| Namespace | Methods (examples) |
|---|---|
| `settings` | `get(keys)`, `set(changes)` (validated against the schema, atomically written, change events), `schema()`, `reset(key)`, `export()`, `import(file)` |
| `secrets` | `set(name, value)`, `clear(name)`, `status()` → `{name: set/unset}`. **No read.** Services read secret files directly |
| `network` | `wifi.scan/connect/forget/list`, `status`, `hostname.set` (NetworkManager over D-Bus) |
| `time` | `timezone.set`, `zones()`, `ntp.status` |
| `tailscale` | `up(authkey?)` → login URL for the QR, `down`, `status`, `serve.phone(on)`, `logout` |
| `ssh` | `enable/disable`, `import_github(user)`, `keys.list/remove` |
| `remote` | `pair.start/stop` (events stream progress), `devices`, `forget`, `ir.program(brand)` |
| `display` | `modes()` (from EDID), `set(mode, scale)` |
| `updates` | `status`, `check`, `install(version)`, `rollback`, `history` |
| `encryption` | `status`, `encrypt(passphrase, tang[], wifi)`, `progress`, `passphrase.change`, `tang.add/remove`, `wifi_unlock.set` |
| `system` | `reboot`, `restart_ui`, `logs.bundle`, `factory_reset(keep_wifi)` |
| `events` | `subscribe(topics)`: settings changes, pairing, update and encryption progress |

Services that need settings read the files themselves and reload on `SIGHUP`. couchboxd sends that signal after a change. This keeps couchboxd off the critical path: if the daemon is down, the TV still works.

## Settings and state on disk

| Path | Owner / mode | What |
|---|---|---|
| `/usr/share/couchbox/defaults.json` | root 0644 (package) | Default values. Can change in updates |
| `/usr/share/couchbox/schema.json` | root 0644 (package) | JSON Schema: types, ranges, enums, which page shows the key, restart hints |
| `/etc/couchbox/settings.json` | root 0644 | **Only keys the user changed.** Written atomically (temp file + rename) and versioned (`"version": N`, with migrations in the package) |
| `/etc/couchbox/couchbox.env` | root 0644 | Generated `KEY=value` view for systemd `EnvironmentFile=` and shell |
| `/var/lib/couchbox/secrets/<name>` | root 0600, dir 0700 | API keys, Tailscale auth key, phone pairing secret. Never in settings.json |
| `/var/lib/couchbox/state/` | root | Updater state, remote pairing records, last-good version |
| `/var/lib/couchbox/updates/` | root | Downloaded and kept packages (current + previous) |
| `/boot/firmware/couchbox.toml` | FAT | Optional preseed, read once at first boot, secrets wiped ([first-boot.md](first-boot.md#preseed)) |
| `~tv/.local/share/couchbox/` | tv | App data: logins and caches for the native apps |

## Security model

- **Assets on the box:**
  - streaming-service sessions (cookies, tokens);
  - API keys;
  - the Tailscale node key;
  - Wi-Fi credentials;
  - SSH host keys.
- **Exposure:**
  - The box is on a home LAN.
  - The phone page is on `:8791`.
  - AirPlay and FCast are open on the LAN.
  - With Tailscale on, the box is also on the tailnet.

| Rule | Detail |
|---|---|
| Least privilege | Only couchboxd, the input mapper, CEC, the updater and voice (hidraw) run as root. Apps run as `tv`. The phone page runs as its own user and talks to couchboxd and the session over narrow calls |
| No secret leaves the box through the UI | Secrets are write-only through the API. Settings shows "set" or "not set" |
| Phone page pairing | The QR code on the TV holds `https://<name>/#t=<token>`. The token is random, stored root-only and can be rotated in Settings. Without the token the page shows "Scan the code on the TV". The token lives in the fragment, so it never reaches proxies or logs |
| Localhost services | Every HTTP endpoint the prototype had on localhost (voice, typing) either moves to the Unix socket or requires the token, plus an `Origin` check against browser cross-site requests |
| SSH | Off by default. When on: keys only (from a GitHub user or pasted), modern ciphers, no root login |
| AirPlay | Optional PIN in Settings |
| Updates | Signed manifest, pinned key, hashes checked before install ([updates-and-releases.md](updates-and-releases.md)) |
| Logs | Always on (journald, capped at 200 MB). Secrets are masked by the shared logging helper. `couchbox logs bundle` writes a redacted archive for bug reports |

## Repository layout

```
couchbox/
├─ README.md  LICENSE  NOTICE  CHANGELOG.md  SECURITY.md  CONTRIBUTING.md  REUSE.toml
├─ docs/                    user guides (install, settings, troubleshooting) + design/
├─ src/couchbox/            Python package
│  ├─ settings/  ipc/  daemon/  cli/  updater/  input/  cec/  voice/  phone/  memory/
│  └─ services/             unofficial clients: vhx.py, nebula.py, twitch.py (+ adfilter), seerr.py
├─ apps/                    QML apps (each: main.py + qml/)
│  ├─ settings/  setup/  seerr/  streaming/ (Dropout, 2nd Try, Nebula, Twitch)  voice-overlay/
│  └─ CouchKit/             shared QML module (keyboard + QR, buttons, pages)
├─ shell/                   Plasma Bigscreen home overrides + theme (GPL files live here)
├─ system/                  systemd units, udev rules, dracut module, sddm/kwin/logind snippets,
│                           Chromium policy and web extension, desktop files, polkit (if needed)
├─ packaging/debian/        couchbox (arch all) and couchbox-media (arm64)
├─ image/                   build-image.sh, rootfs overlay, rpi-imager.json template
├─ media/                   rpi-ffmpeg and jellyfin-desktop build recipes
├─ installer/install.sh     for an existing Ubuntu Server 26.10 Pi 5
├─ tests/                   unit/, qml/ (+ golden/), fixtures/, package/, image/, hardware/
└─ .github/                 workflows/, ISSUE_TEMPLATE/, dependabot.yml, release-please config
```

## Apps registry

Each app has a manifest in `/usr/share/couchbox/apps/<id>.json`. The home screen, Settings, the voice assistant and `couchbox-memory` all read it.

```json
{
  "id": "twitch",
  "name": "Twitch",
  "tile": "tiles/twitch.svg",
  "exec": "couchbox-app streaming --site twitch",
  "kind": "native",
  "requires": [],
  "settings_page": "apps/twitch",
  "default_visible": true,
  "default_order": 60,
  "unofficial": true
}
```

- **`requires`** lists settings that must be set before the tile shows, for example `["media.jellyfin.url"]` for Jellyfin. Tiles whose requirements aren't met are hidden. Settings shows "Set up Jellyfin to show it on the home screen."
- **User web apps** (Settings → Home screen → Add a website) become manifests in `/etc/couchbox/apps/`.
