#!/usr/bin/env bash
# Runs inside an x86 ubuntu:<Pi's release> container (see hevc/build-ffmpeg.sh): cross-compiles
# Raspberry Pi's FFmpeg $FFVER for arm64 against the arm64 Ubuntu libraries (multiarch).
# Output in /out: ffmpeg-rpi.tar.gz (/opt/couchbox/ffmpeg-rpi), ffmpeg-deps.txt (runtime packages).
set -euo pipefail
FF=/opt/couchbox/ffmpeg-rpi
export DEBIAN_FRONTEND=noninteractive
log() { printf '\n=== %s\n' "$*"; }

log "arm64 cross toolchain and libraries"
src=/etc/apt/sources.list.d/ubuntu.sources
if ! grep -q ports.ubuntu.com "$src"; then
  sed -i '/^Types:/a Architectures: amd64' "$src"
  suites=$(awk '/^Suites:/ {sub(/^Suites: */, ""); print; exit}' "$src")
  printf '\nTypes: deb\nURIs: http://ports.ubuntu.com/ubuntu-ports/\nSuites: %s\nComponents: main universe\nArchitectures: arm64\nSigned-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg\n' \
    "$suites" >> "$src"
  dpkg --add-architecture arm64
fi
apt-get update -qq
apt-get install -y -qq --no-install-recommends git ca-certificates make gcc libc6-dev nasm pkg-config \
  gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
  libdrm-dev:arm64 libudev-dev:arm64 libgnutls28-dev:arm64 libdav1d-dev:arm64 >/dev/null

log "Raspberry Pi FFmpeg $FFVER (cross)"
dir=/build/ffmpeg-$FFVER
[[ -d $dir ]] || git clone -q --depth 1 --branch "test/$FFVER/main" https://github.com/jc-kynesim/rpi-ffmpeg "$dir"
cd "$dir"
make distclean >/dev/null 2>&1 || true
PKG_CONFIG_LIBDIR=/usr/lib/aarch64-linux-gnu/pkgconfig:/usr/share/pkgconfig \
./configure --prefix="$FF" --libdir="$FF/lib" --incdir="$FF/include" \
  --enable-cross-compile --cross-prefix=aarch64-linux-gnu- --arch=aarch64 --target-os=linux \
  --pkg-config=pkg-config --enable-gpl --enable-shared --disable-static --disable-doc \
  --host-cc=gcc --disable-thumb --enable-neon --enable-sand --enable-v4l2-request --enable-libudev \
  --enable-libdrm --enable-gnutls --enable-libdav1d --extra-version=couchbox-rpi >/dev/null || { tail -20 ffbuild/config.log; exit 1; }
for c in HEVC_V4L2REQUEST_HWACCEL V4L2_REQUEST SAND LIBDRM GNUTLS LIBDAV1D; do
  cat config.h config_components.h | grep -qx "#define CONFIG_$c 1" || { echo "configure: CONFIG_$c is off"; exit 1; }
done
make -j"$(nproc)" >/dev/null
rm -rf /stage && make install DESTDIR=/stage >/dev/null

log "Runtime packages"
needed=$(find /stage -type f \( -name '*.so*' -o -path '*/bin/*' \) -exec aarch64-linux-gnu-readelf -d {} + \
  | awk '/NEEDED/ {gsub(/[][]/, "", $5); print $5}' | grep -vE '^lib(av|sw)' | sort -u)
deps=$(for so in $needed; do
  for d in /usr/lib/aarch64-linux-gnu /lib/aarch64-linux-gnu; do
    [[ -e $d/$so ]] && { dpkg -S "$d/$so" 2>/dev/null | head -1 | cut -d: -f1; break; }
  done
done | sort -u)
printf '%s\n' $deps | tee /out/ffmpeg-deps.txt
tar -C /stage -czf /out/ffmpeg-rpi.tar.gz "${FF#/}"
ls -lh /out/ffmpeg-rpi.tar.gz
