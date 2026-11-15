#!/bin/bash
# Put a dev box back to a first start, so the setup can be tested again (docs/dev-box.md).
#   ci/box-reset.sh HOST --quick [--keep-remote]
#     Clears the setup's progress, paired remotes and saved Wi-Fi, then restarts the box:
#     the setup opens again in about two minutes. The system, its apps and SSH stay as they are.
#     --keep-remote keeps the paired remote (no need to pair it again for every rerun).
# HOST is anything `ssh HOST` reaches, logged in as an account with passwordless sudo (admin).
set -euo pipefail
[[ $# -ge 2 && $1 != -* ]] || { echo "usage: $0 HOST --quick [--keep-remote]" >&2; exit 2; }
HOST=$1
KEEP_REMOTE=0
for a in "${@:2}"; do
  case $a in
    --quick) ;;
    --keep-remote) KEEP_REMOTE=1 ;;
    *) echo "unknown option $a" >&2; exit 2 ;;
  esac
done
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
