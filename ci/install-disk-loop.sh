#!/bin/bash
# CI (root): "Install to the SSD" for real, on loop devices. A source laid out like the
# image (FAT system-boot + ext4 writable, LABEL= in fstab and cmdline.txt) is copied by
# couchbox.install_disk.copy onto an empty "SSD"; the copy must boot by PARTUUID.
set -euo pipefail
W=$(mktemp -d); trap 'cleanup' EXIT
cleanup() {
  set +e
  [[ -n ${NODES:-} ]] && kill "$NODES" 2>/dev/null
  umount -R "$W/src" 2>/dev/null; umount -R "$W/chk" 2>/dev/null
  [[ -n ${SRC:-} ]] && losetup -d "$SRC"
  [[ -n ${DST:-} ]] && losetup -d "$DST"
  rm -rf "$W"
}
ok() { printf '\033[32mok\033[0m %s\n' "$*"; }
# containers have no udev: make loop and partition device nodes as the kernel adds them
for i in $(seq 0 31); do [[ -e /dev/loop$i ]] || mknod -m 660 "/dev/loop$i" b 7 "$i" 2>/dev/null || true; done
( while :; do
    for d in /sys/block/loop*/loop*p*; do
      [[ -e $d/dev ]] || continue
      n=/dev/$(basename "$d"); want=$(cat "$d/dev")
      [[ -b $n && $(stat -c '%Hr:%Lr' "$n") == "$want" ]] && continue
      rm -f "$n"; mknod -m 660 "$n" b ${want%:*} ${want#*:} 2>/dev/null || true
    done
    sleep 0.2
  done ) &
NODES=$!
# a partition is there when the kernel has it and the node matches (privileged containers
# start with stale nodes copied from the host)
waitdev() {
  local s
  s=/sys/block/$(basename "${1%p[0-9]*}")/$(basename "$1")/dev
  for _ in $(seq 50); do
    [[ -e $s && -b $1 && $(stat -c '%Hr:%Lr' "$1") == "$(cat "$s")" ]] && return 0; sleep 0.2
  done
  echo "no $1"; return 1
}

echo "== a source like the image"
truncate -s 1G "$W/src.img"
SRC=$(losetup -fP --show "$W/src.img")
sfdisk --quiet "$SRC" <<< $'label: dos\n,128MiB,c,*\n,,83'
blockdev --rereadpt "$SRC" 2>/dev/null || partx -u "$SRC" 2>/dev/null || true
waitdev "${SRC}p2"
mkfs.vfat -F 32 -n system-boot "${SRC}p1" >/dev/null
mkfs.ext4 -q -L writable "${SRC}p2"
mkdir -p "$W/src" && mount "${SRC}p2" "$W/src"
mkdir -p "$W/src/boot/firmware" "$W/src/etc" "$W/src/var/lib/couchbox/state" "$W/src/home/tv"
mount "${SRC}p1" "$W/src/boot/firmware"
printf 'LABEL=writable\t/\text4\tdiscard,errors=remount-ro\t0\t1\nLABEL=system-boot\t/boot/firmware\tvfat\tdefaults\t0\t1\n/swapfile none swap sw 0 0\n' > "$W/src/etc/fstab"
mkdir -p "$W/src/boot/firmware/current"
echo "console=tty1 root=LABEL=writable rootfstype=ext4 rootwait quiet" | tee "$W/src/boot/firmware/cmdline.txt" > "$W/src/boot/firmware/current/cmdline.txt"
echo kernel > "$W/src/boot/firmware/vmlinuz"
for i in $(seq 1 30); do head -c 1M /dev/urandom > "$W/src/home/tv/f$i"; done
ln -s f1 "$W/src/home/tv/link"; ln "$W/src/home/tv/f2" "$W/src/home/tv/hard"
chown 1000:1000 "$W/src/home/tv/f3"; chmod 640 "$W/src/home/tv/f3"
echo '{"step": 3}' > "$W/src/var/lib/couchbox/state/setup.json"
truncate -s 64M "$W/src/swapfile"

echo "== copy to an empty SSD"
truncate -s 3G "$W/ssd.img"
DST=$(losetup -fP --show "$W/ssd.img")
PYTHONPATH=src python3 -c "
import sys
from couchbox import install_disk
install_disk.copy(sys.argv[1], lambda s: print(s.get('step'), s.get('percent')), source=sys.argv[2])
" "$DST" "$W/src"
partx -u "$DST" 2>/dev/null || true
waitdev "${DST}p2"

echo "== check"
root_uuid=$(blkid -s PARTUUID -o value "${DST}p2"); boot_uuid=$(blkid -s PARTUUID -o value "${DST}p1")
[[ $(blkid -s LABEL -o value "${DST}p1") == system-boot && $(blkid -s TYPE -o value "${DST}p1") == vfat ]]
[[ $(blkid -s LABEL -o value "${DST}p2") == writable && $(blkid -s TYPE -o value "${DST}p2") == ext4 ]]
ok "partitions: FAT system-boot, ext4 writable"
mkdir -p "$W/chk" && mount "${DST}p2" "$W/chk" && mount "${DST}p1" "$W/chk/boot/firmware"
grep -qP "^PARTUUID=$root_uuid\t/\t" "$W/chk/etc/fstab"
grep -qP "^PARTUUID=$boot_uuid\t/boot/firmware\t" "$W/chk/etc/fstab"
grep -q "^/swapfile " "$W/chk/etc/fstab"
ok "fstab by PARTUUID"
for c in cmdline.txt current/cmdline.txt; do grep -q "root=PARTUUID=$root_uuid rootfstype" "$W/chk/boot/firmware/$c"; done
grep -q kernel "$W/chk/boot/firmware/vmlinuz"
ok "boot files copied, cmdline.txt by PARTUUID"
diff -r --no-dereference "$W/src/home" "$W/chk/home"
[[ $(readlink "$W/chk/home/tv/link") == f1 ]]
[[ $(stat -c %i "$W/chk/home/tv/f2") == $(stat -c %i "$W/chk/home/tv/hard") ]]
[[ $(stat -c %u:%a "$W/chk/home/tv/f3") == 1000:640 ]]
[[ -f $W/chk/var/lib/couchbox/state/setup.json && -f $W/chk/var/lib/couchbox/state/installed-from.json ]]
ok "files, links, owners and the setup progress copied"
[[ $(stat -c %s "$W/chk/swapfile") -eq $((2 * 1024 ** 3)) ]] && [[ $(stat -c %a "$W/chk/swapfile") == 600 ]]
ok "a fresh swap file"
echo "install-to-disk: all good"
