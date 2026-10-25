#!/bin/bash
# shellcheck disable=SC2154  # moddir, initdir, systemdsystemunitdir, SYSTEMCTL come from dracut
# Couchbox dracut module: Wi-Fi in the initrd, so Clevis can reach a Tang server over Wi-Fi
# as well as Ethernet. Credentials come from /etc/couchbox/luks/initrd-wpa.conf (root-only,
# written by couchbox.encryption from the current Wi-Fi, hashed PSK). Installed to
# /usr/lib/dracut/modules.d/90couchbox; added to the initrd only with network unlock (Tang).

check() {
    require_binaries wpa_supplicant || return 1
    [[ -f /etc/couchbox/luks/initrd-wpa.conf ]] || return 1
    return 0
}

depends() {
    echo systemd-networkd
}

installkernel() {
    instmods brcmfmac brcmfmac-cyw cfg80211
}

install() {
    inst_multiple wpa_supplicant
    inst_simple /etc/couchbox/luks/initrd-wpa.conf /etc/wpa_supplicant/couchbox-initrd.conf
    inst_simple "$moddir/couchbox-initrd-wifi.service" "$systemdsystemunitdir/couchbox-initrd-wifi.service"
    inst_simple "$moddir/10-couchbox-initrd.network" /etc/systemd/network/10-couchbox-initrd.network
    inst_simple "$moddir/wait-online-any.conf" \
        "$systemdsystemunitdir/systemd-networkd-wait-online.service.d/50-couchbox-any.conf"
    # Pi 5 Wi-Fi firmware (Ubuntu's 12-raspi-brcmfmac.conf stops at the Pi 4) and the
    # regulatory database, so 5 GHz channels work before the root is unlocked.
    local f
    for f in /usr/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.* \
             /usr/lib/firmware/brcm/brcmfmac43455-sdio.bin.zst \
             /usr/lib/firmware/brcm/brcmfmac43455-sdio.clm_blob.zst \
             /usr/lib/firmware/cypress/cyfmac43455-sdio* \
             /usr/lib/firmware/regulatory.db*; do
        [[ -e $f ]] && inst_simple "$f"
    done
    $SYSTEMCTL -q --root "$initdir" enable couchbox-initrd-wifi.service
}
