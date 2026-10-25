# Install Couchbox

Setting up a new box takes about 20 minutes. **You don't need a keyboard, a mouse or a monitor.** You use a computer once, to write Couchbox onto a USB stick. After that it's the TV, and any one of:
- your TV's own remote;
- a Fire TV remote;
- your phone.

- [What you need](#what-you-need)
- [The short version](#the-short-version)
- [1. Write Couchbox onto a USB stick](#1-write-couchbox-onto-a-usb-stick)
- [2. Plug everything in](#2-plug-everything-in)
- [3. Take control: TV remote, Fire TV remote or phone](#3-take-control-tv-remote-fire-tv-remote-or-phone)
- [4. Install to the SSD](#4-install-to-the-ssd)
- [5. Finish the setup](#5-finish-the-setup)
- [Other ways to install](#other-ways-to-install)
- [When something's wrong](#when-somethings-wrong)

## What you need

| | |
|---|---|
| The box | A **Raspberry Pi 5** with its SSD fitted on the M.2 HAT+, the Active Cooler and the official 27 W power supply. The full list is in [reference hardware](design/first-boot.md#reference-hardware) |
| HDMI | A micro-HDMI to HDMI cable (the official one carries HDMI-CEC, so the TV remote works) |
| A USB stick | **16 GB or larger**, USB 3 if you have one. It's erased. You get it back at the end |
| A computer | Windows, macOS or Linux, to write the stick |
| A remote, any one | The TV's remote, a Fire TV remote, or a phone with a camera |
| Internet | Wi-Fi or an Ethernet cable |

## The short version

1. On your computer, use **Raspberry Pi Imager** to write Couchbox onto the USB stick. Enter your Wi-Fi there too.
2. Put the stick in the Pi, connect it to the TV and plug in the power.
3. On the TV, pair your remote or scan the QR code with your phone. Choose **Install to the SSD**. The box restarts from the SSD; pull out the stick, then finish the setup.

## 1. Write Couchbox onto a USB stick

You write Couchbox to the stick with **Raspberry Pi Imager**, the free official tool. Get it at [raspberrypi.com/software](https://www.raspberrypi.com/software/).

1. **Add Couchbox to Imager.**
   - Open Imager and its **App Options** (or *Options*).
   - Next to **Content Repository**, choose *Edit* (or *Use custom URL*) and paste:
     ```
     https://github.com/Supermaxman/couchbox/releases/latest/download/rpi-imager.json
     ```
   - Imager reloads its list. Couchbox is now the operating system on offer.
2. **Device:** Raspberry Pi 5.
3. **Operating system:** **Couchbox**.
4. **Storage:** your USB stick. Check that it's the stick: everything on it is erased.
5. **Customisation.** Imager offers to customise the system; say yes. All of this is optional, and the TV asks for anything you leave out.
   - **Wi-Fi (recommended):** your network's name and password, and your country. The box is then online from the first minute, so your phone can be the remote straight away and you don't type the password with a remote.
   - **Hostname:** for example `livingroom`, otherwise `couchbox`.
   - **Time zone.**
   - **Username and password:** Couchbox doesn't need them. If Imager insists, use anything: the TV logs in by itself.
   - **SSH**, only if you want remote access. Use a public key.
6. **Write**, and wait for Imager to write and check the stick. That takes 5–10 minutes.

<details>
<summary>Without Imager, or if Couchbox doesn't show up in it</summary>

1. Download `couchbox-<version>-rpi5.img.xz` from the [latest release](https://github.com/Supermaxman/couchbox/releases/latest).
2. Write it with any image writer: Imager's *Use custom*, balenaEtcher, GNOME Disks, or `xz -dc couchbox-*.img.xz | sudo dd of=/dev/sdX bs=4M status=progress`.
3. **Wi-Fi without Imager's settings:**
   - Unplug the stick and plug it back in. A drive called **system-boot** appears.
   - On it, copy `couchbox.toml.example` to **`couchbox.toml`**, then fill in `[wifi]` (and the time zone, if you like).
   - The box reads that file once, at first start, then erases the password from it.
</details>

## 2. Plug everything in

1. **Remove the SD card**, if the Pi has one. The Pi starts from an SD card before anything else.
2. Put the **USB stick** in one of the Pi's **blue** USB ports.
3. Connect the HDMI cable to the Pi's **HDMI 0** port, the one next to the USB-C power socket. Connect the other end to the TV.
4. **Ethernet:** plug it in now if you have it.
5. **Fire TV remote:** if it's paired with a Fire TV Stick, unplug the Stick. Otherwise the remote goes back to it.
6. **Turn on HDMI-CEC on the TV.** It lets the TV's remote control Couchbox. Each brand has its own name for it:
   - Samsung: Anynet+
   - LG: SimpLink
   - Sony: Bravia Sync
   - Others: HDMI-CEC or HDMI Control
7. **Plug in the power.**

The first start takes **2–3 minutes**. The Pi first prepares the stick. The TV switches to the box by itself; if it doesn't, choose its HDMI input. Then the setup starts.

## 3. Take control: TV remote, Fire TV remote or phone

You can use any of these, and switch between them whenever you like.

- **The TV's remote:** the arrows, OK and Back work straight away over HDMI-CEC.
- **A Fire TV remote:** on the **Your remote** screen, hold its **Home** button for about 10 seconds, until the light blinks. It pairs by itself. From then on it works like a normal TV remote, and its power and volume buttons can control the TV (a later step sets that up).
- **Your phone:** point the phone's camera at the **QR code** on the left of the screen and open the link. You get a remote with arrows, OK, Back, Home and play/pause, and a keyboard that types on the TV.
  - **When the box isn't online yet** (no Ethernet, and no Wi-Fi set in Imager), it opens its own Wi-Fi after about 30 seconds, and the TV shows two codes:
    1. **Join its Wi-Fi.** Scan the first code, and the phone joins **Couchbox-XXXX**. If the phone warns that the network has no internet, choose to stay connected.
    2. **Open the remote.** Scan the second code.
  - On the **Internet** step, pick your home Wi-Fi and type its password on the phone. The box joins your network and its own Wi-Fi closes. Your phone goes back to your home Wi-Fi, and the TV shows a new code: scan it to keep using the phone.

## 4. Install to the SSD

Right after the remote, the setup offers **Install to the SSD**. It copies Couchbox from the stick onto the SSD inside the box. The SSD is faster, and the stick is free again afterwards.

1. Choose **Install to SSD …**, then confirm. Everything on the SSD is erased.
2. Wait about 5 minutes. The screen shows the progress. Leave the box on.
3. Choose **Restart now**. The box starts from the SSD and carries on with the setup where you left it. Your Wi-Fi and the paired remote come along.
4. **Pull out the USB stick** whenever you like. You can use it for something else.

**From an SD card instead of a stick:** the last button is **Shut down**. Take the card out, then plug the power back in.

**No SSD?** Choose *Skip* and Couchbox keeps running from the stick or card. It works, but it's slower. You can install to an SSD later: Settings → System → Run the setup again.

## 5. Finish the setup

The rest takes a few minutes. Every step can be skipped and changed later in **Settings**, the last tile on the home row.

| Step | |
|---|---|
| Internet | Already done if you set Wi-Fi in Imager or use Ethernet. Otherwise, pick your Wi-Fi and type the password |
| Time zone and location | For the clock and the weather on the home screen |
| Name | How the box shows up on your network, in AirPlay and on the TV's input list |
| TV buttons | Makes the Fire TV remote's power and volume buttons control your TV |
| Updates | **Automatic** (recommended): updates install while nobody's watching. Or Manual |
| Extras | Optional: Jellyfin, Seerr, voice, Tailscale, disk encryption, SSH |
| Apps | YouTube and the other apps download in the background (about 1.5 GB) |

Then you're on the home screen.
- **Home** on any remote brings you back to it.
- **Menu** on a tile (or hold OK) moves, hides or renames it.

## Other ways to install

- **Straight onto the SSD.** If you have a USB adapter for NVMe drives, write Couchbox onto the SSD itself in step 1. Then fit the SSD in the Pi. The setup skips step 4.
- **SD card.** Write a 32 GB or larger card instead of a stick. It works the same way, and you can install to an SSD from it, as described in [step 4](#4-install-to-the-ssd).
- **Already running Ubuntu Server 26.10 on a Pi 5:**
  ```
  curl -fsSL https://github.com/Supermaxman/couchbox/releases/latest/download/install.sh | sudo bash
  sudo reboot
  ```
  The installer checks the release's signature, installs the packages and keeps SSH working.

## When something's wrong

| Problem | What to do |
|---|---|
| The TV shows "no signal" | The first start takes up to 3 minutes. Check the cable is in **HDMI 0**, the port next to the power socket, and that the TV is on the right input |
| The Pi doesn't start from the stick | Take out any SD card. Use a blue USB port. Pi 5 boards made before 2024 may need a bootloader update: in Imager, *Misc utility images* → *Bootloader (Pi 5)* → *USB Boot*, written to a spare SD card. Start the Pi with that card until the green light blinks steadily, then remove the card |
| The TV remote does nothing | Turn on HDMI-CEC in the TV's settings (Anynet+, SimpLink, Bravia Sync). Some cheap cables don't carry CEC. Meanwhile, use your phone |
| The phone code doesn't open | The phone has to be on the same Wi-Fi as the box, or on **Couchbox-XXXX** when the box shows that network. Turn off "private relay" or a VPN on the phone while you set up |
| The Fire TV remote doesn't pair | Unplug any Fire TV Stick it was paired with. Take the remote's batteries out for 5 seconds, then hold Home for 10 seconds. **Don't** reset it with Menu + Back + Left: that erases its TV buttons |
| "Install to the SSD" isn't offered | The SSD isn't detected. Power off, then check the ribbon cable between the Pi and the M.2 HAT+ (contacts facing the right way) and that the SSD is screwed in |
| Something else | Settings → System → **Run checks** shows what isn't working. Over SSH: `couchbox doctor` and `journalctl -u 'couchbox*'`. Report bugs at [GitHub issues](https://github.com/Supermaxman/couchbox/issues) with the `couchbox doctor` output |

## Updates

Couchbox checks GitHub Releases every 6 hours. Releases are signed, and the box checks the signature before it installs anything.
- **Automatic** (the default) installs updates when nobody's watching, during the install hours (02:00–06:00 by default). After each update the box runs its checks, and rolls back by itself if anything fails.
- **Manual** shows "Update available" in Settings → Updates.

Ubuntu's security updates install by themselves too.
