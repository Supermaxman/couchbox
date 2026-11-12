#!/bin/bash
# shellcheck disable=SC2154  # initdir, systemdsystemunitdir, SYSTEMCTL come from dracut
# Couchbox dracut module: the boot screen's side of the initrd. Plymouth's own module brings
# the theme (system/plymouth/couchbox); this adds what tells it where the boot is
# (couchbox-boot-status), the last boots' pace, the fonts it draws with, and the journal feed
# for its log panel. Installed to /usr/lib/dracut/modules.d/89couchbox-boot.

check() {
    require_binaries plymouthd plymouth journalctl || return 1
    [[ -f /usr/share/plymouth/themes/couchbox/couchbox.plymouth ]] || return 1
    return 0
}

depends() {
    echo plymouth systemd
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
}
