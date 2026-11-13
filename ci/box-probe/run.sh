#!/bin/bash
# On the box: run one Couchbox app muted with the frame probe (probe/), press a scripted set of the
# remote's buttons (keys.py), and collect the logs in $OUT/LABEL (default /tmp/couchbox-probe).
#   run.sh LABEL "APP ARGS..." "KEYS" [ENV=VAL ...]
#   run.sh yt-walk couchbox-yt "gap:0.7 downx6 upx6 rightx8 leftx8"       then: analyze.py $OUT/yt-walk
# Refuses (exit 3) unless the remote has been idle 10 minutes (IDLE=seconds), the home screen is in
# front, nothing plays and no Frigate pop-up shows; stops at once if the real remote is pressed.
# The sound is muted for the run and put back as it was; the app is closed at the end.
# Before the app: PREKEYS="ok wait:8" (pressed first, not measured), SETTLE=seconds (default 4),
# APPCLASS=window-class (when it isn't the command's name), GUARD=1 (stop pressing if the app leaves the
# front), MPRIS=1 (the app takes the remote's media keys, as in real use), REC=fps (a recording too),
# PERF=1 (perf record of the app). ENV=VAL: for the app, e.g. COUCHBOX_FRAME_CLOCK=0,
# QT_LOGGING_RULES=qt.scenegraph.time.renderloop.debug=true (per-frame phases in journal.log).
set -uo pipefail
LABEL="$1"; APP="$2"; KEYS="$3"; shift 3
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${OUT:-/tmp/couchbox-probe}
RUN=/run/user/$(id -u tv); TVHOME=$(getent passwd tv | cut -d: -f6)
E="env XDG_RUNTIME_DIR=$RUN DBUS_SESSION_BUS_ADDRESS=unix:path=$RUN/bus WAYLAND_DISPLAY=wayland-0"
B=/usr/lib/couchbox/bin
exec 9>/tmp/cbtv.lock; flock -w 900 9 || { echo "REFUSED: another test holds the TV"; exit 3; }
age=$(( $(date +%s) - $(stat -c %Y /run/couchbox/last-key) ))
front=$(sudo -u tv $E $B/couchbox-active-window)
streams=$(sudo -u tv $E pactl list sink-inputs | grep -c 'Corked: no')
[ "$age" -ge "${IDLE:-600}" ] || { echo "REFUSED: remote used ${age}s ago"; exit 3; }
case "$front" in *'"shell":true'*) ;; *) echo "REFUSED: front window $front"; exit 3;; esac
[ "$streams" -eq 0 ] || { echo "REFUSED: $streams audio stream(s) playing"; exit 3; }
sudo test -e $RUN/couchbox/frigate-popup.shown && { echo "REFUSED: Frigate pop-up showing"; exit 3; }
D=$OUT/$LABEL; sudo rm -rf "$D"; mkdir -p "$OUT" "$D"; chmod 755 "$OUT"; chmod 777 "$D"
key0=$(stat -c %Y /run/couchbox/last-key)
ytlast=$(sudo -u tv env HOME="$TVHOME" python3 -c 'from couchbox.services import youtube; print(youtube.YouTube(client=youtube.TV_CLIENT).auth.last_profile())' 2>/dev/null)
was=0; sudo -u tv $E wpctl get-volume @DEFAULT_AUDIO_SINK@ | grep -q MUTED && was=1
sudo -u tv $E wpctl set-mute @DEFAULT_AUDIO_SINK@ 1
unit="cbux-$(date +%s)"
cleanup() {
  sudo -u tv $E systemctl --user stop "$unit" 2>/dev/null
  # the YouTube app's "last watched as" profile, as it was (a run as a guest or another profile changes it,
  # and the home screen's Continue watching follows it)
  [ -n "$ytlast" ] && sudo -u tv env HOME="$TVHOME" YTLAST="$ytlast" python3 -c 'import os; from couchbox.services import youtube; youtube.YouTube(client=youtube.TV_CLIENT).auth.set_last_profile(os.environ["YTLAST"])' 2>/dev/null
  sudo -u tv $E wpctl set-mute @DEFAULT_AUDIO_SINK@ $was
  # shellcheck disable=SC2024  # (the log is ours to write: only journalctl runs as the TV user)
  sudo -u tv $E journalctl --user -u "$unit" --no-pager -o short-monotonic > "$D/journal.log" 2>/dev/null
  sudo chmod -R a+rX "$D"
}
trap cleanup EXIT
envs=(--setenv=COUCHBOX_MUTE=1 --setenv=CBPROBE="$D" --setenv=PYTHONPATH="$HERE/probe")
[ -n "${MPRIS:-}" ] || envs+=(--setenv=COUCHBOX_NO_MPRIS=1)   # MPRIS=1: the app takes the remote's media keys, as in real use
for kv in "$@"; do envs+=(--setenv="$kv"); done
# shellcheck disable=SC2086
sudo -u tv $E systemd-run --user --quiet --collect --unit="$unit" "${envs[@]}" -- $B/$APP
cls=${APPCLASS:-${APP%% *}}
for _ in $(seq 80); do sudo -u tv $E $B/couchbox-active-window | grep -q "$cls" && break; sleep 0.25; done
sudo -u tv $E $B/couchbox-active-window | grep -q "$cls" || { echo "FAILED: $cls never came to the front"; exit 4; }
sleep "${SETTLE:-4}"
if [ -n "${PREKEYS:-}" ]; then sudo python3 $HERE/keys.py "$D/pre.csv" "$key0" $PREKEYS || exit 5; fi
if [ -n "${PERF:-}" ]; then
  pid=$(sudo -u tv $E systemctl --user show -p MainPID --value "$unit")
  sudo perf record -F 1999 --call-graph fp -p "$pid" -o "$D/perf.data" >/dev/null 2>"$D/perf.err" &
  perfpid=$!; sleep 1
fi
if [ -n "${REC:-}" ]; then sudo -u tv $E $B/couchbox-record start "$D/rec.mp4" --seconds 120 --fps "${REC}" --width "${RECW:-1280}" >/dev/null 2>&1; sleep 1.5; fi
sudo env EXPECT="${GUARD:+$cls}" python3 $HERE/keys.py "$D/sent.csv" "$key0" $KEYS; rc=$?   # GUARD=1: stop if the app leaves the front
if [ -n "${REC:-}" ]; then sleep 1; sudo -u tv $E $B/couchbox-record stop >/dev/null 2>&1; sudo chmod a+r "$D/rec.mp4" 2>/dev/null; fi
[ $rc -eq 0 ] || echo "STOPPED: keys.py rc=$rc (the remote was used?)"
if [ -n "${PERF:-}" ]; then
  sudo pkill -INT -P $perfpid perf 2>/dev/null; sudo kill -INT $perfpid 2>/dev/null; wait $perfpid 2>/dev/null
  sudo perf report -i "$D/perf.data" --stdio --no-children --sort dso,symbol 2>/dev/null | grep -v "^$" | head -220 > "$D/perf-flat.txt"
  sudo perf report -i "$D/perf.data" --stdio --children --sort symbol -g none 2>/dev/null | grep -v "^$" | head -400 > "$D/perf-incl.txt"
fi
sleep 1
exit $rc
