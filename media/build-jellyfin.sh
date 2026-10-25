#!/usr/bin/env bash
# Runs inside an ubuntu:26.10 arm64 container (media.yml, or by hand on any arm64 machine).
# Builds, into /out:
#   jellyfin-desktop.tar.gz  Jellyfin Desktop built natively against Ubuntu's Qt 6 + libmpv,
#                            with "Hardware decoding" trying the Pi decoder (drm) first.
#   jellyfin-deps.txt        Ubuntu packages it needs at run time.
set -euo pipefail
JD_REPO=https://github.com/jellyfin/jellyfin-desktop
JD_TAG=${JD_TAG:-v2.0.0}
JD=/opt/couchbox/jellyfin-desktop
export DEBIAN_FRONTEND=noninteractive

log() { printf '\n=== %s\n' "$*"; }

log "Build dependencies"
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  build-essential ca-certificates git xz-utils pkg-config cmake ninja-build python3 file \
  qt6-base-dev qt6-base-private-dev qt6-declarative-dev qt6-webengine-dev qt6-webchannel-dev \
  qt6-wayland-dev libmpv-dev libcec-dev libsdl2-dev libgl-dev libegl-dev \
  libx11-dev libxrandr-dev >/dev/null

log "Jellyfin Desktop $JD_TAG"
src=/build/jellyfin-desktop
[[ -d $src ]] || git clone -q --depth 1 --branch "$JD_TAG" --recurse-submodules --shallow-submodules "$JD_REPO" "$src"
cd "$src"
git checkout -q -- src/ui/webview.qml src/player/PlayerComponent.cpp native/nativeshell.js   # re-apply patches cleanly
# (MpvQt: the copy bundled with this release; Ubuntu's newer one changed its API.)
# mpv's "auto" skips the Pi's drm hwdec, so name it first. Copy mode (the default) converts
# the decoder's SAND frames to normal ones; Enabled hands them to the GPU directly.
perl -0pi -e 's/(== "enabled"\)\s*\n\s*hwdecMode = )"auto";/$1"drm,auto";/;
              s/hwdecMode = "auto-copy";/hwdecMode = "drm-copy,auto-copy";/' src/player/PlayerComponent.cpp
grep -q '"drm-copy,auto-copy"' src/player/PlayerComponent.cpp && grep -q '"drm,auto"' src/player/PlayerComponent.cpp \
  || { echo "hwdec patch did not apply"; exit 1; }
# Qt 6.11 no longer converts the plain JS object webview.qml assigns to userScripts.collection,
# so the native shell (NativeShell, mpv player plugin) was never injected and the web client
# used its HTML5 player. Build the script with the documented WebEngine.script() instead.
perl -0pi -e 's/var nativeshell =\s*\{\s*sourceCode: (components\.system\.getNativeShellScript\(\)),\s*injectionPoint: (WebEngineScript\.DocumentCreation),\s*worldId: (WebEngineScript\.MainWorld)\s*\}\s*web\.userScripts\.collection = \[ nativeshell \];/var nativeshell = WebEngine.script();\n      nativeshell.name = "nativeshell";\n      nativeshell.sourceCode = $1;\n      nativeshell.injectionPoint = $2;\n      nativeshell.worldId = $3;\n      web.profile.userScripts.insert(nativeshell);/' src/ui/webview.qml
grep -q "web.profile.userScripts.insert(nativeshell)" src/ui/webview.qml || { echo "webview.qml patch did not apply"; exit 1; }
# "Force transcode Hi10P" limits every codec to 8 bit, which also sends 10-bit HEVC and AV1
# (both fine on the Pi) to the server. Limit it to H.264, the one the Pi can't keep up with.
perl -0pi -e "s/(force_transcode_hi10p\) \{\s*CodecProfiles\.push\(\{\s*'Type': 'Video',)/\$1\n            'Codec': 'h264',/" native/nativeshell.js
grep -A4 force_transcode_hi10p native/nativeshell.js | grep -q "'Codec': 'h264'" || { echo "hi10p patch did not apply"; exit 1; }
# "Internet quality" applies to remote servers (e.g. over Tailscale); at 8 Mbps the server
# transcoded anything bigger. When it's unset, start at the maximum.
cat >> native/nativeshell.js <<'JS'

try {
    if (localStorage.getItem('maxbitrate-Video-false') === null) {
        localStorage.setItem('maxbitrate-Video-false', '120000000');
        localStorage.setItem('enableautobitratebitrate-Video-false', 'false');
    }
} catch (e) {}
JS
rm -rf build
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$JD" \
  -DUSE_STATIC_MPVQT=ON -DCHECK_FOR_UPDATES=OFF > /out/jellyfin-cmake.log 2>&1 \
  || { tail -30 /out/jellyfin-cmake.log; exit 1; }
ninja -C build > /out/jellyfin-ninja.log 2>&1 || { grep -B2 -A12 -m3 "error" /out/jellyfin-ninja.log; exit 1; }
ninja -C build install >/dev/null
install -Dm644 resources/images/icon.svg "$JD/share/icons/hicolor/scalable/apps/couchbox-jellyfin.svg"

log "Runtime packages"
deps=$(find "$JD" -type f -exec sh -c 'file -b "$1" | grep -q ELF' _ {} \; -print0 \
  | xargs -0 -r ldd 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $3}' | grep -v '^/opt/couchbox/' | sort -u \
  | xargs -r -n1 sh -c 'dpkg -S "$(readlink -f "$1")" 2>/dev/null || dpkg -S "$1" 2>/dev/null' _ \
  | cut -d: -f1 | sort -u)
printf '%s\n' $deps qml6-module-qtwebengine qml6-module-qtwebchannel qml6-module-qtquick-controls \
  qml6-module-qtquick-window qml6-module-qtqml-workerscript qml6-module-qtquick-templates \
  qml6-module-qtquick-layouts | sort -u > /out/jellyfin-deps.txt
wc -l < /out/jellyfin-deps.txt

log "Packing"
tar -C / -czf /out/jellyfin-desktop.tar.gz "${JD#/}"
(cd "$src" && git ls-files --recurse-submodules | tar -cJf /out/jellyfin-desktop-source.tar.xz --transform "s,^,jellyfin-desktop-$JD_TAG/," -T -)
ls -lh /out
