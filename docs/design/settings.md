# Settings

Every setting lives in one schema (`schema.json`). This doc is the spec for it. Each row gives the key, its default, and the Settings page it appears on. Secrets are marked 🔒: they're stored root-only and can be written but never read back. The last column says what in the prototype the setting replaces.

**Rule:** no setting may require editing a file. If a setting can't be shown in the UI yet, it isn't in the schema yet.

## Settings app

`couchbox-settings` is a QML app in the same style as the native apps. It's built for the remote, with big type and the same `CouchKit` controls.

- **Opening it:** from the ⚙ tile at the end of the home row (it can't be hidden), or by voice ("open settings").
- **Layout:** the sections are on the left and the selected section's page is on the right. Back goes up a level.
- **Text fields:** every one opens the on-screen keyboard. The keyboard shows the phone-typing QR code and accepts dictation from the mic button.
- **Changes:** they apply right away, with no Save button. Changes that need a restart say so ("Restarts the home screen"), and changes that could cut off the remote or network ask for confirmation first, with a 15-second automatic revert (display mode, Wi-Fi).
- **Status chips:** each section shows its state, such as "Connected", "Off", "Not set up" or "Update available".
- **Disabled states:** any feature that needs something not set up shows why, with a button that leads to where you set it up.

## Sections and settings

### 1. Network
| Key | Default | Notes | Prototype |
|---|---|---|---|
| — (NetworkManager) | — | Wi-Fi list (signal, lock), join (keyboard), forget, hidden network. Ethernet status. IP address, MAC address | KDE network settings / `nmcli` |
| `network.hostname` | `couchbox` | Also used for the mDNS name, the Tailscale name, the CEC on-screen name (14 characters max, trimmed) and the AirPlay name, each unless set separately | `MTV_HOSTNAME` |
| `network.wifi_country` | from the time zone | Regulatory domain (5 GHz channels) | `cfg80211.ieee80211_regdom=US` |
| — | — | "Unlock disk over Wi-Fi" shortcut, shown when encryption with Tang is on (→ §9) | `6-bind-tang.sh` prompt |

### 2. Home screen
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `home.layout` | from app manifests (`default_order`) | Ordered list of app ids on the home row | `home.tsv` |
| `home.hidden` | `[]` | Apps hidden from the home row. They're still in "All apps" | — |
| `home.names` | `{}` | Renamed tiles | `home.tsv` column 2 |
| `home.web_apps` | `[]` | User websites: name, URL, optional icon. They open as remote-friendly Chromium app windows | `apps.tsv` |
| `home.clock` | `12h` (US) / `24h` | 12-hour or 24-hour | 12h hard-coded |
| `home.weather` | `on` when a location is set | Weather in the top bar | `MTV_WEATHER` |
| `appearance.theme` | `graphite` | graphite, neon, amber, sakura, matrix | `mtv-theme` |
| `appearance.scale` | `1.5` | UI size (1.0–2.0). Applies with confirmation | `MTV_SCALE` |

**Customizing the home row:**
- **In Settings → Home screen:** a list of every app with a toggle (shown or hidden) and the order.
  - Press OK on an app to pick it up; it lifts and shows ◀ ▶.
  - Left and Right move it, and OK drops it. Back cancels.
  - "Add a website" asks for a name and URL; the icon defaults to the site's favicon.
  - "Reset to default" restores the order and shows everything.
- **On the home screen:** **hold OK** (or press Menu, where it reaches the home screen) on a tile for options: *Move*, *Hide*, *More in Settings*.
  - *Move* works the same as in Settings, right there on the row.
  - An "All apps" tile at the end of the row opens the grid of every app, hidden ones included.

### 3. Apps and media servers
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `media.jellyfin.url` | unset | "Find on my network" uses Jellyfin's discovery (UDP 7359 broadcast), or type the URL. Tile hidden until set | `apps.tsv` |
| `media.jellyfin.client` | `native` | `native` (hardware HEVC, couchbox-media) or `web` | `9-jellyfin-hevc.sh` |
| `media.seerr.url` | unset | Seerr app sign-in uses Seerr's own login. Tile hidden until set | `MTV_SEERR_URL` |
| `media.seerr.api_key` 🔒 | unset | Optional, only for voice requests | `secrets/seerr-key` |
| `apps.youtube.captions` | `en` | Captions language turned on for each video; empty = off | `MTV_YT_CAPTIONS` |
| `apps.player.captions` | `on` | Native apps: subtitles on by default | per-app setting |
| `apps.twitch.chat` | `overlay` | overlay, side, off | per-app setting |
| `apps.twitch.skip_ads` | `off` | **Experimental.** Drops ad segments from live streams. Unofficial | always on |
| `apps.<id>.enabled` | `true` | Turns each unofficial client off entirely | — |
| `apps.airplay.enabled` | `true` | AirPlay receiver (UxPlay) | always on |
| `apps.airplay.name` | hostname | | `MTV_AIRPLAY_NAME` |
| `apps.airplay.pin` | unset | 4 digits, or off | `MTV_AIRPLAY_PIN` |
| `apps.fcast.enabled` | `true` | FCast receiver | always on |
| `apps.idle_minutes` | `60` | Close apps after this long unused (not while playing) | `MTV_APP_IDLE_MINUTES` |
| `apps.web_cache_mb` | `256` | Chromium cache cap | `MTV_WEB_CACHE_BYTES` |

Each app's sign-in (Twitch device code, Nebula email and password, VHX email and password, profile choice) stays inside the app. Settings → Apps → *app* → "Sign out" clears it.

### 4. Voice and assistant
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `voice.mode` | `off` | `off`: the mic button shows "Set up voice in Settings". `dictation`: speech-to-text into text fields and search, plus simple commands (pause, play, back, home, open *app*, volume) parsed without a model. `assistant`: the full agent with tools | always assistant |
| `voice.stt.url` | unset | OpenAI-compatible `/v1/audio/transcriptions`. "Test" records 3 s and shows the text | `MTV_STT_URL` |
| `voice.stt.model` | `whisper-1` | | `MTV_STT_MODEL` |
| `voice.stt.api_key` 🔒 | unset | | — |
| `voice.llm.url` | unset | OpenAI-compatible `/v1/chat/completions` with tool calling. "Test" sends a ping prompt | `MTV_LLM_URL` |
| `voice.llm.model` | unset | Model list from `/v1/models` when the server offers it | `MTV_LLM_MODEL` |
| `voice.llm.api_key` 🔒 | unset | | `secrets/llm-key` |
| `voice.notes` | empty | "Household notes" added to the assistant's instructions: nicknames, preferences | `voice-notes.md` |
| `voice.language` | `en` | Speech-to-text language hint | — |

On-device speech-to-text (whisper.cpp on the Pi) is a post-1.0 option (`voice.stt.local`). It is planned so that dictation works with no server at all.

### 5. Remote and TV
| Key | Default | Notes | Prototype |
|---|---|---|---|
| — | — | **Pair a remote**: guided, with pictures ("Hold Home for 10 seconds"); paired list (battery level when reported), forget, rename | `mtv-pair-remote` |
| — | — | **TV buttons on the Fire remote (IR)**: choose the TV brand, test Power and Volume, store | `mtv-remote-ir program` |
| `tv.cec.enabled` | `true` | HDMI-CEC control | — |
| `tv.cec.device` | `auto` | Picks the port with a TV attached | `MTV_CEC_DEV` |
| `tv.cec.name` | hostname (14 characters) | Name in the TV's source list | `MTV_OSD_NAME` |
| `tv.power_on_with_box` | `true` | Wake the TV and switch to the box on boot and on any key | always |
| `tv.standby_with_box` | `true` | The remote's Power puts the TV in standby (CEC) | always |
| `tv.volume` | `tv` | `tv`: volume keys control the TV (CEC/IR). `box`: the box's own volume | `MTV_VOLUME` |
| `tv.inputs` | detected over CEC | Inputs cycled by the remote's input button | `MTV_TV_INPUTS` |
| `input.keymap` | `default` | Key mapping preset; per-app overrides are in the package | `input.toml` |

### 6. Display and sound
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `display.mode` | `1920x1080@60` | Picked from the TV's EDID modes. Confirm-or-revert (15 s) | `MTV_MODE` |
| `display.outputs` | `auto` | Whichever HDMI port has a screen | `MTV_OUTPUTS` |
| `audio.output` | `auto` | HDMI port | `mtv-audio` |

### 7. Date, time and location
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `time.timezone` | from the wizard | Searchable list. "Detect" asks a geolocation-by-IP service once, and only when pressed | `MTV_TIMEZONE` |
| `location.name`, `location.lat`, `location.lon` | unset | City search (Open-Meteo geocoding, no API key). Used for the weather | `MTV_WEATHER` |
| `location.units` | `imperial` in US/LR/MM, else `metric` | °F or °C | °F hard-coded |

### 8. Remote access
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `tailscale.enabled` | `false` | On: starts tailscaled. **Sign in** shows the login URL as a QR code to scan with your phone. Alternatively paste an auth key 🔒 (phone page) | `bootstrap.sh` |
| `tailscale.tags` | empty | Optional `--advertise-tags`, e.g. `tag:tv` (key expiry off for tagged nodes) | `MTV_TS_TAGS` |
| `tailscale.serve_phone_page` | `true` | Phone page at `https://<name>.<tailnet>.ts.net` with a real certificate | `tailscale serve` |
| `ssh.enabled` | `false` | Keys only | always on |
| `ssh.github_user` | unset | Import keys from `github.com/<user>.keys`; also "Paste a key" from the phone page | `MTV_GITHUB_KEYS` |
| `phone.enabled` | `true` | Phone typing/remote page | always on |
| — | — | "Show pairing code", "New pairing code" (signs out paired phones) | — |

### 9. Security and privacy
| Key | Default | Notes | Prototype |
|---|---|---|---|
| — | — | **Disk encryption** status: "Not protected" / "Encrypting… 43 %" / "Encrypted: passphrase + 1 network key" | phases 5a–6 |
| — | — | **Encrypt this box**: passphrase (typed twice; shown as dots, with a "show" toggle), optional network unlock (Tang URLs, thumbprint shown to confirm), optional "use Wi-Fi at boot". [encryption.md](encryption.md) | |
| — | — | Change passphrase · Add/remove network unlock · Wi-Fi at boot on/off · "Print recovery info" (QR to save the passphrase hint and LUKS details on your phone; never the passphrase itself) | |
| `privacy.weather` | `on` | Off: no calls to Open-Meteo | — |

### 10. Updates
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `updates.mode` | `automatic` | `automatic`: download and install when idle. `manual`: check and notify; install from here | `mtv-update` by hand |
| `updates.channel` | `stable` | `stable`, `beta` | — |
| `updates.window` | `02:00-06:00` | Preferred install hours (automatic mode) | — |
| `updates.os` | `security` | Ubuntu updates: `security` (unattended-upgrades, default), `all`, `off`. Flatpak apps update weekly | `20auto-upgrades`, flatpak timer |
| `updates.source` | `Supermaxman/couchbox` | For forks; needs a matching signing key | — |
| — | — | Version, "Check now", "Install now", what's new (release notes), history, **Roll back to x.y.z** | |

### 11. System
| Key | Default | Notes | Prototype |
|---|---|---|---|
| `system.swap_gb` | `8` (NVMe) / `2` (SD) | Swap file size | `MTV_SWAP_GB` |
| `system.logs_mb` | `200` | journald cap | journald.conf |
| — | — | About (version, base OS, hardware, temperature, throttling), storage, memory | `mtv-check` |
| — | — | Run checks (the `couchbox doctor` results on screen), Restart home screen, Reboot | `mtv-check` |
| — | — | Export/import settings (to/from the phone page; secrets excluded unless chosen) | — |
| — | — | Factory reset: keep Wi-Fi? (yes/no). Wipes settings, secrets, app logins; keeps encryption keys only if you choose | — |
| — | — | Open-source licenses | — |

## Settings that stay internal

These are not user settings. They're fixed in the package and documented in code:
- the TV user's name (`tv`);
- the admin user (Imager creates it, or there is none);
- DevTools ports;
- service ports.
