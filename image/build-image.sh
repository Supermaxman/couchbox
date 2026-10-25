#!/bin/bash
# Build the Couchbox image: Ubuntu 26.10 for Raspberry Pi + the Couchbox packages.
#   sudo image/build-image.sh VERSION DEBDIR OUTDIR [--luks]
# Runs natively on arm64 (GitHub's ubuntu-24.04-arm runners): loop devices, chroot, no emulation.
#   DEBDIR   couchbox_*.deb (and couchbox-media_*.deb if built)
#   OUTDIR   gets couchbox-VERSION-rpi5.img.xz and its .sha256
#   --luks   (planned) root on LUKS2 opened by the image key, "not protected" until Settings →
#            Security encrypts it (docs/design/encryption.md). Waits for the hardware test (M6a).
set -euo pipefail
VERSION=$1 DEBS=$(readlink -f "$2") OUT=$(readlink -f "$3")
if [[ ${4:-} == --luks ]]; then
  echo "--luks (root on LUKS2 from the start) waits for the hardware test of online re-encryption (M6a)." >&2
  exit 2
fi
HERE=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=/dev/null
. "$HERE/base.lock"
CACHE=${COUCHBOX_IMAGE_CACHE:-/var/cache/couchbox-image}
W=$(mktemp -d /tmp/couchbox-image.XXXX)
R=$W/root
SIZE=${COUCHBOX_IMAGE_SIZE:-9G}
step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
cleanup() {
  set +e
  for m in boot/firmware dev/pts dev proc sys run; do mountpoint -q "$R/$m" && umount -l "$R/$m"; done
  mountpoint -q "$R" && umount -l "$R"
  [[ -n ${LOOP:-} ]] && losetup -d "$LOOP"
  rm -rf "$W"
}
trap cleanup EXIT
[[ $EUID -eq 0 ]] || { echo "run as root"; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo "build on arm64"; exit 1; }
ls "$DEBS"/couchbox_*.deb >/dev/null
for t in xz losetup parted e2fsck resize2fs rsync cryptsetup curl; do command -v $t >/dev/null || NEED=1; done
[[ -z ${NEED:-} ]] || apt-get install -y -qq xz-utils parted e2fsprogs rsync cryptsetup-bin curl >/dev/null
for i in $(seq 0 31); do [[ -e /dev/loop$i ]] || mknod -m 660 "/dev/loop$i" b 7 "$i"; done

step "Base: $(basename "$BASE_URL")"
mkdir -p "$CACHE" "$OUT"
base=$CACHE/$(basename "$BASE_URL")
if [[ ! -f $base ]] || ! echo "$BASE_SHA256  $base" | sha256sum -c --quiet; then
  curl -fL --retry 3 -o "$base.part" "$BASE_URL" && mv "$base.part" "$base"
  echo "$BASE_SHA256  $base" | sha256sum -c --quiet || { echo "!! base image checksum mismatch"; exit 1; }
fi
img=$W/couchbox.img
xz -dc -T0 "$base" > "$img"
truncate -s "$SIZE" "$img"
parted -s "$img" resizepart 2 100%
LOOP=$(losetup -f -P --show "$img")
partprobe "$LOOP" 2>/dev/null || true
BOOT=${LOOP}p1 ROOTP=${LOOP}p2
e2fsck -fy "$ROOTP" >/dev/null || [[ $? -le 1 ]]
resize2fs "$ROOTP" >/dev/null

step "Chroot"
mkdir -p "$R"
mount "$ROOTP" "$R"
mkdir -p "$R/boot/firmware"         # systemd makes mount points at boot; the image may not have it
mount "$BOOT" "$R/boot/firmware"
for m in dev dev/pts proc sys run; do mount --bind "/$m" "$R/$m"; done
cp --remove-destination /etc/resolv.conf "$R/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"; chmod 755 "$R/usr/sbin/policy-rc.d"
mkdir -p "$R/tmp/debs" && cp "$DEBS"/*.deb "$R/tmp/debs/"
in_root() { chroot "$R" env DEBIAN_FRONTEND=noninteractive COUCHBOX_IMAGE_BUILD=1 LANG=C.UTF-8 "$@"; }

step "Packages: upgrade, drop snapd, add Tailscale's repo, install Couchbox"
in_root apt-get -qq update
in_root apt-get -y -qq -o Dpkg::Options::=--force-confold full-upgrade >/dev/null
in_root apt-get -y -qq purge snapd lxd-installer 2>/dev/null || true
rm -rf "$R/var/lib/snapd" "$R/snap" "$R/var/snap"
codename=$(. "$R/etc/os-release" && echo "$VERSION_CODENAME")
tsc=$codename
curl -fsI "https://pkgs.tailscale.com/stable/ubuntu/$tsc.noarmor.gpg" >/dev/null || tsc=resolute
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$tsc.noarmor.gpg" > "$R/usr/share/keyrings/tailscale-archive-keyring.gpg"
curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$tsc.tailscale-keyring.list" > "$R/etc/apt/sources.list.d/tailscale.list"
in_root apt-get -qq update
in_root sh -c 'apt-get install -y -qq --no-install-recommends /tmp/debs/*.deb tailscale openssh-server rpi-eeprom raspi-utils-core >/dev/null'
in_root systemctl disable tailscaled.service ssh.service ssh.socket 2>/dev/null || true
echo "$VERSION" > "$R/etc/couchbox/image-version"

step "First boot: cloud-init only for Raspberry Pi Imager's settings, no default user"
cat > "$R/etc/cloud/cloud.cfg.d/90-couchbox.cfg" <<'X'
# Couchbox: no default "ubuntu" user (Imager can still add one); NetworkManager renders Wi-Fi.
users: []
X
rm -f "$R/etc/cloud/cloud.cfg.d/99-couchbox-no-network.cfg"
cp "$HERE/couchbox.toml.example" "$R/boot/firmware/couchbox.toml.example"

step "Clean up"
in_root apt-get -y -qq autoremove --purge >/dev/null
in_root apt-get -qq clean
rm -rf "$R"/var/lib/apt/lists/* "$R/tmp/debs" "$R/usr/sbin/policy-rc.d" "$R"/etc/ssh/ssh_host_* "$R"/var/log/*.log "$R/root/.bash_history"
: > "$R/etc/machine-id"; rm -f "$R/var/lib/dbus/machine-id"
ln -sf ../run/systemd/resolve/stub-resolv.conf "$R/etc/resolv.conf"
du -sh "$R" | sed 's/^/root filesystem: /'

step "Shrink"
for m in boot/firmware dev/pts dev proc sys run; do umount -l "$R/$m"; done
umount "$R"
e2fsck -fy "$ROOTP" >/dev/null || [[ $? -le 1 ]]
resize2fs -M "$ROOTP" >/dev/null
blocks=$(dumpe2fs -h "$ROOTP" 2>/dev/null | awk -F': *' '/^Block count/ {print $2}')
bs=$(dumpe2fs -h "$ROOTP" 2>/dev/null | awk -F': *' '/^Block size/ {print $2}')
start=$(parted -sm "$img" unit B print | awk -F: '$1 == 2 {sub("B", "", $2); print $2}')
end=$(( start + blocks * bs + 64 * 1024 * 1024 ))     # some slack; first boot grows it to the disk
losetup -d "$LOOP"; LOOP=
parted -s "$img" unit B resizepart 2 "$((end - 1))" 2>/dev/null || echo yes | parted ---pretend-input-tty "$img" unit B resizepart 2 "$((end - 1))"
truncate -s "$end" "$img"

step "Compress"
name=couchbox-$VERSION-rpi5.img
mv "$img" "$OUT/$name"
( cd "$OUT" && sha256sum "$name" | awk '{print $1}' > "$name.extract.sha256" && stat -c %s "$name" > "$name.extract.size" )
xz -T0 -9 -f "$OUT/$name"
( cd "$OUT" && sha256sum "$name.xz" > "$name.xz.sha256" )
ls -la "$OUT"
size=$(stat -c %s "$OUT/$name.xz")
(( size < 2000000000 )) || { echo "!! $name.xz is $size bytes: over GitHub's 2 GB release asset limit"; exit 1; }
