# Installing Couchbox

You need the [reference hardware](design/first-boot.md#reference-hardware): a Raspberry Pi 5 (8 GB is best), an NVMe drive on the M.2 HAT+ (or a microSD card), the Active Cooler, the official 27 W power supply and a micro-HDMI to HDMI cable. A Fire TV remote is optional, because your TV's own remote works over HDMI-CEC.

## 1. Flash

**With Raspberry Pi Imager:**
1. Open Imager. In *App Options*, set the content repository to:
   ```
   https://github.com/Supermaxman/couchbox/releases/latest/download/rpi-imager.json
   ```
2. Choose *Raspberry Pi 5*, then **Couchbox**, then your NVMe drive (in a USB adapter) or SD card.
3. Optionally, use Imager's customisation to set Wi-Fi, a user and an SSH key. Anything you leave out, the TV asks for.

**Or with any image writer** (balenaEtcher, GNOME Disks, `dd`): download `couchbox-VERSION-rpi5.img.xz` from the [latest release](https://github.com/Supermaxman/couchbox/releases/latest) and write it.

**Preseed (optional):** after writing, the drive's boot partition (FAT, readable on any computer) has `couchbox.toml.example`. Copy it to `couchbox.toml` and fill in Wi-Fi, time zone, Jellyfin and so on. It's read once at first boot, and its passwords and keys are erased afterwards.

## 2. Plug in

1. Turn on HDMI-CEC on the TV: Anynet+ (Samsung), SimpLink (LG), Bravia Sync (Sony), or simply "HDMI-CEC" elsewhere.
2. Connect the Pi to the TV.
3. Plug in Ethernet if you have it.
4. Power on.

The first boot takes a minute or two. The TV switches to the box by itself.

## 3. Set up on the TV

The setup takes you through these steps:
1. **Remote.** Pair a Fire TV remote by holding Home for 10 s, or skip and use the TV's remote.
2. **Internet.** Join Wi-Fi.
3. **Location.** Pick your city, which sets the time zone and the weather.
4. **Name.** Name the box.
5. **TV buttons.** Program the Fire TV remote's TV buttons.
6. **Updates.** Choose Automatic or Manual.
7. **Extras.** Optionally add Jellyfin, Seerr and voice.

The apps (YouTube, Chromium) download in the background. Everything is in **Settings**, the last tile on the home row.

## Installing on an existing Ubuntu

On a Raspberry Pi 5 already running **Ubuntu Server 26.10** (64-bit):

```
curl -fsSL https://github.com/Supermaxman/couchbox/releases/latest/download/install.sh | sudo bash
sudo reboot
```

The installer checks the release's signature, installs the packages (Plasma Bigscreen comes from Ubuntu) and keeps SSH working.

## Updates

Couchbox checks GitHub Releases every 6 hours:
- **Automatic** (the default) installs updates when nobody's watching, during the install hours (02:00–06:00 by default). After each update the box runs its checks and rolls back by itself if anything fails.
- **Manual** shows "Update available" in Settings → Updates.

Ubuntu's security updates install by themselves too.

## When something's wrong

- **Settings → System → Run checks** shows what isn't working.
- Over SSH (Settings → Remote access): `couchbox doctor`, and `journalctl -u 'couchbox*'` for the logs.
- Report bugs at https://github.com/Supermaxman/couchbox/issues, with `couchbox doctor` output.
