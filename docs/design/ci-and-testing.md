# CI/CD and testing

## Runners

| Label | Used for | Notes |
|---|---|---|
| `${{ vars.ARM_RUNNER }}` (default `ubuntu-24.04-arm`) | Everything that builds or runs Couchbox | GitHub's arm64 Linux runners are free for public repos. Jobs run in an `ubuntu:26.10` (arm64) container, except image and loop-device jobs, which need the VM itself (`sudo losetup`, nspawn) |
| `ubuntu-latest` | Pure-text checks (PR title, links, REUSE, gitleaks) | Fast and cheap |
| `self-hosted, couchbox-hil` (optional, later) | The hardware checklist on a real Pi 5 + TV | **Never** runs on `pull_request` (a fork's code on our hardware). Only `workflow_dispatch` and release candidates, behind the `hil` environment's approval |

**Moving to Blacksmith:**
- Blacksmith needs a GitHub **organization**, so moving there means moving the repo into an org.
- Then the change is setting `ARM_RUNNER=blacksmith-4vcpu-ubuntu-2404-arm` and installing the Blacksmith app with "Allow public repositories". The workflows themselves don't change.

## Workflows

| File | Trigger | Jobs |
|---|---|---|
| `ci.yml` | pull_request, push to main | `lint` · `unit` · `qml` · `package` · `encryption-loop` · `no-private-values` |
| `pr-title.yml` | pull_request | Conventional Commit title check |
| `nightly.yml` | schedule 09:00 UTC, manual | `image` (build) → `image-boot` (nspawn) · `initrd` (QEMU: key file, Tang, passphrase) · `session` (KWin virtual + screenshots) · `upgrade-from-last-release` |
| `release-please.yml` | push to main | Keeps the release PR up to date; on merge, creates the tag and a draft release |
| `release.yml` | tag `v*` | build debs → build image → package and image tests → **sign** (environment `release`, maintainer approval) → attest → upload assets → publish (prerelease for `-beta`) |
| `media.yml` | changes to `media/`, manual, weekly check of Ubuntu's FFmpeg version | Build `couchbox-media` natively, cache by recipe hash + libavcodec version, upload as artifact for `release.yml` |
| `canary.yml` | daily, manual. Never on PRs | Live API checks of the unofficial clients with test accounts (secrets); opens an issue when a service changed |
| `codeql.yml` | weekly, PR | Python CodeQL |
| `dependabot.yml` | weekly | GitHub Actions versions, Python dev tools |

**Required checks on `main`:** `lint`, `unit`, `qml`, `package`, `encryption-loop`, `no-private-values`, `pr-title`. Branch protection also requires linear history (squash) and no force-pushes.

**Caching:**
- apt archives;
- pip tool caches;
- the Ubuntu base image (keyed on `image/base.lock`);
- `couchbox-media` (keyed on its recipe).

## Test plan

### Lint (`lint`)
- `shellcheck` and `shfmt -d` on every shell file.
- `ruff check` and `ruff format --check`.
- `qmllint` with Ubuntu 26.10's Qt 6, with the import paths of our modules and stubs. Warnings are errors, except a short documented allow-list for Plasma types qmllint can't resolve.
- JSON Schema validation of `defaults.json` (and that every key has a schema entry and a page), every app manifest, and a sample `release.json`.
- `reuse lint`: every file has a license.
- `markdownlint` and `lychee` (links) on the docs.

### Unit (`unit`, pytest, in the 26.10 container)

| Area | Examples |
|---|---|
| Settings | Defaults merge, validation errors, atomic write, migrations N→N+1, env-file generation, secrets never in exports |
| couchboxd | JSON-RPC over a temp socket: peer-credential checks (allowed or denied groups), schema validation, event stream, each namespace with fake NetworkManager / BlueZ / tailscale / cryptsetup backends |
| Updater | Version and channel selection (prereleases, `min_from` chains, bad-version skip), signature verification (good, bad, wrong namespace, rotated key), hash mismatch, resumable download, idle decision table (playing, TV standby, input recency, window, 3-day fallback), rollback path, release-notes rendering |
| Input mapper | Recorded evdev sequences → expected uinput keys and actions per focused app; Fire remote duplicate-key drops; long press; `voice-or:` |
| CEC | Command encoding, power-status parsing, input cycling |
| Home | Layout from manifests + settings (order, hidden, requires), web-app manifest creation, home.json output |
| Phone page | Token required, Origin checks, rotation logs out old phones |
| Voice | Mode routing (off, dictation, assistant), the simple command grammar, OpenAI-compatible request shapes (fake servers), cancellation |
| Unofficial clients | Parsers for VHX, Nebula, Twitch GQL/Helix and Seerr against recorded, scrubbed JSON fixtures; the Twitch ad filter on recorded playlists (ad segments, discontinuities, `EXT-X-MAP` per segment, sequence renumbering) |

**Coverage:** reported on every PR. The gate is ≥ 80 % for `settings`, `daemon`, `updater` and `phone`.

### UI (`qml`)
- **Screenshots:**
  - Every app and every Settings and wizard page is rendered off-screen at 1920×1080 and at 1280×720, using `--shot`, stub backends (`MpvVideo`, couchboxd) and fixture data.
  - The run fails on any QML warning or error.
- **Golden-image comparison:**
  - It runs against reviewed baselines (`tests/qml/golden/`), with a perceptual threshold.
  - Changes are approved by adding the `update-goldens` label, which commits the new images to the PR.
  - Every screenshot is uploaded as a PR artifact.
- **Key-driven flows** (`--keys`):
  - reordering a home tile;
  - joining Wi-Fi in the wizard (fake backend);
  - keyboard entry;
  - player open → Back.

### Package (`package`)
- `dpkg-buildpackage` and `lintian`.
- Install `./couchbox_*.deb` into a clean `ubuntu:26.10` container, resolving every dependency.
- Run `couchbox doctor --container`.
- Upgrade from the previous release's debs, downloaded from GitHub Releases, to check migrations.
- Reinstall (idempotent), then remove and purge (nothing left behind except what policy says).

### Encryption on loop devices (`encryption-loop`)
On the runner VM: create the image's LUKS2 layout, write data while re-encrypting online, interrupt and resume, then check the data and that the old key no longer works. Plan B's offline `--encrypt` is tested too.

### Image tests
- **`image`:** build the full image (nightly and on release). Check its size against the 2 GB limit, check partitions, and check that no private values or secrets appear anywhere in the image.
- **`image-boot`:**
  - Boot the image's root filesystem with `systemd-nspawn --boot`.
  - First-boot services complete and the preseed is applied (fixture `couchbox.toml`).
  - Every Couchbox system unit is active, and couchboxd answers.
  - The updater updates from a **fake release server** (local HTTP serving a test-signed release) and rolls back from a deliberately broken one.
  - Checks run with no network services configured, as G3 requires.
- **`initrd`:** QEMU `virt` (arm64, generic kernel, our dracut initrd, the image's LUKS partition). Covers the key-file unlock, Tang unlock with a `tang` container on the host network, and the passphrase prompt over serial with Tang stopped.
- **`session`:**
  - `kwin_wayland --virtual` with llvmpipe in the image root.
  - plasmashell loads the Couchbox home without QML errors.
  - Screenshot of the home and the wizard.
  - An app plays a generated HLS test clip (mpv with `--ao=null`).

### Hardware checklist

Run on the reference hardware before every minor release and 1.0. It's recorded in `tests/hardware/RESULTS.md` (model, firmware, TV, pass/fail, notes). Later it's automated on the HIL runner.

1. Flash the image with Imager (with and without customisation). The first boot reaches the wizard. CEC wakes the TV and switches input.
2. The wizard works with the TV remote only. Pair the Fire TV remote automatically. Program its IR for the TV (Power, Volume).
3. Wi-Fi from the wizard: 5 GHz, password with the on-screen keyboard.
4. Play YouTube 1080p60 with no dropped frames (`stats for nerds`). Twitch 1080p60 with chat. Nebula HEVC with hardware decode. Jellyfin HEVC with hardware decode. AirPlay mirroring.
5. Home: reorder, hide, rename and add a website, from Settings and with the Menu key.
6. Voice: off (message), dictation into YouTube search (STT endpoint), assistant (LLM endpoint).
7. Tailscale sign-in by QR; the phone page over HTTPS with pairing.
8. Encryption: encrypt from the remote; pull power mid-way and confirm it resumes; Tang over Wi-Fi; the passphrase with Tang off.
9. Updates: automatic update overnight with the TV in standby; manual mode notifies only; a broken release rolls back by itself.
10. 8 h playback soak: `vcgencmd get_throttled` = `0x0`, no memory growth past the swap threshold.
11. Factory reset, then the wizard again.

## Private-values guard (`no-private-values`)

- **What it checks:** a list of patterns kept in an encrypted Actions secret (`PRIVATE_PATTERNS`). The prototype's tailnet name, host names, LAN ranges and personal accounts never appear in the public repo, not even as the list itself.
- **When it runs:**
  - against the repo tree on every PR;
  - against image contents nightly.
- **Fork PRs:** they get no secrets, so the job skips with a notice and runs again on the merge to `main`.
- **Plus:** gitleaks for generic secrets.
