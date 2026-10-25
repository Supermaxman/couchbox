#!/bin/bash
# CI (root): the disk-encryption steps couchbox.encryption uses, on a loop device:
#   LUKS2 with the image's shared key -> online re-encryption to a new volume key while
#   files are being written -> interrupted and resumed -> passphrase in, image key out
# and plan B: encrypting a plain ext4 partition in place (offline), as from the initrd.
set -euo pipefail
W=$(mktemp -d); trap 'cleanup' EXIT
cleanup() {
  set +e
  [[ -n ${WRITER:-} ]] && kill "$WRITER" 2>/dev/null
  mountpoint -q "$W/mnt" && umount "$W/mnt"
  cryptsetup close cbtest 2>/dev/null
  [[ -n ${LOOP:-} ]] && losetup -d "$LOOP"
  rm -rf "$W"
}
# containers start without loop device nodes
for i in $(seq 0 31); do [[ -e /dev/loop$i ]] || mknod -m 660 "/dev/loop$i" b 7 "$i" 2>/dev/null || true; done
FAST=(--pbkdf pbkdf2 --pbkdf-force-iterations 1000)   # quick on CI; the box uses argon2id
ok() { printf '\033[32mok\033[0m %s\n' "$*"; }

echo "== online re-encryption"
truncate -s 400M "$W/disk.img"
LOOP=$(losetup -f --show "$W/disk.img")
head -c 64 /dev/urandom > "$W/image.key"
cryptsetup luksFormat --batch-mode --type luks2 "${FAST[@]}" --key-file "$W/image.key" "$LOOP"
cryptsetup open --key-file "$W/image.key" "$LOOP" cbtest
mkfs.ext4 -q /dev/mapper/cbtest
mkdir "$W/mnt" && mount /dev/mapper/cbtest "$W/mnt"
for i in $(seq 1 40); do head -c 2M /dev/urandom > "$W/mnt/f$i"; done
( i=0; while true; do i=$((i + 1)); head -c 256K /dev/urandom > "$W/mnt/w$((i % 50))"; sleep 0.05; done ) &
WRITER=$!
old_key=$(cryptsetup luksDump --dump-volume-key --batch-mode --key-file "$W/image.key" "$LOOP" | awk '/^MK dump|^Volume key/ {f=1; next} f && NF {printf "%s", $0}')
# like couchbox-reencrypt: start, get interrupted (power cut / reboot), resume
timeout -s INT 3 cryptsetup reencrypt --batch-mode --resilience checksum --key-file "$W/image.key" "$LOOP" || true
if cryptsetup luksDump "$LOOP" | grep -q online-reencrypt; then ok "interrupted mid-way"; fi
cryptsetup reencrypt --batch-mode --resume-only --key-file "$W/image.key" "$LOOP" 2>/dev/null \
  || cryptsetup reencrypt --batch-mode --resilience checksum --key-file "$W/image.key" "$LOOP"
! cryptsetup luksDump "$LOOP" | grep -q online-reencrypt
ok "re-encryption finished"
kill "$WRITER"; wait "$WRITER" 2>/dev/null || true; WRITER=
sync
(cd "$W/mnt" && sha256sum f* > "$W/sums")
umount "$W/mnt"; cryptsetup close cbtest
new_key=$(cryptsetup luksDump --dump-volume-key --batch-mode --key-file "$W/image.key" "$LOOP" | awk '/^MK dump|^Volume key/ {f=1; next} f && NF {printf "%s", $0}')
[[ -n $old_key && $old_key != "$new_key" ]]
ok "new volume key"
# finish(): passphrase in (from stdin, no newline, as typed at boot), image key out
printf 'correct horse battery' | cryptsetup luksAddKey --batch-mode "${FAST[@]}" --key-file "$W/image.key" "$LOOP" -
cryptsetup luksRemoveKey --batch-mode "$LOOP" "$W/image.key"
! cryptsetup open --test-passphrase --key-file "$W/image.key" "$LOOP" 2>/dev/null
printf 'correct horse battery' | cryptsetup open --test-passphrase "$LOOP" --key-file -
ok "passphrase opens it, the image key doesn't"
printf 'correct horse battery' | cryptsetup open --key-file - "$LOOP" cbtest
mount /dev/mapper/cbtest "$W/mnt"
(cd "$W/mnt" && sha256sum -c --quiet "$W/sums")
ok "data intact"
umount "$W/mnt"; cryptsetup close cbtest; losetup -d "$LOOP"; LOOP=

echo "== plan B: encrypt a plain ext4 partition in place"
truncate -s 300M "$W/plain.img"
LOOP=$(losetup -f --show "$W/plain.img")
mkfs.ext4 -q "$LOOP"
mount "$LOOP" "$W/mnt"
for i in $(seq 1 20); do head -c 2M /dev/urandom > "$W/mnt/p$i"; done
(cd "$W/mnt" && sha256sum p* > "$W/psums"); umount "$W/mnt"
e2fsck -f -p "$LOOP" || [[ $? -le 1 ]]
blocks=$(dumpe2fs -h "$LOOP" 2>/dev/null | awk -F': *' '/^Block count/ {print $2}')
bs=$(dumpe2fs -h "$LOOP" 2>/dev/null | awk -F': *' '/^Block size/ {print $2}')
resize2fs "$LOOP" "$(( blocks * bs / 1024 - 65536 ))K" >/dev/null
cryptsetup reencrypt --batch-mode --encrypt --type luks2 "${FAST[@]}" --reduce-device-size 32M --key-file "$W/image.key" "$LOOP"
cryptsetup open --key-file "$W/image.key" "$LOOP" cbtest
e2fsck -f -p /dev/mapper/cbtest || [[ $? -le 1 ]]
resize2fs /dev/mapper/cbtest >/dev/null
mount /dev/mapper/cbtest "$W/mnt"
(cd "$W/mnt" && sha256sum -c --quiet "$W/psums")
ok "encrypted in place, data intact"
echo "encryption: all good"
