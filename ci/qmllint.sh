#!/bin/sh
# qmllint on every QML file of our apps (the home screen's are Plasma's types: syntax only).
# Unqualified access is how the apps reach their Python back ends (context properties).
set -eu
Q=/usr/lib/qt6/bin/qmllint
export LANG=C.UTF-8
$Q --unqualified disable --missing-property disable --max-warnings 0 -I ui -I ui/stubs \
  ui/streaming/qml/*.qml ui/seerr/*.qml ui/frigate/*.qml ui/weather/*.qml ui/spotify/*.qml ui/CouchKit/*.qml ui/voice-overlay/*.qml ui/settings/*.qml ui/setup/*.qml
# the home screen, laid over the real Plasma Bigscreen home screen (as couchbox.home does)
S=/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen
if [ -d $S ]; then
  O=$(mktemp -d)
  cp -a $S/. "$O/" && cp -r shell/home/. "$O/contents/ui/"
  printf '.pragma library\nvar data = {"apps": [], "weather": null, "clock24": false};\n' > "$O/contents/ui/couchbox/home-data.js"
  (cd "$O/contents/ui" && $Q --unqualified disable --missing-property disable --max-warnings 0 \
     couchbox/Home.qml couchbox/TileMenu.qml couchbox/AppTile.qml couchbox/HomeData.qml couchbox/Weather.qml HomeHeader.qml)
  rm -rf "$O"
else
  find shell -name '*.qml' -exec $Q --import disable --unresolved-type disable --unqualified disable --missing-property disable --max-warnings 1000 {} + >/dev/null
fi
echo "qmllint: ok"
