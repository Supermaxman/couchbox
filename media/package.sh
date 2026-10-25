#!/bin/bash
# couchbox-media_VERSION_arm64.deb from what build-ffmpeg.sh and build-jellyfin.sh left in
# OUT (default /out), plus one tarball with the exact sources of both (GPL).
#   media/package.sh VERSION [OUT]
set -euo pipefail
V=${1#v} OUT=${2:-/out}
S=$(mktemp -d)
tar -C "$S" -xzf "$OUT/ffmpeg-rpi.tar.gz"
tar -C "$S" -xzf "$OUT/jellyfin-desktop.tar.gz"
deps=$(cat "$OUT/ffmpeg-deps.txt" "$OUT/jellyfin-deps.txt" | grep -v '^$' | sort -u | paste -sd, | sed 's/,/, /g')
mkdir -p "$S/DEBIAN" "$S/usr/share/doc/couchbox-media"
cat > "$S/DEBIAN/control" <<X
Package: couchbox-media
Version: $(printf '%s' "$V" | sed 's/-/~/')
Architecture: arm64
Maintainer: Couchbox Authors <couchbox@users.noreply.github.com>
Section: video
Priority: optional
Depends: $deps
Description: Couchbox media: hardware HEVC for the Raspberry Pi 5
 Raspberry Pi's FFmpeg fork (V4L2 request API: the Pi 5's HEVC decoder) in
 /opt/couchbox/ffmpeg-rpi, used by Couchbox's own TV apps, and Jellyfin Desktop
 built to use it, in /opt/couchbox/jellyfin-desktop.
X
cat > "$S/usr/share/doc/couchbox-media/copyright" <<'X'
Raspberry Pi FFmpeg (https://github.com/jc-kynesim/rpi-ffmpeg): LGPL-2.1-or-later / GPL-2.0-or-later
(built with --enable-gpl). Jellyfin Desktop (https://github.com/jellyfin/jellyfin-desktop): GPL.
The exact sources are attached to each Couchbox release: couchbox-media-VERSION-sources.tar.xz.
X
dpkg-deb --root-owner-group -Zxz -b "$S" "$OUT/couchbox-media_${V}_arm64.deb"
tar -C "$OUT" -cf "$OUT/couchbox-media-$V-sources.tar" ffmpeg-source.tar.xz jellyfin-desktop-source.tar.xz
rm -rf "$S"
ls -la "$OUT"/couchbox-media*
