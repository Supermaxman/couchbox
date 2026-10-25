#!/usr/bin/env bash
# hevc/build.sh (on the Pi, no sudo; needs the docker group): build Jellyfin Desktop
# natively (~10 min). FFmpeg comes from a PC: hevc/build-ffmpeg.sh. Output: ~/couchbox-build.
# Then install with: sudo ~/scripts/9-jellyfin-hevc.sh
set -euo pipefail
here=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
out=$HOME/couchbox-build
mkdir -p "$out"
release=$(. /etc/os-release && echo "$VERSION_ID")
docker run --rm -v "$here:/src:ro" -v "$out:/out" -v couchbox-hevc-build:/build \
  "ubuntu:$release" bash /src/build-jellyfin-docker.sh 2>&1 | tee "$out/jellyfin-build.log"
