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
git -C external/mpvqt checkout -q -- src/mpvrenderer.cpp
# (MpvQt: the copy bundled with this release; Ubuntu's newer one changed its API.)
# mpv's "auto" skips the Pi's drm hwdec, so name it first. Copy mode (the default) converts
# the decoder's SAND frames to normal ones; Enabled hands them to the GPU directly.
perl -0pi -e 's/(== "enabled"\)\s*\n\s*hwdecMode = )"auto";/$1"drm,auto";/;
              s/hwdecMode = "auto-copy";/hwdecMode = "drm-copy,auto-copy";/' src/player/PlayerComponent.cpp
grep -q '"drm-copy,auto-copy"' src/player/PlayerComponent.cpp && grep -q '"drm,auto"' src/player/PlayerComponent.cpp \
  || { echo "hwdec patch did not apply"; exit 1; }
# libmpv 0.41's OpenGL render API makes a GL fence at the end of every frame and keeps it for
# a buffer swap that only its own windows do (fixed upstream after 0.41), so it never deletes
# it. On the Pi each fence holds a file descriptor (a sync_file): Jellyfin used about 23 a
# second and crashed at the open-file limit ("MESA: error: Export failed", then SEGV) every
# ~6 minutes of video. Same fix as Couchbox's own player (src/couchbox/player.py): MpvQt's
# get_proc_address hands mpv a glFenceSync that notes the newest fence, and after each frame
# the renderer deletes the frame's last one, the end-of-frame fence (mpv makes it last).
python3 - external/mpvqt/src/mpvrenderer.cpp <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
helpers = """// Couchbox: delete libmpv 0.41's leaked end-of-frame GL fence (see build-jellyfin.sh).
typedef void *(*couchbox_fence_fn)(unsigned int, unsigned int);
typedef void (*couchbox_delete_fn)(void *);
static couchbox_fence_fn couchbox_real_fence = nullptr;
static couchbox_delete_fn couchbox_real_delete = nullptr;
static void *couchbox_last_fence = nullptr;

static void *couchbox_fence_sync(unsigned int condition, unsigned int flags)
{
    void *fence = couchbox_real_fence(condition, flags);
    couchbox_last_fence = fence;
    return fence;
}

static void *get_proc_address_mpv(void *ctx, const char *name)"""
edits = [
    ("static void *get_proc_address_mpv(void *ctx, const char *name)", helpers),
    ("    return reinterpret_cast<void *>(glctx->getProcAddress(QByteArray(name)));",
     """    void *addr = reinterpret_cast<void *>(glctx->getProcAddress(QByteArray(name)));
    if (addr && qstrcmp(name, "glFenceSync") == 0) {
        couchbox_real_fence = reinterpret_cast<couchbox_fence_fn>(addr);
        return reinterpret_cast<void *>(&couchbox_fence_sync);
    }
    if (addr && qstrcmp(name, "glDeleteSync") == 0) {
        couchbox_real_delete = reinterpret_cast<couchbox_delete_fn>(addr);
    }
    return addr;"""),
    ("    mpv_render_context_render(m_mpvAItem->d_ptr->m_mpv_gl, params);",
     """    couchbox_last_fence = nullptr;
    mpv_render_context_render(m_mpvAItem->d_ptr->m_mpv_gl, params);
    if (couchbox_last_fence && couchbox_real_delete) {
        couchbox_real_delete(couchbox_last_fence);
    }
    couchbox_last_fence = nullptr;"""),
]
for a, b in edits:
    if s.count(a) != 1:
        sys.exit("mpvrenderer fence patch did not apply: " + a.strip()[:60])
    s = s.replace(a, b)
open(p, "w").write(s)
PY
grep -q "couchbox_real_delete(couchbox_last_fence)" external/mpvqt/src/mpvrenderer.cpp || { echo "fence patch did not apply"; exit 1; }
# Qt 6.11 no longer converts the plain JS object webview.qml assigns to userScripts.collection,
# so the native shell (NativeShell, mpv player plugin) was never injected and the web client
# used its HTML5 player. Build the script with the documented WebEngine.script() instead.
perl -0pi -e 's/var nativeshell =\s*\{\s*sourceCode: (components\.system\.getNativeShellScript\(\)),\s*injectionPoint: (WebEngineScript\.DocumentCreation),\s*worldId: (WebEngineScript\.MainWorld)\s*\}\s*web\.userScripts\.collection = \[ nativeshell \];/var nativeshell = WebEngine.script();\n      nativeshell.name = "nativeshell";\n      nativeshell.sourceCode = $1;\n      nativeshell.injectionPoint = $2;\n      nativeshell.worldId = $3;\n      web.profile.userScripts.insert(nativeshell);/' src/ui/webview.qml
grep -q "web.profile.userScripts.insert(nativeshell)" src/ui/webview.qml || { echo "webview.qml patch did not apply"; exit 1; }
# The web client draws over the video with a transparent background. When the start page hands
# over to the server, Chromium swaps in a new renderer, and that one sometimes keeps Chromium's
# default white background though Qt still reports transparent: the video plays unseen under
# white (on the Pi 5, measured: 6 of 23 starts, and every start for an evening). Set the
# background again after each page load and whenever a video starts. Chromium accepts only an
# opaque or a fully transparent background (anything else aborts), so the value in between is
# transparent white.
python3 - src/ui/webview.qml <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
edits = [
    ("    onLoadingChanged: function(loadingInfo)",
     """    // Couchbox: the transparent background again (see build-jellyfin.sh)
    function couchboxTransparent() {
      web.backgroundColor = Qt.rgba(1, 1, 1, 0)
      web.backgroundColor = "transparent"
    }

    onLoadingChanged: function(loadingInfo)"""),
    ("""        console.log("WebEngineLoadRequest success: " + loadingInfo.url);""",
     """        console.log("WebEngineLoadRequest success: " + loadingInfo.url);
        web.couchboxTransparent()"""),
    ("  Text\n  {\n    id: errorLabel",
     """  Connections
  {
    target: components.player
    function onVideoPlaybackActive(active) { if (active) web.couchboxTransparent() }
  }

  Text
  {
    id: errorLabel"""),
]
for a, b in edits:
    if s.count(a) != 1:
        sys.exit("webview.qml background patch did not apply: " + a.strip()[:60])
    s = s.replace(a, b)
open(p, "w").write(s)
PY
grep -q "function onVideoPlaybackActive" src/ui/webview.qml || { echo "background patch did not apply"; exit 1; }
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
