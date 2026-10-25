#!/usr/bin/env bash
# hevc/build-ffmpeg.sh (on an x86 PC with Docker): cross-compile Raspberry Pi's
# FFmpeg fork for the Pi in a few minutes, and copy it to the Pi's ~/couchbox-build.
#   hevc/build-ffmpeg.sh [ssh host, default couchbox]
# The fork adds the V4L2 request API hwaccel for the Pi 5 HEVC decoder (rpi-hevc-dec). It is
# built from the same FFmpeg version as the Pi's Ubuntu libav*, so it's an ABI drop-in that
# Ubuntu's libmpv loads unchanged (Raspberry Pi OS ships it the same way); couchbox only uses it
# for Jellyfin, through LD_LIBRARY_PATH.
set -euo pipefail
host=${1:-couchbox}
here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
out=${COUCHBOX_BUILD_DIR:-$HOME/couchbox-build}
mkdir -p "$out"
release=$(ssh "$host" '. /etc/os-release && echo "$VERSION_ID"')
ffver=$(ssh "$host" "dpkg-query -W -f '\${Version}' libavcodec62" | sed -E 's/^[0-9]+://; s/-.*//')
echo "Pi runs Ubuntu $release with FFmpeg $ffver"
docker run --rm --platform linux/amd64 -e FFVER="$ffver" -v "$here:/src:ro" -v "$out:/out" \
  -v couchbox-ffmpeg-cross:/build "ubuntu:$release" bash /src/build-ffmpeg-docker.sh 2>&1 | tee "$out/ffmpeg-build.log"
scp -q "$out/ffmpeg-rpi.tar.gz" "$out/ffmpeg-deps.txt" "$host:couchbox-build/" 2>/dev/null || {
  ssh "$host" mkdir -p couchbox-build; scp -q "$out/ffmpeg-rpi.tar.gz" "$out/ffmpeg-deps.txt" "$host:couchbox-build/"; }
echo "Copied to $host:~/couchbox-build"
