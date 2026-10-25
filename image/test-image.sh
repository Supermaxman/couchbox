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
command -v systemd-nspawn >/dev/null || apt-get install -y -qq systemd-container >/dev/null
for i in $(seq 0 31); do [[ -e /dev/loop$i ]] || mknod -m 660 "/dev/loop$i" b 7 "$i"; done
xz -dc -T0 "$IMG" > "$W/disk.img"
LOOP=$(losetup -f -P --show "$W/disk.img")
mkdir -p "$W/root" && mount "${LOOP}p2" "$W/root" && mount "${LOOP}p1" "$W/root/boot/firmware"
ok() { printf '\033[32mok\033[0m %s\n' "$*"; }

# nothing private, no leftover keys
! ls "$W/root/etc/ssh/ssh_host_"* 2>/dev/null
[[ ! -s $W/root/etc/machine-id ]]
ok "no host keys, empty machine-id"
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
! grep -q 'test-fake-password' "$W/root/boot/firmware/couchbox.toml" && ok "preseed password erased"
grep -q 'psk=test-fake-password' "$W/root/etc/NetworkManager/system-connections/couchbox-TestNet.nmconnection" && ok "Wi-Fi from the preseed"
run /usr/bin/couchbox config set voice.mode dictation >/dev/null && run /usr/bin/couchbox config get voice.mode | grep -qx dictation && ok "settings through couchboxd"
for u in couchboxd couchbox-phone couchbox-memory couchbox-firstboot; do
  s=$(systemctl -M cbtest is-active "$u.service" || true)
  [[ $s == active ]] && ok "$u: active" || { echo "!! $u: $s"; systemctl -M cbtest status "$u.service" --no-pager | tail -15; FAIL=1; }
done
run /usr/bin/couchbox doctor --container
[[ -z ${FAIL:-} ]] && echo "image test: passed"
