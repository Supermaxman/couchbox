#!/bin/bash
# Couchbox installer for a Raspberry Pi 5 already running Ubuntu Server 26.10.
#   curl -fsSL https://github.com/Supermaxman/couchbox/releases/latest/download/install.sh | sudo bash
# Downloads the latest release, checks its signature, installs the packages (and Ubuntu's
# Plasma Bigscreen with them), and hands networking to NetworkManager at the next boot.
# Then: reboot, and the TV shows the Couchbox setup. Safe to run again (it updates).
set -euo pipefail
REPO=${COUCHBOX_REPO:-Supermaxman/couchbox}
CHANNEL=${COUCHBOX_CHANNEL:-stable}
# The release signing key (the same as /usr/share/couchbox/keys/allowed_signers once installed)
SIGNERS='__ALLOWED_SIGNERS__'
say() { printf '\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31m!! %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Run with sudo."
. /etc/os-release
[[ $ID == ubuntu ]] || die "This needs Ubuntu (found $PRETTY_NAME)."
[[ $VERSION_ID == 26.10 ]] || die "This needs Ubuntu 26.10 (found $VERSION_ID): Plasma Bigscreen is packaged from 26.10."
[[ $(dpkg --print-architecture) == arm64 ]] || die "This needs a 64-bit Raspberry Pi OS install (arm64)."
grep -qa 'Raspberry Pi 5' /proc/device-tree/model 2>/dev/null || echo "Note: this doesn't look like a Raspberry Pi 5; continuing."
(( $(df --output=avail -k / | tail -1) > 8000000 )) || die "Needs at least 8 GB free on /."
if dpkg -l ubuntu-desktop gnome-shell 2>/dev/null | grep -q '^ii'; then
  die "A desktop (GNOME) is installed. Couchbox is for Ubuntu Server: start from a fresh Server install."
fi

W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
say "Finding the latest $CHANNEL release of $REPO"
if [[ $CHANNEL == stable ]]; then
  base="https://github.com/$REPO/releases/latest/download"
else
  tag=$(curl -fsSL "https://api.github.com/repos/$REPO/releases?per_page=10" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["tag_name"])')
  base="https://github.com/$REPO/releases/download/$tag"
fi
curl -fsSL -o "$W/release.json" "$base/release.json"
curl -fsSL -o "$W/release.json.sig" "$base/release.json.sig"
printf '%s\n' "$SIGNERS" > "$W/allowed_signers"
ssh-keygen -Y verify -f "$W/allowed_signers" -I release@couchbox -n couchbox-release -s "$W/release.json.sig" < "$W/release.json" >/dev/null \
  || die "The release's signature doesn't match. Not installing."
version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$W/release.json")
say "Couchbox $version (signature checked)"
mapfile -t debs < <(python3 -c 'import json,sys; [print(n, a["sha256"]) for n, a in json.load(open(sys.argv[1]))["assets"].items() if n.endswith(".deb")]' "$W/release.json")
for line in "${debs[@]}"; do
  name=${line% *} sum=${line#* }
  curl -fL --retry 3 -o "$W/$name" "$base/$name"
  echo "$sum  $W/$name" | sha256sum -c --quiet || die "$name doesn't match the signed checksum."
done

say "Ubuntu package sources (the -updates suite must be there)"
src=/etc/apt/sources.list.d/ubuntu.sources
if [[ -f $src ]] && ! grep -qE "^Suites:.*[[:space:]]$VERSION_CODENAME-updates([[:space:]]|$)" "$src"; then
  sed -i -E "s/^Suites:[[:space:]]+${VERSION_CODENAME}[[:space:]]*$/Suites: $VERSION_CODENAME $VERSION_CODENAME-updates $VERSION_CODENAME-backports/" "$src"
fi

say "Tailscale's package repository (Tailscale stays off until Settings turns it on)"
if [[ ! -f /etc/apt/sources.list.d/tailscale.list ]]; then
  tsc=$VERSION_CODENAME
  curl -fsI "https://pkgs.tailscale.com/stable/ubuntu/$tsc.noarmor.gpg" >/dev/null || tsc=resolute
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$tsc.noarmor.gpg" > /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$tsc.tailscale-keyring.list" > /etc/apt/sources.list.d/tailscale.list
fi

say "Installing (Plasma Bigscreen and the rest come from Ubuntu: 1-2 GB, 10-30 minutes)"
apt-get -o DPkg::Lock::Timeout=900 update -qq
export DEBIAN_FRONTEND=noninteractive
# Tailscale that's already up stays up (this may be the connection we're installing over)
ts_was_on=0
systemctl is-enabled tailscaled >/dev/null 2>&1 && tailscale status >/dev/null 2>&1 && ts_was_on=1
apt-get -o DPkg::Lock::Timeout=900 install -y "$W"/couchbox*.deb tailscale
# keep this release's packages for the updater's rollback
install -d -m 700 "/var/lib/couchbox/updates/$version"
cp "$W"/*.deb "$W/release.json" "/var/lib/couchbox/updates/$version/"
[[ $ts_was_on == 1 ]] || systemctl disable tailscaled >/dev/null 2>&1 || true

cat <<X

Couchbox $version is installed. Now:
  sudo reboot
The TV shows the Couchbox setup (remote, Wi-Fi, time zone...). Networking switches to
NetworkManager at this reboot. SSH stays on (Settings → Remote access manages it).
X
