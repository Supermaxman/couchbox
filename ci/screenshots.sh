#!/bin/sh
# Render every Settings page and the setup wizard off screen (demo mode: a fake system),
# into $1 (default build/shots). Fails on QML errors.
set -eu
OUT=${1:-build/shots}
make -s stage >/dev/null
mkdir -p "$OUT"
export COUCHBOX_SHARE="$PWD/build/share" PYTHONPATH="$PWD/src" QT_QPA_PLATFORM=offscreen LANG=C.UTF-8
fail=0
shot() {  # shot NAME APP ARGS...
  name=$1; app=$2; shift 2
  if ! python3 "bin/$app" --demo --shot "$OUT/$name.png" "$@" >"$OUT/$name.log" 2>&1 || grep -qE "qrc:|file:.*(Error|TypeError|ReferenceError)|is not defined|Cannot assign|Unable to assign" "$OUT/$name.log"; then
    echo "!! $name"; grep -E "Error|error|not defined|Cannot" "$OUT/$name.log" | head -5; fail=1
  else
    echo "ok $name"
  fi
}
for p in network home apps voice remote display time access security updates system; do
  shot "settings-$p" couchbox-settings --page "$p" --in
done
# the Frigate app with made-up cameras: dashboard, a camera full screen (and its strip),
# review, a recording, the timeline (the group's lanes, one camera), sign-in
shot frigate-live couchbox-frigate
shot frigate-camera couchbox-frigate --keys down,ok
shot frigate-camera-strip couchbox-frigate --keys down,ok,down
shot frigate-review couchbox-frigate --open review
shot frigate-recording couchbox-frigate --open review --keys right,ok
shot frigate-timeline couchbox-frigate --open timeline
shot frigate-timeline-camera couchbox-frigate --open timeline:driveway
shot frigate-signin couchbox-frigate --signin
[ -f bin/couchbox-setup ] && for s in 0 1 2 3 4 5 6 7 8 9 10; do shot "setup-$s" couchbox-setup --step "$s"; done
exit $fail
