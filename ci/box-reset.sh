#!/bin/bash
# Put a dev box back to a first start, so the setup can be tested again (docs/dev-box.md).
#
#   ci/box-reset.sh HOST --quick [--keep-remote]
#     Clears the setup's progress, paired remotes and saved Wi-Fi, then restarts the box:
#     the setup opens again in about two minutes. The system, its apps and SSH stay as they are.
#     --keep-remote keeps the paired remote (no need to pair it again for every rerun).
#
#   ci/box-reset.sh HOST --image VERSION|latest [--preseed FILE] [--keys FILE] [--no-ethernet MINUTES]
#     A real first start, as on a new box: writes that release's image onto the USB stick in the
#     box, erases the SSD, and restarts. The box starts from the stick and the setup begins from
#     Hello (Install to SSD included). Everything on the SSD is lost.
#     --preseed FILE        a couchbox.toml for the stick's boot partition. To reach the box again
#                           over SSH it needs `[ssh] github_user` (SSH is off on a new box), and over
#                           Tailscale a `[tailscale] auth_key` (the box is a new device there).
#     --keys FILE           public keys for the admin account on the stick (authorized_keys)
#     --no-ethernet MINUTES keep Ethernet off from the first start until the setup is done, or for
#                           MINUTES at most, so the setup has to get online over Wi-Fi. Ethernet then
#                           comes back by itself: the way back in if the Wi-Fi part fails.
#
# HOST is anything `ssh HOST` reaches, logged in as an account with passwordless sudo (admin).
set -euo pipefail
usage() {
  echo "usage: $0 HOST --quick [--keep-remote]" >&2
  echo "       $0 HOST --image VERSION|latest [--preseed FILE] [--keys FILE] [--no-ethernet MINUTES]" >&2
  exit 2
}
[[ $# -ge 2 && $1 != -* ]] || usage
HOST=$1
shift
MODE="" KEEP_REMOTE=0 VERSION="" PRESEED="" KEYS="" NOETH=0
while [[ $# -gt 0 ]]; do
  case $1 in
    --quick) MODE=quick ;;
    --keep-remote) KEEP_REMOTE=1 ;;
    --image) MODE=image VERSION=${2:?}; shift ;;
    --preseed) PRESEED=${2:?}; shift ;;
    --keys) KEYS=${2:?}; shift ;;
    --no-ethernet) NOETH=${2:?}; shift ;;
    *) usage ;;
  esac
  shift
done
[[ -n $MODE ]] || usage

if [[ $MODE == quick ]]; then
  # shellcheck disable=SC2016  # expanded on the box
  ssh "$HOST" sudo KEEP_REMOTE=$KEEP_REMOTE bash -s <<'BOX'
set -euo pipefail
systemctl stop couchboxd.service
rm -f /var/lib/couchbox/state/setup.json
[ "$KEEP_REMOTE" = 1 ] || for d in $(bluetoothctl devices Paired | awk '{print $2}'); do bluetoothctl remove "$d" >/dev/null && echo "forgot remote $d"; done
nmcli -t -f NAME,TYPE connection show | awk -F: '$2 == "802-11-wireless" {print $1}' | while read -r c; do
  nmcli connection delete id "$c" >/dev/null && echo "forgot Wi-Fi $c"
done
systemd-run --on-active=2 --quiet systemctl reboot
BOX
  echo "restarting $HOST"
  sleep 30
  for _ in $(seq 60); do
    if ssh -o ConnectTimeout=10 -o BatchMode=yes "$HOST" 'pgrep -f "[p]ython3 /usr/lib/couchbox/bin/couchbox-setup"' >/dev/null 2>&1; then
      echo "setup reset: $HOST shows the setup again"
      exit 0
    fi
    sleep 10
  done
  echo "$HOST: no setup after 10 minutes" >&2
  exit 1
fi

# --image: the release, checked against its published checksum, then onto the stick
if [[ $VERSION == latest ]]; then
  VERSION=$(curl -fsSL https://api.github.com/repos/Supermaxman/couchbox/releases/latest | jq -r .tag_name)
fi
VERSION=${VERSION#v}
ssh "$HOST" "sudo install -d -m 700 /run/couchbox-reset"
[[ -z $PRESEED ]] || ssh "$HOST" 'sudo sh -c "umask 077; cat > /run/couchbox-reset/couchbox.toml"' <"$PRESEED"
[[ -z $KEYS ]] || ssh "$HOST" 'sudo sh -c "umask 077; cat > /run/couchbox-reset/authorized_keys"' <"$KEYS"
# shellcheck disable=SC2016  # expanded on the box
ssh "$HOST" sudo bash -s -- "$VERSION" "$NOETH" <<'BOX'
set -euo pipefail
v=$1 noeth=$2
root=$(lsblk -n -o PKNAME "$(findmnt -n -o SOURCE /)")
stick=$(lsblk -d -n -o NAME,TRAN | awk -v r="$root" '$2 == "usb" && $1 != r {print $1}')
[ "$(echo "$stick" | grep -c .)" = 1 ] || { echo "need exactly one USB stick in the box (found: ${stick:-none})" >&2; exit 1; }
ssd=$(lsblk -d -n -o NAME,TRAN | awk -v r="$root" '$2 == "nvme" && $1 == r {print $1}')
[ -n "$ssd" ] || { echo "the box isn't running from an NVMe SSD; nothing to erase" >&2; exit 1; }
size=$(lsblk -d -n -b -o SIZE "/dev/$stick")
[ "$size" -ge 8000000000 ] || { echo "/dev/$stick is under 8 GB" >&2; exit 1; }
echo "stick /dev/$stick ($(lsblk -d -n -o MODEL "/dev/$stick" | xargs), $((size / 1000000000)) GB); SSD /dev/$ssd"
d=/var/tmp/couchbox-reset
mkdir -p "$d"
cd "$d"
img=couchbox-$v-rpi5.img.xz
base=https://github.com/Supermaxman/couchbox/releases/download/v$v
[ -f "$img" ] || curl -fsSL -o "$img" "$base/$img"
curl -fsSL -o "$img.sha256" "$base/$img.sha256"
sha256sum -c "$img.sha256"
for p in $(lsblk -n -o NAME "/dev/$stick" | tail -n +2); do umount "/dev/$p" 2>/dev/null || true; done
echo "writing $img to /dev/$stick"
xz -dc "$img" | dd of="/dev/$stick" bs=4M conv=fsync iflag=fullblock status=none
partprobe "/dev/$stick"
sleep 2
m=$(mktemp -d)
mount "/dev/${stick}1" "$m"
[ ! -f /run/couchbox-reset/couchbox.toml ] || install -m 600 /run/couchbox-reset/couchbox.toml "$m/couchbox.toml"
umount "$m"
mount "/dev/${stick}2" "$m"
if [ -f /run/couchbox-reset/authorized_keys ]; then
  read -r u g h < <(awk -F: '$1 == "admin" {print $3, $4, $6}' "$m/etc/passwd")
  install -d -m 700 -o "$u" -g "$g" "$m$h/.ssh"
  install -m 600 -o "$u" -g "$g" /run/couchbox-reset/authorized_keys "$m$h/.ssh/authorized_keys"
fi
if [ "$noeth" -gt 0 ]; then
  # test only: Ethernet off until the setup is done (or noeth minutes), then on again, once
  cat >"$m/usr/local/sbin/couchbox-test-noeth" <<SH
#!/bin/sh
nmcli device set eth0 managed no 2>/dev/null; ip link set eth0 down
for i in \$(seq $((noeth * 6))); do
  grep -qs '"done": true' /var/lib/couchbox/state/setup.json && break
  sleep 10
done
ip link set eth0 up; nmcli device set eth0 managed yes
systemctl disable couchbox-test-noeth.service
SH
  chmod 755 "$m/usr/local/sbin/couchbox-test-noeth"
  printf '[Unit]\nDescription=Test only: no Ethernet until the setup is done\nAfter=NetworkManager.service\n\n[Service]\nType=simple\nExecStart=/usr/local/sbin/couchbox-test-noeth\n\n[Install]\nWantedBy=multi-user.target\n' \
    >"$m/etc/systemd/system/couchbox-test-noeth.service"
  ln -sf /etc/systemd/system/couchbox-test-noeth.service "$m/etc/systemd/system/multi-user.target.wants/couchbox-test-noeth.service"
fi
umount "$m"
rmdir "$m"
rm -rf /run/couchbox-reset
sync
echo "erasing the SSD /dev/$ssd: the next start is from the stick"
wipefs -a -q "/dev/${ssd}p1" "/dev/${ssd}p2" || true
wipefs -a -q "/dev/$ssd"
systemd-run --on-active=2 --quiet systemctl reboot --force
BOX
echo "$HOST is restarting from the stick (v$VERSION). The setup opens on the TV in 3-4 minutes."
echo "It's a new device on the network and on Tailscale: reach it by the name in the preseed."
