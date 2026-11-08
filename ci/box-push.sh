#!/bin/bash
# Dev loop: copy a checkout's YouTube app (and the shared Python and CouchKit) straight onto a dev box.
#   ci/box-push.sh HOST [CHECKOUT]
# HOST is anything `ssh HOST` reaches, logged in as an account with passwordless sudo (admin).
# No package and no release: the next update overwrites all of it, and `dpkg --verify couchbox`
# lists these files until then. Keep the box's updates on Manual (docs/dev-box.md).
set -euo pipefail
[[ $# -ge 1 && $1 != -* ]] || { echo "usage: $0 HOST [CHECKOUT]" >&2; exit 2; }
HOST=$1
cd "${2:-$(dirname "$0")/..}"
R=(rsync -rlt "--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r" --exclude=__pycache__ --exclude='*.pyc' --rsync-path="sudo rsync")
"${R[@]}" src/couchbox/ "$HOST:/usr/lib/python3/dist-packages/couchbox/"
"${R[@]}" --delete ui/youtube/ "$HOST:/usr/share/couchbox/ui/youtube/"
"${R[@]}" --delete ui/CouchKit/ "$HOST:/usr/share/couchbox/ui/CouchKit/"
"${R[@]}" --chmod=F755 bin/couchbox-yt bin/couchbox-yt-cast "$HOST:/usr/lib/couchbox/bin/"
"${R[@]}" system/user/couchbox-yt-cast.service "$HOST:/usr/lib/systemd/user/couchbox-yt-cast.service"
"${R[@]}" data/schema.json "$HOST:/usr/share/couchbox/schema.json"
# shellcheck disable=SC2016  # expanded on the box
ssh "$HOST" 'u=$(id -u tv); sudo -u tv env XDG_RUNTIME_DIR=/run/user/$u DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$u/bus systemctl --user daemon-reload'
c=$(git rev-parse --short HEAD)$(git diff --quiet HEAD || echo +dirty)
ssh "$HOST" "echo '$c $(date -Is)' | sudo tee /var/lib/couchbox/state/yt-dev >/dev/null"
echo "pushed $c to $HOST (a new couchbox-yt launch picks it up)"
