# Disk encryption (optional)

- **Off by default.** Settings → Security → **Encrypt this box** turns it on, from the remote, while you keep watching.
- **Unlock at boot** uses any mix of:
  - **a passphrase**, typed at boot on a USB keyboard; always present as the recovery method;
  - **network unlock** through one or more **Tang servers** (Clevis). The box unlocks itself when it can reach one, over **Ethernet or Wi-Fi**.
- **No TPM:** the Pi 5 has none, so there's no "sealed to this device" option.

## Design: LUKS2 from the start, re-keyed online (D12)

The prototype encrypted in place from a USB-booted system. That needed a second boot medium, a keyboard and SSH, and none of that is acceptable for a box set up from the couch. Couchbox instead does this:

1. **The image's root partition is already LUKS2.**
   - It is unlocked by a key file inside the initrd, so it boots unattended.
   - That key file is the same for every image and public, so the disk is **not protected** in this state. Settings says exactly that.
2. **Encrypt this box** in Settings:
   1. Asks for the passphrase on the on-screen keyboard or the phone page, typed twice.
   2. Optionally asks for Tang URLs. Each one is fetched and its thumbprint shown, to compare with the server's `tang-show-keys`.
   3. Optionally asks "Unlock over Wi-Fi", explained below.
3. **couchboxd then:**
   1. Adds the passphrase keyslot (argon2id).
   2. Starts **online re-encryption with a new random volume key**: `cryptsetup reencrypt --resilience checksum /dev/nvme0n1p2` on the mounted, active device. It runs in the background at low I/O priority, with progress shown in Settings and on the home screen. A power cut resumes it at the next boot, because the LUKS2 re-encryption metadata is crash-safe.
   3. When it finishes, removes the image key-file keyslot.
   4. Binds Tang (`clevis luks bind … sss '{"t":1,"pins":{"tang":[…]}}'`).
   5. Rebuilds the initrd **without** the key file, with Clevis, networking and (optionally) Wi-Fi. It installs that initrd through the Pi's tryboot path (`piboot-try`), so a failed boot falls back to the previous initrd.
4. **Afterwards, in Settings:**
   - status;
   - change passphrase;
   - add or remove Tang servers;
   - Wi-Fi at boot on or off;
   - "Save recovery info" to the phone page: the LUKS UUID and a header backup (`cryptsetup luksHeaderBackup`), **never** the passphrase.

**Why the key has to change:** anyone with the public image can derive the image's volume key. So moving from "not protected" to "protected" must replace the volume key, not just add a passphrase. Online re-encryption does that without unmounting.

### First boot

- **State:** first boot leaves the disk in "not protected" mode. Generating a fresh volume key there would cost a full re-encryption at first boot, which is 15–30 minutes of slow first impressions, for users who may not want encryption at all.
- **Choosing it:** the wizard offers "Encrypt now" as one of its optional extras, and it runs in the background.

### Cost when not encrypting

Every read and write goes through dm-crypt even in "not protected" mode. The Pi 5's Cortex-A76 has AES instructions, and the prototype box has run LUKS2 every day with no visible slowdown. **M6a measures** `cryptsetup benchmark` and app start times against plain ext4. Over 10 % slower makes plan B the default.

## Wi-Fi at boot

- **What it is:** a dracut module (`90couchbox`, ported from the prototype's `90mtv-wifi`) runs wpa_supplicant in the initrd, so Clevis can reach Tang without Ethernet.
  - It includes the Pi 5 Wi-Fi firmware, the regulatory database and DHCP on `eth0`/`wlan0`.
  - wait-online accepts either interface, with a 45 s timeout.
- **Credentials:** they come from the **current NetworkManager connection**, as a hashed PSK.
  - When you change Wi-Fi or its password in Settings, couchboxd rebuilds the initrd. It asks first: "Update the network unlock to use this Wi-Fi?"
- **Trade-off, shown in the UI:**
  - The initrd lives on the unencrypted boot partition, so **anyone with the drive can read the Wi-Fi key**.
  - Ethernet-only network unlock avoids that.
  - The prototype accepted the same trade-off.

## Tang servers

- **What a server needs:** Tang is tiny and stateless. Any always-on Linux machine on the LAN will do: `apt install tang`, a NAS container, or a home server. The docs give a 3-step guide.
  - The prototype ran Tang on port 7500, LAN only, behind a firewall rule.
- **More than one server:** Couchbox can bind several (Shamir threshold 1 of n), so any one of them unlocks the disk.
- **What Tang never sees:** the key. It only helps derive it, and only for a client that can reach it.
- **If the Tang keys are lost** (back up `/var/lib/tang` on the server), the box falls back to the passphrase.

| Threat | Protected? |
|---|---|
| Box stolen and powered up away from home | Yes. No Tang reachable means it asks for the passphrase |
| Drive pulled and read elsewhere | Yes |
| Box stolen and booted on your LAN | No. It auto-unlocks, which is the point of network unlock |
| Boot partition tampered with to capture keys later | No. That needs Raspberry Pi secure boot, which is irreversible and out of scope |
| Wi-Fi key read from the boot partition | No, when Wi-Fi at boot is on (see above) |

## Passphrase at boot

- **When it's asked:** when no Tang answers within 45 s, the console asks for the passphrase. That needs a **USB keyboard** in 1.0.
- **After 1.0:** a remote-friendly unlock prompt, with the paired Bluetooth remote or CEC keys and an on-screen keyboard, in the initrd.

## Plan B

**If M6a shows online re-keying isn't reliable or is too slow on the Pi 5:**
- The image ships with **plain ext4**.
- **Encrypt** sets up an *encrypt at next boot*: the dracut module runs `cryptsetup reencrypt --encrypt --reduce-device-size 32M` in the initrd, before root is mounted, with progress on the console.
- **That pass uses a one-time random key file**, so nobody has to type anything at the console. The key file sits on the boot partition only until the next step.
- **Right after the first unlocked boot,** couchboxd does what steps 3 and 4 above do:
  - adds your passphrase, which it kept root-only on the disk that has just been encrypted;
  - re-keys online, so the volume key changes and the one-time key file is worthless;
  - deletes the key file and binds Tang.
- **Cost:** plan B means two passes over the disk instead of one.

### Installer systems

Boxes set up with `install.sh` keep the root layout they have:
- **Already LUKS** (like the prototype box): Settings manages its keyslots and Tang bindings and shows "Encrypted (set up before Couchbox)".
- **Plain ext4:** they use plan B.

## Tests

- **Every pull request (loop devices on the CI VM):**
  - create a LUKS2 image with the image key;
  - mount it and write data;
  - online re-encrypt while it's being written to;
  - kill it mid-way and resume;
  - check the data;
  - check the old key no longer opens it.
- **Nightly (QEMU arm64 `virt`, generic kernel and our initrd):**
  - key-file unlock;
  - Tang unlock against a Tang container;
  - passphrase fallback with Tang stopped (typed over QEMU's serial console).
- **Hardware checklist:**
  - encrypt from the remote;
  - pull power at about 50 %;
  - boot and confirm it resumes;
  - Tang unlock over Wi-Fi;
  - passphrase unlock with Tang off.
