#!/bin/bash
# shellcheck disable=SC2154  # initdir, moddir, systemdsystemunitdir, udevrulesdir, SYSTEMCTL come from dracut
# Couchbox dracut module: the boot screen's side of the initrd. Plymouth's own module brings
# the theme (system/plymouth/couchbox); this adds what tells it where the boot is
# (couchbox-boot-status), the last boots' pace, the fonts it draws with, and the journal feed
# for its log panel. With a paired Bluetooth remote it also brings Bluetooth (dracut's own
# module), the remote's pairing, and couchbox-boot-remote, so the remote works on the boot
# screen: the log, and the disk passphrase on its on-screen keyboard. Installed to
# /usr/lib/dracut/modules.d/89couchbox-boot.

check() {
    require_binaries plymouthd plymouth journalctl || return 1
    [[ -f /usr/share/plymouth/themes/couchbox/couchbox.plymouth ]] || return 1
    return 0
}

# The Bluetooth devices this box is paired with (their pairing directories), if bluetoothd and
# evtest are here to use them.
paired() {
    [[ -x /usr/libexec/bluetooth/bluetoothd || -x /usr/lib/bluetooth/bluetoothd ]] || return 1
    command -v evtest > /dev/null || return 1
    local f found=1
    for f in /var/lib/bluetooth/*/*/info; do
        if grep -qsE '^\[(LongTermKey|PeripheralLongTermKey|SlaveLongTermKey|LinkKey)\]' "$f"; then
            echo "${f%/info}"
            found=0
        fi
    done
    return $found
}

depends() {
    if paired > /dev/null; then echo plymouth systemd bluetooth; else echo plymouth systemd; fi
}

installkernel() {
    # the Pi's Bluetooth is on a UART; remotes that pair over Bluetooth LE come in through uhid
    # (dracut's bluetooth module brings the rest)
    paired > /dev/null && hostonly='' instmods hci_uart uhid hid-generic
    return 0
}

install() {
    inst_multiple cat ls mkdir mv sleep journalctl
    inst_simple /usr/lib/couchbox/bin/couchbox-boot-status /usr/bin/couchbox-boot-status
    [[ -f /var/lib/couchbox/boot-pace ]] && inst_simple /var/lib/couchbox/boot-pace /etc/couchbox-boot-pace
    # Inter (as on the home screen) and a monospace face for the log, with fontconfig's setup
    local f
    for f in /usr/share/fonts/opentype/inter/Inter-Regular.otf /usr/share/fonts/opentype/inter/Inter-Medium.otf \
             /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf; do
        [[ -e $f ]] && inst_simple "$f"
    done
    inst_multiple -o /etc/fonts/fonts.conf /etc/fonts/conf.d/*
    local u
    for u in couchbox-boot-begin couchbox-boot-net couchbox-boot-unlocked couchbox-boot-log; do
        inst_simple "$moddir/$u.service" "$systemdsystemunitdir/$u.service"
        $SYSTEMCTL -q --root "$initdir" enable "$u.service"
    done

    # The remote. Its pairing goes into the initrd, which sits unencrypted on the boot partition
    # (as the Wi-Fi password does when Wi-Fi at boot is on). The adapter's own settings come too.
    local devs d
    devs=$(paired) || return 0
    inst_multiple evtest mkfifo /usr/lib/systemd/systemd-reply-password
    inst_simple /usr/lib/couchbox/bin/couchbox-boot-remote /usr/bin/couchbox-boot-remote
    for d in $devs; do
        inst_multiple -o "$d"/* "${d%/*}/cache/${d##*/}" "${d%/*}/settings" "${d%/*}/identity"
    done
    inst_simple "$moddir/couchbox-boot-remote.service" "$systemdsystemunitdir/couchbox-boot-remote.service"
    inst_simple "$moddir/couchbox-boot-remote@.service" "$systemdsystemunitdir/couchbox-boot-remote@.service"
    inst_simple "$moddir/90-couchbox-boot-remote.rules" "$udevrulesdir/90-couchbox-boot-remote.rules"
    $SYSTEMCTL -q --root "$initdir" enable couchbox-boot-remote.service
}
