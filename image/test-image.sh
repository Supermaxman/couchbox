#!/bin/bash
# Boot test for a built image: its root filesystem booted in systemd-nspawn (no kernel, no
# GPU): first boot and the preseed run, couchboxd answers, every Couchbox unit that can run
# in a container starts, settings work, and nothing private ended up in it.
#   sudo image/test-image.sh couchbox-X-rpi5.img.xz
set -euo pipefail
IMG=$(readlink -f "$1")
W=$(mktemp -d /tmp/couchbox-test.XXXX)
cleanup() { set +e; machinectl terminate cbtest 2>/dev/null; sleep 2; umount -l "$W/root/boot/firmware" "$W/root" 2>/dev/null; [[ -n ${LOOP:-} ]] && losetup -d "$LOOP"; rm -rf "$W"; }
trap cleanup EXIT
command -v systemd-nspawn >/dev/null || { apt-get update -qq && apt-get install -y -qq systemd-container >/dev/null; }
for i in $(seq 0 31); do [[ -e /dev/loop$i ]] || mknod -m 660 "/dev/loop$i" b 7 "$i"; done
xz -dc -T0 "$IMG" > "$W/disk.img"
LOOP=$(losetup -f -P --show "$W/disk.img")
mkdir -p "$W/root" && mount "${LOOP}p2" "$W/root" && mkdir -p "$W/root/boot/firmware" && mount "${LOOP}p1" "$W/root/boot/firmware"
ok() { printf '\033[32mok\033[0m %s\n' "$*"; }

# nothing private, no leftover keys
! ls "$W/root/etc/ssh/ssh_host_"* 2>/dev/null
[[ ! -s $W/root/etc/machine-id ]]
ok "no host keys, empty machine-id"
for f in brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.bin.zst brcm/brcmfmac43455-sdio.clm_blob.zst brcm/BCM4345C0.raspberrypi,5-model-b.hcd.zst; do
  chroot "$W/root" test -e "/usr/lib/firmware/$f" || { echo "!! missing firmware $f"; exit 1; }   # links resolve inside
done
ok "Pi 5 Wi-Fi and Bluetooth firmware present"
if grep -qw splash "$W/root/boot/firmware/current/cmdline.txt" && grep -qw quiet "$W/root/boot/firmware/current/cmdline.txt"; then
  ok "boot screen on (quiet splash)"
else echo "!! no boot screen: cmdline.txt is $(cat "$W/root/boot/firmware/current/cmdline.txt")"; FAIL=1; fi
# the TV user's session, written by couchbox-session-setup during the build: without the setup
# autostart a new box goes straight to Home, with no remote paired and no network
TVH=$W/root$(chroot "$W/root" getent passwd tv | cut -d: -f6)
for f in .config/autostart/couchbox-setup.desktop .config/autostart/couchbox-display.desktop .config/bluedevilglobalrc \
         .config/ksplashrc .config/systemd/user/graphical-session.target.wants/couchbox-mediakeys.service .local/share/couchbox/web-extension; do
  [[ -e $TVH/$f || -L $TVH/$f ]] || { echo "!! the TV user has no ~/$f (couchbox-session-setup stopped early?)"; FAIL=1; MISSING=1; }
done
[[ -n ${MISSING:-} ]] || ok "the TV user's session is set up (the setup wizard starts at the first login)"
# a preseed like a user would write
cat > "$W/root/boot/firmware/couchbox.toml" <<'X'
hostname = "testbox"
timezone = "Europe/Berlin"
[wifi]
ssid = "TestNet"
password = "test-fake-password"
[updates]
mode = "manual"
X
# what cloud-init writes from Raspberry Pi Imager's Wi-Fi settings (renderer networkd)
cat > "$W/root/etc/netplan/50-imager-test.yaml" <<'X'
network:
  version: 2
  wifis:
    renderer: networkd
    wlan0:
      dhcp4: true
      optional: true
      access-points:
        "ImagerNet":
          password: "test-fake-imager"
X
chmod 600 "$W/root/etc/netplan/50-imager-test.yaml"
systemd-nspawn -q -D "$W/root" --boot --machine=cbtest --network-veth -E COUCHBOX_IMAGE_TEST=1 >"$W/boot.log" 2>&1 &
for _ in $(seq 1 90); do
  sleep 2
  st=$(systemctl -M cbtest is-system-running 2>/dev/null || true)
  [[ $st == running || $st == degraded ]] && break
done
echo "system: $st"
run() { systemd-run -M cbtest --wait --pipe -q "$@"; }
run /usr/bin/couchbox config get network.hostname | grep -qx testbox && ok "preseed applied (hostname)"
run /usr/bin/couchbox config get updates.mode | grep -qx manual && ok "preseed applied (updates)"
if [[ $(cat "$W/root/etc/hostname") == testbox ]]; then ok "preseed host name in effect"
else echo "!! host name is $(cat "$W/root/etc/hostname"), not the preseed's testbox"; FAIL=1; FB=1; fi
if [[ $(readlink "$W/root/etc/localtime") == */Europe/Berlin ]]; then ok "preseed time zone in effect"
else echo "!! time zone is $(readlink "$W/root/etc/localtime"), not the preseed's Europe/Berlin"; FAIL=1; FB=1; fi
[[ -z ${FB:-} ]] || journalctl -M cbtest -b --no-pager | sed -n '/Starting couchbox-firstboot/,/Changed time zone to .Etc/p' | tail -80 || true
! grep -q 'test-fake-password' "$W/root/boot/firmware/couchbox.toml" && ok "preseed password erased"
grep -q 'psk=test-fake-password' "$W/root/etc/NetworkManager/system-connections/couchbox-TestNet.nmconnection" && ok "Wi-Fi from the preseed"
if ! grep -q networkd "$W/root/etc/netplan/50-imager-test.yaml" && run /bin/sh -c 'ls /run/NetworkManager/system-connections/' | grep -q 'netplan-wlan0-ImagerNet'; then
  ok "Wi-Fi from Imager goes to NetworkManager"
else echo "!! Imager Wi-Fi not handed to NetworkManager"; systemctl -M cbtest status couchbox-netplan.service --no-pager | tail -10 || true; FAIL=1; fi
run /usr/bin/couchbox config set voice.mode dictation >/dev/null && run /usr/bin/couchbox config get voice.mode | grep -qx dictation && ok "settings through couchboxd"
for u in couchboxd couchbox-phone couchbox-memory couchbox-firstboot; do
  s=$(systemctl -M cbtest is-active "$u.service" || true)
  if [[ $s == active ]]; then ok "$u: active"
  else echo "!! $u: $s"; systemctl -M cbtest status "$u.service" --no-pager | tail -15 || true; journalctl -M cbtest -u "$u.service" --no-pager | tail -20 || true; FAIL=1; fi
done
# couchbox-input: a container has no /dev/uinput, but the key map must load before that
if journalctl -M cbtest -u couchbox-input.service --no-pager 2>/dev/null | grep -q -E "input.toml|unknown key|has no match"; then
  echo "!! couchbox-input: key map problem"; journalctl -M cbtest -u couchbox-input.service --no-pager | tail -15; FAIL=1
else ok "couchbox-input: key map loads (no /dev/uinput in a container)"; fi
# systemd drops a job to break an ordering cycle (couchbox-cloudinit-off once never ran that way).
# A container boots without cloud-init, so the boot as on a Pi (with cloud-init.target) is verified too.
cyc=$({ journalctl -M cbtest -b --no-pager; run /bin/sh -c 'systemd-analyze verify --man=no graphical.target cloud-init.target 2>&1'; } 2>/dev/null \
  | grep -i 'ordering cycle' | grep -i couchbox || true)
if [[ -n $cyc ]]; then echo "!! ordering cycle with a Couchbox unit:"; echo "$cyc"; FAIL=1
else ok "no ordering cycles with Couchbox units (as booted, and with cloud-init as on a Pi)"; fi
run /usr/bin/couchbox doctor --container || FAIL=1
echo "failed units:"; systemctl -M cbtest list-units --failed --no-pager --plain | head -20 || true
[[ -z ${FAIL:-} ]] || { echo "image test: FAILED"; exit 1; }
echo "image test: passed"
