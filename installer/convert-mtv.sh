#!/bin/bash
# convert-mtv.sh: turn the mtv prototype box into Couchbox, in place, keeping what it has:
# the encrypted disk and its network unlock (Tang over Wi-Fi or Ethernet), Wi-Fi, Tailscale,
# SSH, the paired remote, the apps and their sign-ins, and the settings (couchbox import-mtv).
#
#   sudo ./convert-mtv.sh --check              preflight: changes nothing, says what would happen
#   sudo ./convert-mtv.sh --apply              back up, convert, check; asks before it starts
#   sudo ./convert-mtv.sh --rollback BACKUP    put mtv back from the backup --apply made
#
#   --debs DIR     install these couchbox .debs instead of the latest signed release
#   --yes          don't ask
#   --rehearsal    a copy of the box in a container: no Tang, display or device checks
#
# Safety:
# - mtv's files are moved into the backup (/var/backups/couchbox-convert/<time>), never deleted.
# - The new boot image (initrd) goes through the Pi's test boot (piboot-try): it's tried once at
#   the next reboot, and if that boot fails or hangs, unplugging the power boots the old one.
# - Couchbox's settings are written before the package is installed, so SSH and Tailscale are
#   never switched off on the way.
set -euo pipefail

MODE="" DEBS="" YES=0 REHEARSAL=0 BACKUP=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --check|--apply) MODE=${1#--} ;;
    --rollback) MODE=rollback; BACKUP=${2:?--rollback needs the backup directory}; shift ;;
    --debs) DEBS=$(readlink -f "${2:?}"); shift ;;
    --yes) YES=1 ;;
    --rehearsal) REHEARSAL=1 ;;
    *) sed -n '2,20p' "$0"; exit 2 ;;
  esac
  shift
done
[[ -n $MODE ]] || { sed -n '2,20p' "$0"; exit 2; }
[[ $EUID -eq 0 ]] || { echo "Run with sudo."; exit 1; }

REPO=${COUCHBOX_REPO:-Supermaxman/couchbox}
SIGNERS='__ALLOWED_SIGNERS__'
TV=tv
TVHOME=$(getent passwd "$TV" | cut -d: -f6 || true)
FW=/boot/firmware
LOG=/var/log/couchbox-convert.log
SITES="dropout 2ndtry nebula twitch"
fails=0 warns=0
say() { printf '\033[1;36m==> %s\033[0m\n' "$*" | tee -a "$LOG"; }
ok() { printf '  \033[32mok\033[0m   %s\n' "$*" | tee -a "$LOG"; }
warn() { printf '  \033[33mwarn\033[0m %s\n' "$*" | tee -a "$LOG"; warns=$((warns + 1)); }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$*" | tee -a "$LOG"; fails=$((fails + 1)); }
die() { printf '\033[1;31m!! %s\033[0m\n' "$*" | tee -a "$LOG" >&2; exit 1; }
ask() { [[ $YES == 1 ]] && return 0; read -r -p "$1 [y/N] " a </dev/tty; [[ $a == [yY]* ]]; }
user_systemctl() { systemctl --user -M "$TV@" "$@" 2>/dev/null || true; }

# Everything mtv put on the system (globs allowed), moved into the backup by --apply
MTV_PATHS=(
  /usr/local/bin/mtv-* /usr/local/lib/mtv-* /usr/local/share/mtv
  /usr/local/share/applications/mtv-*.desktop /usr/local/share/plasma/plasmoids/org.kde.bigscreen.homescreen
  /etc/systemd/system/mtv-*.service /etc/systemd/system/mtv-*.timer
  /etc/udev/rules.d/61-mtv-input.rules /etc/sddm.conf.d/50-mtv.conf
  /etc/systemd/logind.conf.d/50-mtv.conf /etc/systemd/journald.conf.d/50-mtv.conf
  /etc/apt/apt.conf.d/80mtv-home /etc/netplan/90-mtv-networkmanager.yaml
  /etc/dracut.conf.d/90-mtv-crypt.conf /etc/dracut.conf.d/91-mtv-tang.conf /usr/lib/dracut/modules.d/90mtv-wifi
  "$TVHOME"/.config/systemd/user/mtv-*.service "$TVHOME"/.config/systemd/user/graphical-session.target.wants/mtv-*.service
  "$TVHOME"/.config/autostart/mtv-*.desktop "$TVHOME"/.local/share/applications/mtv-web-*.desktop
)
# Kept as they are: /etc/mtv (the source of the import, and for a rollback), /opt/mtv
# (the old Jellyfin build, unused afterwards), sudoers.d/90-mtv-admin (the admin's sudo),
# sshd_config.d/00-mtv-hardening.conf (same rules as Couchbox's, stricter ciphers).

luks_dev() {
  if [[ $REHEARSAL == 1 ]]; then  # a copy of the box: its crypttab stands in for the disk
    grep -q '^root[[:space:]]' /etc/crypttab 2>/dev/null && echo /dev/rehearsal && return 0
    return 1
  fi
  local src; src=$(findmnt -no SOURCE /)
  [[ $src == /dev/mapper/* ]] || return 1
  cryptsetup status "${src#/dev/mapper/}" | awk '/device:/ {print $2}'
}

tang_urls() {  # the Tang servers bound to the disk, one per line
  if [[ $REHEARSAL == 1 ]]; then cat /etc/mtv/tang.url 2>/dev/null; return 0; fi
  clevis luks list -d "$1" 2>/dev/null | grep -o '"url":"[^"]*"' | cut -d'"' -f4 || true
}

# ------------------------------------------------------------------ the release
fetch_release() {  # -> $REL (a directory with the .debs and couchbox's Python package)
  REL=$(mktemp -d /var/tmp/couchbox-convert.XXXX)
  if [[ -n $DEBS ]]; then
    cp "$DEBS"/couchbox*.deb "$REL/" || return 1
    ok "using the .debs in $DEBS ($(cd "$REL" && ls couchbox*.deb | tr '\n' ' '))"
  else
    local base="https://github.com/$REPO/releases/latest/download"
    curl -fsSL -o "$REL/release.json" "$base/release.json" && curl -fsSL -o "$REL/release.json.sig" "$base/release.json.sig" \
      || { fail "can't download the latest release"; return 1; }
    printf '%s\n' "$SIGNERS" > "$REL/allowed_signers"
    ssh-keygen -Y verify -f "$REL/allowed_signers" -I release@couchbox -n couchbox-release -s "$REL/release.json.sig" \
      < "$REL/release.json" >/dev/null || { fail "the release's signature doesn't match"; return 1; }
    local line name sum
    while read -r line; do
      name=${line% *} sum=${line#* }
      curl -fsSL --retry 3 -o "$REL/$name" "$base/$name" || { fail "download $name"; return 1; }
      echo "$sum  $REL/$name" | sha256sum -c --quiet || { fail "$name doesn't match the signed checksum"; return 1; }
    done < <(python3 -c 'import json,sys; [print(n, a["sha256"]) for n, a in json.load(open(sys.argv[1]))["assets"].items() if n.endswith(".deb")]' "$REL/release.json")
    ok "Couchbox $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$REL/release.json"), signature checked"
  fi
  mkdir -p "$REL/x" && dpkg-deb -x "$REL"/couchbox_*_all.deb "$REL/x"
  PYLIB=$(dirname "$(find "$REL/x/usr/lib/python3" -type d -name couchbox -path '*/couchbox' | head -1)")
  [[ -d $PYLIB/couchbox ]] || { fail "no couchbox Python package in the .deb"; return 1; }
}

# ------------------------------------------------------------------ preflight
check() {
  : > "$LOG"
  say "Preflight ($(date))"
  . /etc/os-release
  [[ $VERSION_ID == 26.10 && $(dpkg --print-architecture) == arm64 ]] && ok "Ubuntu $VERSION_ID arm64" || fail "needs Ubuntu 26.10 arm64 (found $VERSION_ID $(dpkg --print-architecture))"
  [[ -f /etc/mtv/mtv.conf ]] && ok "mtv settings in /etc/mtv" || fail "no /etc/mtv/mtv.conf: not an mtv box"
  [[ -n $TVHOME && -d $TVHOME ]] && ok "TV user $TV ($TVHOME)" || fail "no $TV user"
  [[ -x /usr/bin/couchbox ]] && warn "Couchbox is already installed: --apply carries on from there" || ok "Couchbox not installed yet"

  # disk encryption and its network unlock
  local dev tang=""
  if dev=$(luks_dev); then
    ok "root is LUKS ($dev)"
    tang=$(tang_urls "$dev" | head -1)
    [[ -n $tang ]] && ok "network unlock bound: $tang" || fail "no Clevis/Tang binding on $dev"
    [[ -f /etc/mtv/initrd-wpa.conf ]] && ok "Wi-Fi for unlock at boot (/etc/mtv/initrd-wpa.conf)" || warn "no initrd Wi-Fi config: unlock at boot would need Ethernet"
    if [[ -n $tang ]]; then
      if curl -fsS --max-time 5 "$tang/adv" >/dev/null 2>&1; then ok "Tang server answers"
      elif [[ $REHEARSAL == 1 ]]; then warn "Tang server not reachable (rehearsal)"
      else fail "Tang server $tang doesn't answer: the converted box couldn't unlock by itself"; fi
    fi
    if [[ $REHEARSAL == 0 ]]; then
      grep -qs 'tryboot_a_b=1' "$FW/autoboot.txt" "$FW/config.txt" && ok "Pi test boot (tryboot) on" || fail "no tryboot_a_b=1 in $FW/autoboot.txt or config.txt: the new boot image couldn't be tested first"
      if [[ -d $FW/new ]] && [[ $(cat "$FW/new/state" 2>/dev/null) == unknown ]]; then
        fail "a new boot image is already waiting to be tested ($FW/new): reboot once first"
      else ok "no untested boot image pending"; fi
    fi
  else
    warn "root isn't encrypted: nothing to carry over for unlock"
  fi

  # the connections we must not lose
  { systemctl is-enabled ssh.service >/dev/null 2>&1 || systemctl is-enabled ssh.socket >/dev/null 2>&1; } && ok "SSH enabled" || warn "SSH isn't enabled"
  if [[ $REHEARSAL == 0 ]]; then
    tailscale status >/dev/null 2>&1 && ok "Tailscale up ($(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null))" || warn "Tailscale isn't up"
  fi
  nmcli -t -f NAME,TYPE connection show 2>/dev/null | grep -q ':802-11-wireless' && ok "Wi-Fi profile in NetworkManager" || warn "no Wi-Fi profile in NetworkManager"
  local free; free=$(df --output=avail -k / | tail -1)
  (( free > 3000000 )) && ok "free space: $((free / 1024 / 1024)) GB" || fail "needs 3 GB free on /"
  if [[ $REHEARSAL == 0 ]]; then
    local fwfree; fwfree=$(df --output=avail -k "$FW" | tail -1)
    (( fwfree > 150000 )) && ok "boot partition free: $((fwfree / 1024)) MB" || fail "needs 150 MB free on $FW for the test boot image"
  fi
  fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && fail "apt is busy" || ok "apt is free"

  # the release and what installing it would do
  say "The release"
  fetch_release || { say "NOT READY: the release (above). Nothing was changed."; return 1; }
  local sim; sim=$(apt-get -s -o Debug::NoLocking=1 install "$REL"/couchbox*.deb 2>&1) || { fail "apt can't install it: $(echo "$sim" | tail -3)"; say "NOT READY. Nothing was changed."; return 1; }
  local inst rem; inst=$(echo "$sim" | grep -c '^Inst ' || true); rem=$(echo "$sim" | grep '^Remv ' | awk '{print $2}' | tr '\n' ' ' || true)
  ok "apt would install $inst packages"
  [[ -z $rem ]] && ok "apt would remove nothing" || fail "apt would remove: $rem"

  if luks_dev >/dev/null; then
    say "The new boot image, built aside (/var/tmp) and checked; /boot isn't touched"
    shadow_initrd || true
  fi

  say "What carries over (couchbox import-mtv)"
  PYTHONPATH=$PYLIB python3 - <<'PY' | tee -a "$LOG"
from couchbox import migrate_mtv
s, sec = migrate_mtv.read("/etc/mtv")
hide = ("voice.notes",)
for k, v in sorted(s.items()):
    print(f"  {k} = {'(text, %d chars)' % len(v) if k in hide else v}")
print("  secrets: " + (", ".join(sorted(sec)) or "none"))
PY
  for s in $SITES; do
    [[ -s $TVHOME/.local/share/mtv-$s/session.json ]] && ok "$s sign-in carries over" || warn "$s: not signed in on mtv"
  done
  [[ -d $TVHOME/.local/share/jellyfin-desktop ]] && ok "Jellyfin Desktop sign-in stays (same folder)" || warn "Jellyfin Desktop has no data yet"
  [[ -d $TVHOME/.var/app/org.chromium.Chromium ]] && ok "web app sign-ins stay (Chromium profile)"
  [[ -d $TVHOME/.var/app/rocks.shy.VacuumTube ]] && ok "YouTube sign-in stays (VacuumTube)"
  ls /var/lib/bluetooth/*/* -d >/dev/null 2>&1 && ok "Bluetooth pairings stay ($(ls -d /var/lib/bluetooth/*/??:* 2>/dev/null | wc -l))"
  say "mtv files that move to the backup"
  local n=0 p
  for p in "${MTV_PATHS[@]}"; do [[ -e $p || -L $p ]] && n=$((n + 1)); done
  ok "$n files and folders (listed in the log)"
  for p in "${MTV_PATHS[@]}"; do [[ -e $p || -L $p ]] && echo "       $p" >> "$LOG"; done
  local units; units=$(systemctl list-unit-files 'mtv-*' --no-legend 2>/dev/null | awk '$2=="enabled"{print $1}' | tr '\n' ' ')
  ok "mtv units to stop: ${units:-none}"
  if [[ $REHEARSAL == 0 ]]; then
    if pgrep -u "$TV" -f 'vacuumtube|jellyfin-desktop|mtv-(dropout|twitch|nebula|2ndtry)|uxplay .*-fs' >/dev/null && \
       [[ $(top -bn2 -d2 -u "$TV" | awk '/^top -/{n++} n==2 && $1 ~ /^[0-9]+$/ {s+=$9} END {print int(s)}') -gt 40 ]]; then
      warn "something is playing on the TV right now: --apply restarts the TV session"
    fi
  fi
  echo
  if (( fails )); then say "NOT READY: $fails problem(s) above, $warns warning(s). Nothing was changed."; return 1; fi
  say "READY ($warns warning(s)). Nothing was changed. Next: sudo $0 --apply"
}

# ------------------------------------------------------------------ apply
apply() {
  check || die "Fix the problems above first."
  echo
  echo "This stops mtv's services, installs Couchbox, carries the settings and sign-ins over,"
  echo "and switches the TV to Couchbox. The new boot image is tested at the next reboot."
  ask "Convert this box now?" || die "Not converted."
  local ts; ts=$(date +%Y%m%d-%H%M%S)
  BK=/var/backups/couchbox-convert/$ts
  install -d -m 700 "$BK"
  say "Backup: $BK"
  systemctl list-unit-files 'mtv-*' --no-legend > "$BK/system-units.txt" 2>/dev/null || true
  ls "$TVHOME/.config/systemd/user/graphical-session.target.wants/" > "$BK/user-units.txt" 2>/dev/null || true
  dpkg --get-selections > "$BK/dpkg-selections.txt"
  [[ -d $FW/current ]] && cp -a "$FW/current/cmdline.txt" "$FW/current/initrd.img" "$BK/" 2>/dev/null || true
  local list=() p
  for p in "${MTV_PATHS[@]}"; do [[ -e $p || -L $p ]] && list+=("$p"); done
  tar --xattrs --acls -cpf "$BK/mtv-files.tar" -P "${list[@]}"
  cp -a /etc/mtv "$BK/etc-mtv"
  printf '%s\n' "${list[@]}" > "$BK/moved.txt"
  ok "${#list[@]} mtv files saved"

  say "Couchbox settings (before the package, so SSH and Tailscale stay on)"
  install -d -m 755 /etc/couchbox /etc/couchbox/luks /var/lib/couchbox /var/lib/couchbox/state
  install -d -m 700 /var/lib/couchbox/secrets
  chmod 700 /etc/couchbox/luks
  PYTHONPATH=$PYLIB COUCHBOX_SHARE=$REL/x/usr/share/couchbox python3 - <<'PY'
import json, time
from couchbox import migrate_mtv, paths, secrets, settings
s, sec = migrate_mtv.read("/etc/mtv")
settings.update(s)
for k, v in sec.items():
    secrets.put(k, v)
st = paths.state() / "state"
st.mkdir(parents=True, exist_ok=True)
(st / "firstboot.done").write_text("converted from mtv\n")
(st / "setup.json").write_text(json.dumps({"done": True, "step": 99, "completed": ["converted"], "time": time.time()}) + "\n")
print("  settings:", len(settings.changed()), "secrets:", len(sec))
PY
  local dev tang
  if dev=$(luks_dev); then
    [[ -f /etc/mtv/initrd-wpa.conf ]] && install -m 600 /etc/mtv/initrd-wpa.conf /etc/couchbox/luks/initrd-wpa.conf
    tang=$(tang_urls "$dev" | python3 -c 'import json,sys; print(json.dumps({"urls": sys.stdin.read().split()}))')
    echo "$tang" > /etc/couchbox/luks/tang.json
    ok "disk unlock: $tang, Wi-Fi at boot: $([[ -f /etc/couchbox/luks/initrd-wpa.conf ]] && echo yes || echo no)"
  fi

  say "Stopping mtv"
  local units; units=$(systemctl list-unit-files 'mtv-*' --no-legend 2>/dev/null | awk '{print $1}')
  for u in $units; do systemctl disable --now "$u" >/dev/null 2>&1 || true; done
  user_systemctl stop mtv-airplay.service mtv-voice-overlay.service
  for p in "${list[@]}"; do rm -rf "$p"; done
  systemctl daemon-reload
  user_systemctl daemon-reload
  udevadm control --reload 2>/dev/null || true
  ok "mtv services stopped and its files moved to the backup"

  say "Installing Couchbox"
  export DEBIAN_FRONTEND=noninteractive
  apt-get -o DPkg::Lock::Timeout=900 install -y "$REL"/couchbox*.deb 2>&1 | tail -5 | tee -a "$LOG"
  local ver; ver=$(dpkg-query -W -f '${Version}' couchbox)
  install -d -m 700 "/var/lib/couchbox/updates/$ver"
  cp "$REL"/*.deb "/var/lib/couchbox/updates/$ver/"; [[ -f $REL/release.json ]] && cp "$REL/release.json" "/var/lib/couchbox/updates/$ver/"
  ok "couchbox $ver installed"

  say "App sign-ins and preferences"
  for s in $SITES; do
    if [[ -d $TVHOME/.local/share/mtv-$s && ! -e $TVHOME/.local/share/couchbox-$s/session.json ]]; then
      runuser -u "$TV" -- mkdir -p "$TVHOME/.local/share/couchbox-$s"
      runuser -u "$TV" -- cp -a "$TVHOME/.local/share/mtv-$s/." "$TVHOME/.local/share/couchbox-$s/"
      ok "$s"
    fi
    if [[ -f $TVHOME/.config/mtv/mtv-$s.conf && ! -e $TVHOME/.config/couchbox/couchbox-$s.conf ]]; then
      runuser -u "$TV" -- mkdir -p "$TVHOME/.config/couchbox"
      runuser -u "$TV" -- cp -a "$TVHOME/.config/mtv/mtv-$s.conf" "$TVHOME/.config/couchbox/couchbox-$s.conf"
    fi
  done

  if [[ -n ${dev:-} ]]; then
    say "Boot image: unlock with Tang (Wi-Fi or Ethernet), through the Pi's test boot"
    printf '# Couchbox (from mtv): root is LUKS2; the console asks for the passphrase\nadd_dracutmodules+=" crypt systemd-cryptsetup "\n' \
      > /etc/dracut.conf.d/90-couchbox-crypt.conf
    if [[ $REHEARSAL == 1 ]]; then  # a container: the copy's kernel, and say which board
      export FK_MACHINE="Raspberry Pi 5 Model B Rev 1.0" COUCHBOX_KVER
      COUCHBOX_KVER=$(ls /usr/lib/modules | sort -V | tail -1)
    fi
    python3 -c 'from couchbox import encryption; encryption.rebuild_initrd(network=True)' 2>&1 | tail -5 | tee -a "$LOG"
    verify_initrd "$FW/new/initrd.img" || {
      piboot-try --reset-new >/dev/null 2>&1 || rm -rf "$FW/new"
      die "The new boot image is missing parts (above): it was removed, the box keeps booting the old one. Nothing else to undo for boot; see $LOG."
    }
  fi

  say "Starting Couchbox"
  systemctl daemon-reload
  for u in couchboxd couchbox-input couchbox-cec couchbox-phone couchbox-memory couchbox-voice; do
    systemctl enable --now "$u.service" >/dev/null 2>&1 || warn "$u didn't start"
  done
  couchbox home rebuild >/dev/null 2>&1 || warn "home rebuild"
  if [[ $REHEARSAL == 0 ]]; then
    systemctl restart sddm.service && ok "TV session restarted into Couchbox"
  fi
  sleep 5
  say "Checks"
  couchbox doctor | tee -a "$LOG" || warn "couchbox doctor reported problems (above)"
  for u in couchboxd couchbox-input couchbox-phone couchbox-memory; do
    systemctl is-active --quiet "$u" && ok "$u running" || fail "$u not running"
  done
  { systemctl is-active --quiet ssh.service || systemctl is-active --quiet ssh.socket; } && ok "SSH still on" || fail "SSH is off"
  [[ $REHEARSAL == 1 ]] || { tailscale status >/dev/null 2>&1 && ok "Tailscale still up" || fail "Tailscale is down"; }
  echo
  say "Converted. Backup: $BK"
  cat <<X | tee -a "$LOG"
Next, when nobody's watching:  sudo reboot
  The box tries the new boot image once (it may restart twice). It should be back in 2-3
  minutes, unlocked by Tang, on the Couchbox home screen. If it isn't back after 5 minutes,
  unplug the power and plug it back in: it boots the old image, which unlocks the same way.
To undo everything:  sudo $0 --rollback $BK
X
}

shadow_initrd() {
  # What --apply will build: this system's dracut and host-only detection, with Couchbox's
  # unlock module in place of mtv's, from the .deb (reading mtv's initrd Wi-Fi config for now)
  local base=$REL/dracut conf=$REL/dracut.conf.d img=$REL/initrd.img kver
  kver=$(uname -r)
  [[ $REHEARSAL == 1 ]] && kver=$(ls /usr/lib/modules | sort -V | tail -1)
  rm -rf "$base" "$conf"; cp -a /usr/lib/dracut "$base"; mkdir -p "$conf"
  rm -rf "$base/modules.d/90mtv-wifi"
  cp -a "$REL/x/usr/lib/dracut/modules.d/90couchbox" "$base/modules.d/"
  sed -i 's|/etc/couchbox/luks/initrd-wpa.conf|/etc/mtv/initrd-wpa.conf|g' "$base/modules.d/90couchbox/module-setup.sh"
  cp /etc/dracut.conf.d/*.conf "$conf/" 2>/dev/null || true
  rm -f "$conf/90-mtv-crypt.conf" "$conf/91-mtv-tang.conf"
  printf 'add_dracutmodules+=" crypt systemd-cryptsetup "\n' > "$conf/90-couchbox-crypt.conf"
  printf 'add_dracutmodules+=" clevis clevis-pin-tang clevis-pin-sss systemd-networkd%s "\n' \
    "$([[ -f /etc/mtv/initrd-wpa.conf ]] && echo ' couchbox')" > "$conf/91-couchbox-unlock.conf"
  if ! dracutbasedir=$base ionice -c3 nice -n19 dracut --quiet --force --confdir "$conf" --kver "$kver" "$img" >"$REL/dracut.log" 2>&1; then
    fail "dracut couldn't build it: $(tail -3 "$REL/dracut.log")"; return 1
  fi
  ok "built ($(du -h "$img" | cut -f1))"
  # names the conversion gives these files
  verify_initrd "$img" "$FW/current/cmdline.txt"
}

verify_initrd() {  # verify_initrd IMG CMDLINE: the new boot image must unlock the disk the way the old one did
  local img=$1 cmdline=${2:-$(dirname "$1")/cmdline.txt} have miss=0
  [[ -f $img ]] || { fail "no new boot image at $img"; return 1; }
  have=$(lsinitrd "$img" 2>/dev/null)
  local need=(
    "usr/bin/clevis-decrypt-tang" "clevis-luks-askpass" "systemd-cryptsetup"
    "etc/crypttab" "usr/sbin/wpa_supplicant" "etc/wpa_supplicant/couchbox-initrd.conf"
    "couchbox-initrd-wifi.service" "etc/systemd/network/10-couchbox-initrd.network"
    "brcmfmac43455-sdio.raspberrypi,5-model-b" "brcmfmac.ko" "systemd-networkd" "usr/bin/jose" "usr/bin/curl"
  )
  [[ -f /etc/couchbox/luks/initrd-wpa.conf || -f /etc/mtv/initrd-wpa.conf ]] || need=("${need[@]:0:4}" "systemd-networkd" "usr/bin/jose" "usr/bin/curl")
  if [[ $REHEARSAL == 1 ]]; then  # a container can't detect the disk: no host-only crypttab
    local keep=() n0; for n0 in "${need[@]}"; do [[ $n0 == etc/crypttab ]] || keep+=("$n0"); done; need=("${keep[@]}")
  fi
  local n
  for n in "${need[@]}"; do
    if grep -qF -- "$n" <<<"$have"; then ok "boot image has $n"; else fail "boot image is missing $n"; miss=1; fi
  done
  # everything the old image had, under Couchbox's names, should be in the new one too
  local old="$FW/current/initrd.img"
  if [[ -f $old ]]; then
    # file entries only: the name follows the date and time (or year) column
    names() { sed -nE 's/^[-dlcbps][-rwxsStT]{9} .* [0-9]{1,2} +([0-9]{2}:[0-9]{2}|[0-9]{4}) (.+)$/\2/p' | sed 's/ -> .*//'; }
    comm -23 <(lsinitrd "$old" 2>/dev/null | names | sed 's/mtv-initrd/couchbox-initrd/; s/mtv-any/couchbox-any/' | grep -v mtv | sort -u) \
             <(names <<<"$have" | sort -u) > /var/log/couchbox-convert-initrd.diff || true
    local nd; nd=$(wc -l < /var/log/couchbox-convert-initrd.diff)
    (( nd == 0 )) && ok "the new boot image has every file the old one had" \
      || warn "$nd file(s) of the old boot image aren't in the new one: /var/log/couchbox-convert-initrd.diff"
  fi
  if [[ $REHEARSAL == 0 ]]; then
    grep -q 'rd.neednet=1' "$cmdline" 2>/dev/null && ok "boot command line asks for the network" || { fail "rd.neednet=1 missing from $cmdline"; miss=1; }
  fi
  return $miss
}

# ------------------------------------------------------------------ rollback
rollback() {
  [[ -f $BACKUP/mtv-files.tar ]] || die "$BACKUP isn't a conversion backup."
  ask "Put mtv back from $BACKUP?" || die "Nothing changed."
  : >> "$LOG"
  say "Stopping Couchbox"
  for u in $(systemctl list-unit-files 'couchbox*' --no-legend | awk '{print $1}'); do systemctl disable --now "$u" >/dev/null 2>&1 || true; done
  user_systemctl stop couchbox-airplay.service couchbox-voice-overlay.service
  export DEBIAN_FRONTEND=noninteractive
  apt-get -y purge couchbox couchbox-media 2>&1 | tail -3 | tee -a "$LOG"
  rm -f /etc/dracut.conf.d/90-couchbox-crypt.conf /etc/dracut.conf.d/91-couchbox-unlock.conf
  rm -f "$TVHOME"/.config/autostart/couchbox-*.desktop "$TVHOME"/.config/systemd/user/graphical-session.target.wants/couchbox-*.service
  say "Restoring mtv's files"
  tar --xattrs --acls -xpf "$BACKUP/mtv-files.tar" -P
  systemctl daemon-reload
  while read -r unit state _; do
    [[ $state == enabled ]] && systemctl enable --now "$unit" >/dev/null 2>&1 || true
  done < "$BACKUP/system-units.txt"
  user_systemctl daemon-reload
  user_systemctl start mtv-airplay.service mtv-voice-overlay.service
  udevadm control --reload 2>/dev/null || true
  if luks_dev >/dev/null; then
    say "Boot image back to mtv's (through the test boot)"
    local kver; kver=$(uname -r)
    dracut --force --kver "$kver" 2>&1 | tail -2 | tee -a "$LOG"
    flash-kernel "$kver" 2>&1 | tail -2 | tee -a "$LOG" || true
    grep -q 'rd.neednet=1' "$FW/new/cmdline.txt" 2>/dev/null || sed -i '1s/$/ rd.neednet=1/' "$FW/new/cmdline.txt"
  fi
  [[ -x /usr/local/bin/mtv-home ]] && /usr/local/bin/mtv-home --refresh >/dev/null 2>&1 || true
  [[ $REHEARSAL == 1 ]] || systemctl restart sddm.service
  say "mtv is back. Reboot when convenient (the old boot image is tested first)."
}

case $MODE in
  check) check ;;
  apply) apply ;;
  rollback) rollback ;;
esac
