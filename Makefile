# Couchbox: lay the files out for the package (make install DESTDIR=...) or a dev tree
# (make stage: build/share, for running apps from the repo with COUCHBOX_SHARE=build/share).
DESTDIR ?=
PY := $(DESTDIR)/usr/lib/python3/dist-packages
SHARE := $(DESTDIR)/usr/share/couchbox
LIBBIN := $(DESTDIR)/usr/lib/couchbox/bin
SYSD := $(DESTDIR)/usr/lib/systemd

.PHONY: install stage test lint clean deb

install:
	install -d $(PY) $(SHARE) $(LIBBIN) $(DESTDIR)/usr/bin
	cp -r src/couchbox $(PY)/
	find $(PY)/couchbox -name __pycache__ -prune -exec rm -rf {} +
	install -m 755 bin/couchbox-* $(LIBBIN)/
	printf '#!/usr/bin/python3\nfrom couchbox.cli import main\nmain()\n' > $(DESTDIR)/usr/bin/couchbox
	chmod 755 $(DESTDIR)/usr/bin/couchbox
	$(MAKE) share SHAREDIR=$(SHARE)
	install -d $(SYSD)/system $(SYSD)/user $(SYSD)/logind.conf.d $(SYSD)/journald.conf.d \
	  $(SYSD)/user/plasma-plasmashell.service.d $(DESTDIR)/usr/lib/udev/rules.d $(DESTDIR)/usr/lib/sysctl.d \
	  $(DESTDIR)/usr/lib/tmpfiles.d $(DESTDIR)/usr/lib/environment.d $(DESTDIR)/usr/lib/sddm/sddm.conf.d \
	  $(DESTDIR)/usr/lib/dracut/modules.d/90couchbox $(DESTDIR)/usr/share/applications
	install -m 644 system/systemd/* $(SYSD)/system/
	install -m 644 system/user/* $(SYSD)/user/
	install -m 644 system/plasmashell/couchbox.conf $(SYSD)/user/plasma-plasmashell.service.d/
	install -m 644 system/logind/* $(SYSD)/logind.conf.d/
	install -m 644 system/journald/* $(SYSD)/journald.conf.d/
	install -m 644 system/udev/* $(DESTDIR)/usr/lib/udev/rules.d/
	install -m 644 system/sysctl/* $(DESTDIR)/usr/lib/sysctl.d/
	install -m 644 system/tmpfiles/couchbox.conf $(DESTDIR)/usr/lib/tmpfiles.d/
	install -m 644 system/environment.d/* $(DESTDIR)/usr/lib/environment.d/
	install -m 644 system/sddm/* $(DESTDIR)/usr/lib/sddm/sddm.conf.d/
	install -m 644 system/dracut/90couchbox/* $(DESTDIR)/usr/lib/dracut/modules.d/90couchbox/
	chmod 755 $(DESTDIR)/usr/lib/dracut/modules.d/90couchbox/module-setup.sh
	install -m 644 system/applications/*.desktop $(DESTDIR)/usr/share/applications/

# share/: data, apps (QML), home screen, theme, tiles, web extension, keys
share:
	install -d $(SHAREDIR)/ui $(SHAREDIR)/shell $(SHAREDIR)/theme $(SHAREDIR)/tiles $(SHAREDIR)/input \
	  $(SHAREDIR)/keys $(SHAREDIR)/chromium $(SHAREDIR)/web-extension
	install -m 644 data/schema.json $(SHAREDIR)/
	cp -r data/apps $(SHAREDIR)/
	install -m 644 data/input/* $(SHAREDIR)/input/
	cp -r ui/. $(SHAREDIR)/ui/
	cp -r shell/home $(SHAREDIR)/shell/
	cp -r shell/theme/. $(SHAREDIR)/theme/
	cp -r shell/theme/tiles/. $(SHAREDIR)/tiles/
	install -m 644 system/chromium/policies.json $(SHAREDIR)/chromium/
	install -m 644 system/web-extension/* $(SHAREDIR)/web-extension/
	install -m 644 system/keys/allowed_signers $(SHAREDIR)/keys/
	find $(SHAREDIR) -name __pycache__ -prune -exec rm -rf {} +

stage:
	rm -rf build/share
	$(MAKE) share SHAREDIR=$(CURDIR)/build/share

test:
	python3 -m pytest

lint:
	ruff check src tests bin/couchbox-firstboot bin/couchbox-updater
	shellcheck -x $$(grep -l '^#!/.*sh' bin/* system/dracut/90couchbox/*.sh installer/*.sh image/*.sh 2>/dev/null)

deb:
	dpkg-buildpackage -us -uc -b

clean:
	rm -rf build debian/couchbox debian/.debhelper debian/files debian/*.substvars debian/*.log
