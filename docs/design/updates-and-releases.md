# Versioning, releases and updates

## Versioning

- **SemVer:** `MAJOR.MINOR.PATCH`.
  - MAJOR changes the base OS (for example, a move to Ubuntu 27.04) or breaks settings migrations.
  - MINOR adds features.
  - PATCH fixes things.
- **Tags:** `vX.Y.Z` for stable releases and `vX.Y.Z-beta.N` for prereleases (the beta channel).
- **Before 1.0,** `0.MINOR` may break things, and the release notes say so.
- **Version file:** the package version is the tag without the `v`. `couchbox --version` and Settings → Updates show it, plus the commit hash.
- **Commits** follow **Conventional Commits** (`feat:`, `fix:`, `feat!:`…). A PR-title check enforces it, and squash-merge keeps one commit per PR.

## Release flow

```
PRs merged to main ──► release-please keeps a "Release vX.Y.Z" PR updated (CHANGELOG.md + version)
                             │ merge it
                             ▼
                      tag vX.Y.Z + GitHub Release (draft)
                             │ release.yml (on tag)
                             ▼
  build debs ─► build image ─► test (package, image boot) ─► sign manifest ─► attest ─► upload ─► publish
```

- **Beta:** release-please runs in prerelease mode on a `beta` branch, or a manual `workflow_dispatch` with "prerelease" cuts `vX.Y.Z-beta.N` from main.
- **Hotfix:** a `fix:` PR merged to main, then the release PR, gives a patch release. No release branches before 1.0.
- **Manual approval:** the `release` GitHub environment holds the signing key and requires the maintainer's approval in Actions. Nothing is signed without that click.

### Release assets

| Asset | What |
|---|---|
| `couchbox_X.Y.Z_all.deb` | Main package |
| `couchbox-media_X.Y.Z_arm64.deb` | FFmpeg fork and Jellyfin Desktop |
| `couchbox-X.Y.Z-rpi5.img.xz` | Flashable image (+ `.sha256`) |
| `install.sh` | Installer for existing Ubuntu |
| `rpi-imager.json` | Raspberry Pi Imager repository entry (`releases/latest/download/rpi-imager.json` is the stable URL) |
| `release.json` + `release.json.sig` | Signed manifest (below) |
| `couchbox-media-X.Y.Z-sources.tar.xz` | Exact sources of the GPL/LGPL builds |
| `SBOM.spdx.json` | Package list of the image (syft) |

### `release.json`

```json
{
  "schema": 1,
  "version": "0.4.0",
  "channel": "stable",
  "commit": "8c1f…",
  "date": "2026-11-20T18:00:00Z",
  "base": {"os": "ubuntu", "version": "26.10"},
  "min_from": "0.2.0",
  "assets": {
    "couchbox_0.4.0_all.deb": {"sha256": "…", "size": 812345},
    "couchbox-media_0.4.0_arm64.deb": {"sha256": "…", "size": 40123456}
  },
  "notes_md": "…release notes…",
  "restart": ["session"],
  "reboot": false,
  "next_key": null
}
```

- **`min_from`:** devices on older versions update to an intermediate release first. The updater walks the chain.
- **`restart`:** which parts restart. `services` is quiet; `session` restarts the TV interface. `reboot` is only for kernel or initrd changes.
- **`base`:** a release with a different base never installs automatically. Settings offers it as a "System upgrade" with its own flow (R1 in the plan).
- **`next_key`:** announces a new signing key, signed by the current one, for key rotation.

### Signing

- **Key:** an ed25519 SSH key, kept only in the `release` environment secret `RELEASE_SIGNING_KEY`. An offline backup lives in the maintainer's password manager.
- **Signing:** `ssh-keygen -Y sign -f key -n couchbox-release release.json`.
- **Devices verify** with the public key the package ships (`/usr/share/couchbox/keys/allowed_signers`): `ssh-keygen -Y verify -f allowed_signers -I release@couchbox -n couchbox-release -s release.json.sig < release.json`. Then every asset's SHA-256 is checked against the manifest before dpkg sees it.
- **Provenance:** `actions/attest-build-provenance` attests each asset as well. Anyone can check one with `gh attestation verify <file> -R Supermaxman/couchbox`. Devices don't need this, but it shows that CI built the asset from that commit.

## The updater (`couchbox-updater`)

A `couchbox-updater.timer` fires every 6 h with a 1 h random delay, plus 10 min after boot.

```
check ──► newer release for my channel? ──no──► done
  │ yes
  ▼
download (resumable, to /var/lib/couchbox/updates/X.Y.Z/) ─► verify signature + hashes
  │
  ├─ mode = manual ─► mark "Update available" (Settings chip + one home-screen toast) ─► wait for "Install"
  │
  └─ mode = automatic ─► wait until idle ─► install ─► health check ─► ok: "Updated to X.Y.Z" toast
                                                         └─ fail: roll back, mark X.Y.Z bad, report
```

**Finding releases:**
- **stable:** `https://github.com/<source>/releases/latest/download/release.json`. This is a redirect, so it isn't subject to API rate limits.
- **beta:** `GET /repos/<source>/releases?per_page=10`, newest version wins. That's 4 calls a day, well under the anonymous limit of 60 an hour.
- **Errors:** a network error just means trying again later, with backoff. A signature error is logged loudly and shown in Settings → Updates ("Update couldn't be verified").

**When to install ("idle")**, in automatic mode, means all of these are true:
- No MPRIS player is playing, and no video is up in our apps, VacuumTube or Jellyfin.
- **And** either the TV is in standby (CEC power status) **or** there's been no input for 30 min.
- **And** it's inside `updates.window` (default 02:00–06:00). If no idle moment comes inside the window for 3 days, any idle moment counts.
- Manual "Install now" skips all of this and shows progress on screen.

**Install:**
1. Keep the current debs as the rollback set. Write `state/update.json` = `{from, to, started}`.
2. `apt-get install --allow-downgrades ./couchbox_X.Y.Z_all.deb ./couchbox-media_…deb`. This pulls new Ubuntu dependencies; if that fails, nothing changes and the update fails without effect.
3. Restart per `restart`. Reboot only if `reboot` is set **and** the TV is in standby (otherwise wait).

**Health check** (`couchbox doctor --post-update`, at most 3 min):
- Every enabled unit is active.
- couchboxd answers.
- The TV session is up (plasmashell running, home overlay loaded with no QML errors in the journal).
- Settings migrate and validate.
- The remote is still connected, if one was before.
- On a reboot release, the check runs after boot. The previous kernel/initrd stays available through the Pi's tryboot (`piboot-try`) path.

**Rollback:**
- **What happens:** the updater reinstalls the previous debs and restores the `settings.json` backup taken before the migration. It records `bad: X.Y.Z` so it doesn't retry that version, and reports it in Settings → Updates with the failing check.
- **Ubuntu dependencies** that were pulled in stay installed. Rolling them back is out of scope; packages only ever add or raise dependencies.
- **Manual rollback:** "Roll back to <previous>" in Settings does the same on demand.

**OS and app updates:**
- **Ubuntu:** stays with unattended-upgrades (`updates.os`, security updates by default). It reboots only for kernel updates, inside the window, with the TV in standby.
- **Flatpak apps:** update weekly, also at an idle time.
- **Settings → Updates** shows the last run of each.

**Forks:** `updates.source` points at another repo. The fork must ship its own key in its package, so a fork can't sign for the upstream repo, or the other way round.

## CLI

```
couchbox update status           version, channel, mode, last check, pending
couchbox update check            check now (no install)
couchbox update install [VER]    install now (latest if no version)
couchbox update rollback
couchbox update history
```
