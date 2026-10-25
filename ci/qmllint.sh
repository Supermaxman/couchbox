#!/bin/sh
# qmllint on every QML file of our apps (the home screen's are Plasma's types: syntax only).
# Unqualified access is how the apps reach their Python back ends (context properties).
set -eu
Q=/usr/lib/qt6/bin/qmllint
export LANG=C.UTF-8
$Q --unqualified disable --missing-property disable --max-warnings 0 -I ui -I ui/stubs \
  ui/streaming/qml/*.qml ui/seerr/*.qml ui/CouchKit/*.qml ui/voice-overlay/*.qml ui/settings/*.qml ui/setup/*.qml
# the home screen: only syntax (Plasma's modules aren't in the CI image)
find shell -name '*.qml' -exec $Q --import disable --unresolved-type disable --unqualified disable --missing-property disable --max-warnings 1000 {} + >/dev/null
echo "qmllint: ok"
