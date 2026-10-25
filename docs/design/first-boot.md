# From a fresh Pi to a working TV

## Reference hardware

This is the tested set. Other NVMe drives and cases generally work, but only this set is tested before each release.

| Part | Model | Notes |
|---|---|---|
| Board | Raspberry Pi 5, **8 GB** | 4 GB works with fewer apps open at once (swap on NVMe). 2 GB is not supported |
| Power | Raspberry Pi 27 W USB-C PSU (SC1158) | Needed for full USB current with an NVMe drive |
| Cooling | Raspberry Pi Active Cooler (SC1148) | Long playback without throttling |
| Storage | NVMe 2230/2242 on the **Raspberry Pi M.2 HAT+** (SC1116), e.g. Samsung PM9C1a 256 GB | Or a 32 GB+ A2 microSD card (slower app starts) |
| Case | One that fits the cooler, the HAT+ and exposed micro-HDMI (e.g. PiShop HighPi Pro 5S) | |
| HDMI | Micro-HDMI to HDMI, e.g. Raspberry Pi SC0532 | **CEC needs the cable's pin 13 connected**; the official cable has it |
| Remote | Amazon Fire TV remote (tested: model `0171:0427`, firmware `53101201`) | Optional: the TV's own remote works over CEC |
| TV | Any with HDMI-CEC (Samsung "Anynet+", LG "SimpLink", Sony "Bravia Sync") | Turn CEC on in the TV's settings |

## Install paths

| Path | For | Steps |
|---|---|---|
| **A. Image on a USB stick (recommended)** | Everyone | Write `couchbox-<version>-rpi5.img.xz` to a USB stick, boot the Pi from it, follow the TV. The wizard installs to the SSD. No keyboard or monitor ([install.md](../install.md)) |
| B. Installer | People already running Ubuntu Server 26.10 on a Pi 5 | `curl -fsSL https://github.com/Supermaxman/couchbox/releases/latest/download/install.sh \| sudo bash`, then reboot into the wizard ([image-and-packaging.md](image-and-packaging.md#installer)) |

### A. Flashing

- **Raspberry Pi Imager:**
  - Add Couchbox's repository URL, `…/releases/latest/download/rpi-imager.json`, in Imager's options ("Content repository").
  - Then *Choose OS* → **Couchbox**.
  - Imager's **OS customisation** works: Wi-Fi, host name, time zone, user and SSH key are applied at first boot through cloud-init. Every one is optional; the wizard asks for whatever is missing.
- **Any image writer** (Etcher, `dd`, GNOME Disks): write the `.img.xz`.
- **USB stick → SSD (the default path):** the Pi 5 bootloader's default order is SD card, NVMe, USB.
  - A blank SSD is skipped, so the stick boots.
  - The wizard's **Install to the SSD** step (`couchbox.install_disk`) copies the running system to the NVMe drive:
    - a FAT boot partition the size of the stick's;
    - an ext4 root over the rest of the drive;
    - `rsync -aHAXx`;
    - fstab and every `cmdline.txt` rewritten to the new partitions' PARTUUIDs;
    - a fresh swap file.
  - It's the same box: settings, Wi-Fi, the paired remote, the machine-id and the wizard's progress come along.
  - After the restart the SSD boots first, even with the stick still in. The PARTUUIDs keep `LABEL=writable` on the stick from being picked by mistake.
  - From an SD card, the card has to come out: the wizard shuts down and says so.
  - Tested on loop devices in CI (`ci/install-disk-loop.sh`). Also `couchbox install-to-disk` over SSH.
- **NVMe directly:** write to the drive in a USB NVMe adapter, then fit it to the HAT+. The wizard skips the install step.
  - The Pi 5 bootloader boots NVMe when no SD card is inserted. This needs current bootloader firmware, and Pi 5 boards from 2024 on have it.
  - **To verify in M4:** the factory EEPROM boot order on new boards, and whether we need to tell people to update the bootloader first. The fallback is Raspberry Pi Imager's "Bootloader → NVMe/USB boot" image on a spare SD card.
- **SD card:** works like the stick. Install to the SSD from it, or keep running from the card.

### Preseed

`couchbox.toml` on the FAT boot partition. You can edit it from any computer after flashing. It's read once, at first boot, and then the secrets in it are erased. It's for people setting up several boxes, or with no TV remote to hand.

```toml
hostname = "livingroom"
timezone = "America/Los_Angeles"
[wifi]
ssid = "Home"
password = "…"            # erased from the file after first boot
[location]
name = "Springfield"     # looked up with Open-Meteo geocoding
[updates]
mode = "automatic"
[ssh]
github_user = "someone"
[tailscale]
auth_key = "tskey-auth-…"   # erased after first boot
[skip]
wizard = false             # true: go straight to the home screen once the network is up
```

Order: package defaults, then Imager/cloud-init, then `couchbox.toml`, then the wizard. A later source wins.

## First boot, step by step

1. **System first boot** (no screen interaction, about 1–2 min):
   - The root filesystem grows to fill the disk.
   - A new machine-id and new SSH host keys are generated.
   - The disk stays in "not protected" mode (LUKS2 with the image's shared key) until you choose Encrypt; see [encryption.md](encryption.md#first-boot).
   - cloud-init applies any Imager settings, then disables itself.
   - The preseed is applied.
2. **The TV wakes up.** couchbox-cec sends Image View On + Active Source, so the TV switches to the box from any input.
3. **The setup wizard** (`couchbox-setup`, full screen) starts instead of the home screen. Each step can be finished with:
   - the **TV remote over CEC** (arrows, OK, Back);
   - a Fire TV remote, once paired;
   - a USB keyboard;
   - **the phone:** every step shows the phone page's QR code (by IP address, since not every phone resolves `.local`).
     - Offline for 25 s (no Ethernet, no Wi-Fi from Imager or the preseed), or for 2 minutes with a saved Wi-Fi that may still be joining? couchboxd opens a **setup Wi-Fi**, `Couchbox-XXXX`, with a random password. It's NetworkManager's hotspot at 10.42.0.1.
     - The TV then shows two codes: a `WIFI:` code to join, and the phone page at `http://10.42.0.1:8791`.
     - The radio can't scan while it's a hotspot, so the Wi-Fi list is the scan from just before.
     - Joining home Wi-Fi closes the hotspot, and reopens it if the join fails. Ethernet coming up, or the end of the wizard, closes it too.

| Step | What it shows | Skippable |
|---|---|---|
| 1. Hello | "Couchbox. Use your TV remote's arrows and OK." Also starts **scanning for remotes** in the background | — |
| 2. Remote | "Have a Fire TV remote? Hold its **Home** button for 10 seconds." Pairs automatically as soon as one shows up (BlueZ agent, retries), then: "Press any button on the new remote" to confirm. Also explains: don't factory-reset the remote (Menu + Back + Left) because that erases its TV IR codes | yes ("Use the TV remote") |
| 2b. Install to the SSD | Only when running from a USB stick or SD card with an SSD present. Copy, then restart (stick) or shut down and remove the card (SD). Setup resumes at Network on the SSD | yes ("keep running from the stick") |
| 3. Network | Ethernet connected → shows it, Next. Otherwise the Wi-Fi list → password on the on-screen keyboard. Checks internet access and shows the result | no (needed for apps and time) |
| 4. Time zone and location | A suggestion from the Wi-Fi country, or "Detect" (asks once). City search for the weather (optional). °F/°C | yes |
| 5. Name | `couchbox`, or type one. Used on the network, in AirPlay and in the TV's source list | yes |
| 6. TV buttons | If a Fire remote is paired: "Program its Power and Volume buttons for your TV?" Brand list → test → keep | yes |
| 7. Updates | **Automatic (recommended)** or Manual | default Automatic |
| 8. Extras | A checklist that leads into the same Settings pages: Jellyfin (offers servers found on the LAN), Seerr, voice and assistant, Tailscale (QR sign-in), encryption, SSH | yes, all |
| 9. Apps | YouTube, Chromium and Jellyfin download in the background from step 3 on (Flatpak, about 1.5 GB). This step shows progress, then "You're set" | no wait if already done |
| 10. Done | The home screen. Tips: Home goes home, Menu on a tile customizes it, the mic button needs voice set up | — |

The wizard stores its progress in `/var/lib/couchbox/state/setup.json`, so a reboot or power loss resumes at the same step. Running it again: Settings → System → "Run setup again".

## Remote pairing details

- **Auto-pairing in the wizard:**
  - couchboxd keeps a BlueZ discovery session open from step 1 until a remote pairs or step 2 is skipped.
  - It pairs the first device that matches the remote name pattern (`AR`, `Amazon`, `Fire`, `*Remote`) or the HID remote class.
  - Its agent accepts pairing confirmation automatically, because the user started this on purpose.
- **Reconnects:** the remote is trusted, so it reconnects on any key press. couchbox-cec re-activates its IR table on each reconnect, as Fire OS does.
- **Menu key:** on the home screen, Menu (≡) opens a tile's options (move, hide, rename). Elsewhere it keeps Bigscreen's meaning, the running-apps overview.
- **No remote at all:**
  - The TV's own remote keeps working over CEC.
  - A USB keyboard works.
  - The phone page: its QR code is on every wizard step (through the setup Wi-Fi when offline), and later in Settings → Remote access.

## Failure paths the wizard handles

| Problem | What the user sees |
|---|---|
| The TV doesn't do CEC (or it's off) | The wizard works with a USB keyboard. A banner explains turning on CEC (Anynet+, SimpLink…) with brand-specific names |
| No network | "Couchbox needs internet for apps and the clock." Retry, other Wi-Fi, or hidden network |
| The remote won't pair | "Hold Home for 10 s until the light blinks fast. Still nothing? Remove the batteries for 5 s." Retries forever, and "Skip" is always available |
| Flatpak download fails | Retries in the background. The home screen shows "Downloading YouTube…" on the tile |
| Clock wrong, so TLS fails | NTP sync is awaited before app downloads. The wizard shows "Setting the clock…" |
