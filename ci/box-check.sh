#!/bin/bash
# Run ci/yt-box-check.py on a box, but only if nobody's using it; muted throughout; results pulled to $OUT.
#   ci/box-check.sh HOST [yt-box-check.py arguments...]
# HOST is anything `ssh HOST` reaches, logged in as an account with passwordless sudo (admin).
# Refuses (exit 3) unless: the remote is idle >= 10 min, the front window is the home screen or
# couchbox-yt, no audio is playing, and no Frigate pop-up is showing. FORCE=1 skips the idle check.
set -uo pipefail
[[ $# -ge 1 && $1 != -* ]] || { echo "usage: $0 HOST [yt-box-check.py arguments...]" >&2; exit 2; }
HOST=$1
shift
OUT=${OUT:-$(dirname "$0")/../build/box-check/$HOST-$(date +%Y%m%d-%H%M%S)}
scp -q "$(dirname "$0")/yt-box-check.py" "$HOST:/tmp/yt-box-check.py" || exit
ssh "$HOST" FORCE="${FORCE:-0}" bash -s -- "$@" <<'REMOTE'
u=$(id -u tv)
E="env XDG_RUNTIME_DIR=/run/user/$u DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$u/bus WAYLAND_DISPLAY=wayland-0"
age=$(( $(date +%s) - $(stat -c %Y /run/couchbox/last-key 2>/dev/null || echo 0) ))
front=$(sudo -u tv $E /usr/lib/couchbox/bin/couchbox-active-window)
streams=$(sudo -u tv $E pactl list sink-inputs | grep -c 'Corked: no')
[ "$FORCE" = 1 ] || [ "$age" -ge 600 ] || { echo "REFUSED: remote used ${age}s ago"; exit 3; }
case "$front" in *'"shell":true'*|*couchbox-yt*) ;; *) echo "REFUSED: front window $front"; exit 3;; esac
pgrep -u tv -f '[c]ouchbox-yt' >/dev/null || [ "$streams" -eq 0 ] || { echo "REFUSED: $streams audio stream(s) playing"; exit 3; }
sudo test -e "/run/user/$u/couchbox/frigate-popup.shown" && { echo "REFUSED: Frigate pop-up showing"; exit 3; }
mkdir -p /tmp/ytwrap
sudo tee /tmp/ytwrap/couchbox-screenshot >/dev/null <<"W"
#!/bin/bash
# the packaged screenshot tool (KWin authorizes its own python link); it saves as tv, so via a temp file
out="${@: -1}"; t=$(mktemp /tmp/ytshot.XXXXXX.png); chmod 666 "$t"
/usr/lib/couchbox/bin/couchbox-screenshot "${@:1:$#-1}" "$t" >/dev/null && cp "$t" "$out"; rm -f "$t"
W
sudo chmod +x /tmp/ytwrap/couchbox-screenshot; sudo ln -sf /usr/lib/couchbox/bin/couchbox-remote /tmp/ytwrap/couchbox-remote
was=0; sudo -u tv $E wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -q MUTED && was=1
sudo -u tv $E wpctl set-mute @DEFAULT_AUDIO_SINK@ 1
trap 'sudo -u tv $E wpctl set-mute @DEFAULT_AUDIO_SINK@ $was' EXIT
sudo rm -rf /tmp/yt-check
flock -w 600 /tmp/cbtv.lock sudo env PATH=/tmp/ytwrap:$PATH /usr/bin/python3 /tmp/yt-box-check.py "$@"
rc=$?; sudo chmod -R a+rX /tmp/yt-check; cat /var/lib/couchbox/state/yt-dev 2>/dev/null; exit $rc
REMOTE
rc=$?
[ $rc -eq 3 ] && exit 3
mkdir -p "$OUT" && scp -q "$HOST:/tmp/yt-check/*" "$OUT/" && echo "results in $OUT"
exit $rc
