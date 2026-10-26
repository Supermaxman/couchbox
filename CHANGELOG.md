# Changelog

## [0.5.3](https://github.com/Supermaxman/couchbox/compare/v0.5.2...v0.5.3) (2026-10-26)


### Fixed

* **frigate:** play from the timeline, and keep its picture in step ([#35](https://github.com/Supermaxman/couchbox/issues/35)) ([15ff7e7](https://github.com/Supermaxman/couchbox/commit/15ff7e784734927a70e76f6b6027690fdfa955af))

## [0.5.2](https://github.com/Supermaxman/couchbox/compare/v0.5.1...v0.5.2) (2026-10-26)


### Fixed

* **frigate:** stop the crash after a few minutes of video; timeline, icons, roomier cards ([#34](https://github.com/Supermaxman/couchbox/issues/34)) ([e5fc125](https://github.com/Supermaxman/couchbox/commit/e5fc12589ca16cb1ac9c42d46353a886e8dae9f7))
* **phone:** pair by typed code, and type slowly enough not to drop keys ([#32](https://github.com/Supermaxman/couchbox/issues/32)) ([9e39ab2](https://github.com/Supermaxman/couchbox/commit/9e39ab288d9620699a1ae78c0f99c829fc6be75e))

## [0.5.1](https://github.com/Supermaxman/couchbox/compare/v0.5.0...v0.5.1) (2026-10-26)


### Fixed

* **frigate:** no "Sign in to Frigate." error on the first sign-in screen ([#30](https://github.com/Supermaxman/couchbox/issues/30)) ([c748b7a](https://github.com/Supermaxman/couchbox/commit/c748b7a2e7448cdf1e38caa36dc3682d56be553b))

## [0.5.0](https://github.com/Supermaxman/couchbox/compare/v0.4.9...v0.5.0) (2026-10-26)


### New

* **frigate:** a native TV app for Frigate cameras: live dashboard, full-screen live, review and recordings ([#28](https://github.com/Supermaxman/couchbox/issues/28)) ([f029100](https://github.com/Supermaxman/couchbox/commit/f0291001d80d1b374fc3c7c76e10c0ec83611aad))

## [0.4.9](https://github.com/Supermaxman/couchbox/compare/v0.4.8...v0.4.9) (2026-10-26)


### Fixed

* **input:** find Couchbox's helpers for the remote's Power, Input and Home buttons ([#26](https://github.com/Supermaxman/couchbox/issues/26)) ([120c350](https://github.com/Supermaxman/couchbox/commit/120c350d98c0d653a9624e9d7bca6ad4a12a7024))

## [0.4.8](https://github.com/Supermaxman/couchbox/compare/v0.4.7...v0.4.8) (2026-10-26)


### Fixed

* **updater:** on the stable channel, look past a latest release that is still being published ([#24](https://github.com/Supermaxman/couchbox/issues/24)) ([8612c2d](https://github.com/Supermaxman/couchbox/commit/8612c2d64c01ddc5ab2abb98179744c80350ae03))

## [0.4.7](https://github.com/Supermaxman/couchbox/compare/v0.4.6...v0.4.7) (2026-10-26)


### Fixed

* **updater:** skip a release whose files are still being published ([#22](https://github.com/Supermaxman/couchbox/issues/22)) ([0626e76](https://github.com/Supermaxman/couchbox/commit/0626e763bf636acf236f0f6a513c0b69c1469e43))

## [0.4.6](https://github.com/Supermaxman/couchbox/compare/v0.4.5...v0.4.6) (2026-10-26)


### Fixed

* **updater:** don't let the package upgrade stop the updater's own unit ([#18](https://github.com/Supermaxman/couchbox/issues/18)) ([1cbe7f2](https://github.com/Supermaxman/couchbox/commit/1cbe7f2bfb1d22ca6768d863222c0fdec812205f))

## [0.4.5](https://github.com/Supermaxman/couchbox/compare/v0.4.4...v0.4.5) (2026-10-26)


### Fixed

* **twitch:** keep the sign-in: finish a code entered after Back, survive token rotation, refresh weekly ([#16](https://github.com/Supermaxman/couchbox/issues/16)) ([f4e40fe](https://github.com/Supermaxman/couchbox/commit/f4e40fead9469606288969ce37136b0343750f02))

## [0.4.4](https://github.com/Supermaxman/couchbox/compare/v0.4.3...v0.4.4) (2026-10-25)


### Fixed

* **voice:** pass loadScript's signature explicitly so KWin picks the (ss) overload ([#14](https://github.com/Supermaxman/couchbox/issues/14)) ([0cc9ed8](https://github.com/Supermaxman/couchbox/commit/0cc9ed80f514f626a932392acaba8caff33b776d))

## [0.4.3](https://github.com/Supermaxman/couchbox/compare/v0.4.2...v0.4.3) (2026-10-25)


### Fixed

* **install:** rollback finishes when there's no new boot image to adjust ([4bafdd0](https://github.com/Supermaxman/couchbox/commit/4bafdd03f995dfe9dadbc9673b5db769f9bbfd61))

## [0.4.2](https://github.com/Supermaxman/couchbox/compare/v0.4.1...v0.4.2) (2026-10-25)


### Fixed

* **install:** a boot image that can't be built keeps mtv's boot setup and the conversion carries on ([dd90fcb](https://github.com/Supermaxman/couchbox/commit/dd90fcbba8298c872c457548c1ffa6558c2afe14))
* **install:** rehearsals on an EFI host let flash-kernel run ([17c8782](https://github.com/Supermaxman/couchbox/commit/17c87826b1a643c52c7608c466f66c85a5309a95))

## [0.4.1](https://github.com/Supermaxman/couchbox/compare/v0.4.0...v0.4.1) (2026-10-25)


### Fixed

* **ci:** image test checks couchbox-input's key map loads (containers have no /dev/uinput) ([b8c74f2](https://github.com/Supermaxman/couchbox/commit/b8c74f22faf5b8fca51ed5c30bb42404d19c93b9))

## [0.4.0](https://github.com/Supermaxman/couchbox/compare/v0.3.0...v0.4.0) (2026-10-25)


### New

* **install:** convert the mtv prototype in place (installer/convert-mtv.sh); keep SSH and Tailscale when installing over them ([58dd612](https://github.com/Supermaxman/couchbox/commit/58dd6122fb0ec3872bb763603a32db24c01db7c0))


### Fixed

* **apps:** stop the sign-in import's headless browser for real ([6e6aa84](https://github.com/Supermaxman/couchbox/commit/6e6aa841eeaf7856720ce75cda14a7aab81bb429))
* **input:** use the shipped key map when the household has none ([490792f](https://github.com/Supermaxman/couchbox/commit/490792f79a5c33686b53306197b6dd33b9030052))
* **install:** convert-mtv preflight builds and checks the new boot image aside; theme on install ([7c7457a](https://github.com/Supermaxman/couchbox/commit/7c7457aa456c4ca809747e50039ffcbf982b7187))

## [0.3.0](https://github.com/Supermaxman/couchbox/compare/v0.2.0...v0.3.0) (2026-10-25)


### New

* **voice:** app tools follow the home row, Dropout/2nd Try/Nebula/Twitch tools, and the app in front as context ([6487702](https://github.com/Supermaxman/couchbox/commit/64877024b6b87ff00304f5c01cf418661daafa1f))


### Fixed

* **voice:** newest episodes in one step, without a search first ([a0c96e0](https://github.com/Supermaxman/couchbox/commit/a0c96e04365eb2d15c82be3d83e93dc767c1b9a5))

## [0.2.0](https://github.com/Supermaxman/couchbox/compare/v0.1.0...v0.2.0) (2026-10-25)


### New

* **setup:** install to the SSD from a USB stick, and the phone as the remote from the first screen ([c43f5d6](https://github.com/Supermaxman/couchbox/commit/c43f5d6dce97f3984a19fc46870e2a319261a5a1))


### Fixed

* **network:** Wi-Fi set in Raspberry Pi Imager is run by NetworkManager ([3f6f098](https://github.com/Supermaxman/couchbox/commit/3f6f0980961e0f685b87264a07e31464bb0cfe36))
* **setup:** don't open the setup Wi-Fi while a saved network may still be joining ([da67886](https://github.com/Supermaxman/couchbox/commit/da67886ab6b6d9b4641e2f6211681af4b347c89d))


### Docs

* step-by-step install guide (USB stick, TV, phone or remote) and the fresh-hardware run sheet ([f0b450c](https://github.com/Supermaxman/couchbox/commit/f0b450c2d6e5033b480609da0d1175dfad2340b1))
* when the setup Wi-Fi opens ([fe56fc0](https://github.com/Supermaxman/couchbox/commit/fe56fc0c467b000542711511ac0b3f2071f0c076))

## 0.1.0 (2026-10-25)


### New

* 512 MB video memory and tuned Jellyfin player settings, as on the prototype ([19c100d](https://github.com/Supermaxman/couchbox/commit/19c100d2a1f6cb5a622507c9516c8742b678d3c9))
* Settings app, CI workflow, encryption loop test, Debian package ([785aa29](https://github.com/Supermaxman/couchbox/commit/785aa29e19362d0649a2c27bb7c5829abf122b7a))
* settings service, CLI, updater, encryption, home screen builder; port the TV apps ([9f9c8d9](https://github.com/Supermaxman/couchbox/commit/9f9c8d91e4ac632d25c2ae463e6d9fa725ef20b2))
* setup wizard, live home row with tile options, CI fixes ([67e2ad2](https://github.com/Supermaxman/couchbox/commit/67e2ad260b89a3b23c9cca9be647f8c730df8060))


### Fixed

* **image:** create /boot/firmware before mounting the boot partition ([2a79c01](https://github.com/Supermaxman/couchbox/commit/2a79c01d3cd492c3a5f3cb73eb648a813f024895))
* **image:** drop unneeded firmware, prebuilt locales and cloud SDKs; no SIGPIPE ([bbf6dee](https://github.com/Supermaxman/couchbox/commit/bbf6dee5ebb720e156ed5ccce95cec004f8d0352))
* **image:** keep the Broadcom Wi-Fi firmware the Pi 5 uses; test for it ([7116e8a](https://github.com/Supermaxman/couchbox/commit/7116e8a3b7485c9718a11140f6dc474c936ab85b))
* **image:** size report stays on the root filesystem ([5ab8068](https://github.com/Supermaxman/couchbox/commit/5ab806874f47264f2cd9bb9feff43deacb4659f4))
* **image:** smaller image (zeroed free space, no docs, no unused firmware) ([b6ca34a](https://github.com/Supermaxman/couchbox/commit/b6ca34a1cdc339d3af074445881d75ebe9223277))
* **phone:** serve the page even without a virtual keyboard device; test reports every unit ([b87bb54](https://github.com/Supermaxman/couchbox/commit/b87bb546ca44e89f02dd8a864f31144f120272ef))
* TV control and theme follow settings ([e2f488b](https://github.com/Supermaxman/couchbox/commit/e2f488b92a9bcd32d93d3e8a707c5c0ac4e8bf1c))


### Docs

* Couchbox plan and design ([3068d31](https://github.com/Supermaxman/couchbox/commit/3068d3147039872cdc53f40533fe3c0d074ef86c))
* image progress ([0b45e29](https://github.com/Supermaxman/couchbox/commit/0b45e295379ce73b2138be65cafcd744b503dcb2))
* install guide, progress, project icon ([701a291](https://github.com/Supermaxman/couchbox/commit/701a2910a5a656d2b336eaa1e1f13f6d3be9beac))
