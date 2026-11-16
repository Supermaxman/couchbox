#!/bin/bash
# Prove that a dev box joins Wi-Fi by itself, with its Ethernet off, the way the setup joins it
# (couchboxd's network.wifi_connect), and that the setup's own Wi-Fi comes up. Ethernet comes
# back afterwards, and a timer on the box brings it back after --lifeline minutes whatever happens.
#   ci/box-wifi-check.sh HOST SSID PASSWORD_FILE [--lifeline MINUTES] [--hotspot] [--scan-from SCANNER]
#     --hotspot            also start the setup Wi-Fi (Couchbox-XXXX) and check it's broadcasting
#     --scan-from SCANNER  a Linux host with Wi-Fi, reachable by `ssh SCANNER`, that looks for it (3 scans)
#     --ap-powersave on|off  switch the Wi-Fi chip's power saving while the setup Wi-Fi is on (default: as is)
# The password is read from PASSWORD_FILE and sent over SSH's stdin: never on a command line.
# Results: a JSON report printed at the end, and kept on the box in /var/lib/couchbox-test/.
set -euo pipefail
[[ $# -ge 3 && $1 != -* ]] || { echo "usage: $0 HOST SSID PASSWORD_FILE [--lifeline MINUTES] [--hotspot] [--scan-from SCANNER] [--ap-powersave on|off]" >&2; exit 2; }
HOST=$1 SSID=$2 PWFILE=$3
shift 3
LIFE=10 HOTSPOT=0 SCANNER="" APPS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --lifeline) LIFE=$2; shift ;;
    --hotspot) HOTSPOT=1 ;;
    --scan-from) SCANNER=$2; shift ;;
    --ap-powersave) APPS=$2; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done
RUN=$(date +%Y%m%d-%H%M%S)
B64SSID=$(printf %s "$SSID" | base64 -w0)

# the scanner looks for any Couchbox-XXXX network every few seconds from the start, on its own:
# with Ethernet off and the radio busy as the setup Wi-Fi, the box can't be asked anything
SCANLOG=""
if [[ -n $SCANNER && $HOTSPOT == 1 ]]; then
  SCANLOG=$(mktemp)
  # shellcheck disable=SC2016  # expanded on the scanner
  ssh "$SCANNER" 'dev=$(iw dev | awk "/Interface/ {print \$2; exit}"); end=$(( $(date +%s) + '"$((LIFE * 60))"' ));
    while [ "$(date +%s)" -lt "$end" ]; do
      r=$(sudo iw dev "$dev" scan 2>/dev/null | awk "/^BSS/ {s=\"\"} /signal:/ {g=\$2} /SSID: Couchbox-/ {print \$2, g}" | sort -u | xargs)
      echo "$(date +%T) ${r:-none}"; sleep 4
    done' >"$SCANLOG" 2>/dev/null &
  SCANPID=$!
  trap 'kill $SCANPID 2>/dev/null || true' EXIT
fi

# the password, to a root-only file on the box
ssh "$HOST" 'sudo install -d -m 700 /run/couchbox-test && sudo sh -c "umask 077; cat > /run/couchbox-test/psk"' <"$PWFILE"

# the test runs on the box as a service of its own: taking Ethernet down may drop this SSH session
ssh "$HOST" sudo bash -s -- "$B64SSID" "$LIFE" "$RUN" "$HOTSPOT" "${APPS:--}" <<'BOX'
set -euo pipefail
install -d -m 755 /var/lib/couchbox-test
cat >/run/couchbox-test/wifi-check.py <<'PY'
import base64, json, subprocess, sys, time
from couchbox import ipc

ssid = base64.b64decode(sys.argv[1]).decode()
life, run, hotspot = int(sys.argv[2]), sys.argv[3], sys.argv[4] == "1"
apps = "" if len(sys.argv) < 6 or sys.argv[5] == "-" else sys.argv[5]
out = f"/var/lib/couchbox-test/wifi-{run}.json"
rep = {"run": run, "ssid": ssid, "ok": False, "steps": []}


def sh(*cmd, timeout=60):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.stdout.strip()


def step(name, **kw):
    rep["steps"].append({"t": round(time.time() - t0, 1), "step": name, **kw})
    json.dump(rep, open(out, "w"), indent=1)


t0 = time.time()
sh("systemd-run", "--quiet", f"--on-active={life}min", "--unit=couchbox-test-lifeline", "nmcli", "device", "connect", "eth0")
step("lifeline", minutes=life)
try:
    try:
        ipc.call("network.wifi_forget", ssid=ssid)
    except ipc.IpcError:
        pass
    sh("nmcli", "device", "disconnect", "eth0")
    time.sleep(3)
    step("ethernet off", eth0=sh("nmcli", "-t", "-f", "GENERAL.STATE", "device", "show", "eth0"))
    pw = open("/run/couchbox-test/psk").read().rstrip("\n")
    t = time.time()
    try:
        ipc.call("network.wifi_connect", ssid=ssid, password=pw, timeout=90)
        step("joined", seconds=round(time.time() - t, 1))
    except ipc.IpcError as e:
        step("join failed", error=str(e))
        raise SystemExit(1)
    finally:
        pw = ""
    for _ in range(30):
        code = sh("curl", "-sS", "--interface", "wlan0", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10", "https://github.com")
        if code.startswith(("2", "3")):
            break
        time.sleep(2)
    link = sh("iw", "dev", "wlan0", "link")
    step("online over Wi-Fi", http=code,
         signal=next((l.split(":", 1)[1].strip() for l in link.splitlines() if "signal" in l), ""),
         freq=next((l.split(":", 1)[1].strip() for l in link.splitlines() if "freq" in l), ""),
         power_save=sh("iw", "dev", "wlan0", "get", "power_save"),
         ip=sh("sh", "-c", "ip -4 -o addr show wlan0 | awk '{print $4}'"))
    rep["ok"] = code.startswith(("2", "3"))
    if hotspot:
        sh("nmcli", "device", "disconnect", "wlan0")
        h = ipc.call("setup.hotspot", on=True, timeout=90)
        time.sleep(5)
        if apps:
            sh("iw", "dev", "wlan0", "set", "power_save", apps)
        info = sh("iw", "dev", "wlan0", "info")
        step("setup Wi-Fi on", ssid=h.get("ssid"), ap="type AP" in info,
             channel=next((l.strip() for l in info.splitlines() if "channel" in l), ""),
             power_save=sh("iw", "dev", "wlan0", "get", "power_save"))
        rep["hotspot_ssid"] = h.get("ssid")
        json.dump(rep, open(out, "w"), indent=1)
        time.sleep(40)  # time for the scanner to look
        ipc.call("setup.hotspot", on=False, timeout=60)
        step("setup Wi-Fi off")
finally:
    subprocess.run(["rm", "-f", "/run/couchbox-test/psk"])
    sh("nmcli", "device", "connect", "eth0")
    sh("systemctl", "stop", "couchbox-test-lifeline.timer")
    step("ethernet back", eth0=sh("nmcli", "-t", "-f", "GENERAL.STATE", "device", "show", "eth0"))
    rep["done"] = True
    json.dump(rep, open(out, "w"), indent=1)
PY
systemd-run --quiet --unit="couchbox-wifi-check-$3" --collect /usr/bin/python3 /run/couchbox-test/wifi-check.py "$@"
echo "started on the box: couchbox-wifi-check-$3"
BOX

R=/var/lib/couchbox-test/wifi-$RUN.json
for _ in $(seq $((LIFE * 6 + 12))); do
  if ssh -o ConnectTimeout=10 "$HOST" "jq -e .done $R >/dev/null 2>&1" 2>/dev/null; then
    ssh "$HOST" cat "$R"
    if [[ -n $SCANLOG ]]; then
      echo "Couchbox-XXXX networks seen from $SCANNER (time, name, signal dBm):"
      grep -v ' none$' "$SCANLOG" || echo "  none"
    fi
    ssh "$HOST" "jq -e .ok $R >/dev/null"
    exit
  fi
  sleep 10
done
echo "$HOST: no result after the lifeline; check it over Ethernet" >&2
exit 1
