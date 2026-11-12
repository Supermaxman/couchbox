# Changelog

## [0.25.0](https://github.com/Supermaxman/couchbox/compare/v0.24.0...v0.25.0) (2026-11-12)


### New

* **boot:** a Couchbox boot screen with a progress bar, a log panel, and unlock problems explained ([#134](https://github.com/Supermaxman/couchbox/issues/134)) ([1bfa98c](https://github.com/Supermaxman/couchbox/commit/1bfa98c81a5f2a468089e59cfb628540c7f0fc62))
* **morning:** the morning show: a tile first on Home each morning plays a silent, captioned show made overnight ([#133](https://github.com/Supermaxman/couchbox/issues/133)) ([cbbc665](https://github.com/Supermaxman/couchbox/commit/cbbc66561021dcdf77375f982d1bdd2bfabfee7a))

## [0.24.0](https://github.com/Supermaxman/couchbox/compare/v0.23.0...v0.24.0) (2026-11-12)


### New

* **frigate:** While you were out: back home, a card on Home offers a short silent reel of what the cameras saw ([#131](https://github.com/Supermaxman/couchbox/issues/131)) ([93d805d](https://github.com/Supermaxman/couchbox/commit/93d805d59564ea3b628dcc166b9b367cce7ef069))


### Fixed

* **ci:** install-to-SSD loop check no longer races its own partition re-read ([#130](https://github.com/Supermaxman/couchbox/issues/130)) ([ddf7b21](https://github.com/Supermaxman/couchbox/commit/ddf7b217e99217a672c918acf6e38dc62c940b09))

## [0.23.0](https://github.com/Supermaxman/couchbox/compare/v0.22.0...v0.23.0) (2026-11-12)


### New

* **weather:** rain and warning pop-ups in the camera pop-up's corner ([#124](https://github.com/Supermaxman/couchbox/issues/124)) ([77b5ca8](https://github.com/Supermaxman/couchbox/commit/77b5ca8ad3b42cbf0f8b10095955bdefa91f1bf3))

## [0.22.0](https://github.com/Supermaxman/couchbox/compare/v0.21.0...v0.22.0) (2026-11-12)


### New

* **moments:** teach the TV something by showing it, then start it by voice, its home tile or the phone page ([#127](https://github.com/Supermaxman/couchbox/issues/127)) ([d3096ef](https://github.com/Supermaxman/couchbox/commit/d3096ef490ae18247099773ca913de17624684f6))

## [0.21.0](https://github.com/Supermaxman/couchbox/compare/v0.20.5...v0.21.0) (2026-11-12)


### New

* **voice:** ask the assistant about what's playing: who's this, what did I miss, skip to a moment ([#125](https://github.com/Supermaxman/couchbox/issues/125)) ([8364f7e](https://github.com/Supermaxman/couchbox/commit/8364f7ebffdcaa0b5a665b0f125feeac2e65488d))

## [0.20.5](https://github.com/Supermaxman/couchbox/compare/v0.20.4...v0.20.5) (2026-11-12)


### Fixed

* **youtube:** Refresh at the end of Home no longer crashes the app ([#122](https://github.com/Supermaxman/couchbox/issues/122)) ([4c50a74](https://github.com/Supermaxman/couchbox/commit/4c50a74269712fc23422d2274a7b4ec30ab69db0))

## [0.20.4](https://github.com/Supermaxman/couchbox/compare/v0.20.3...v0.20.4) (2026-11-11)


### Fixed

* **network:** the Wi-Fi reconnects by itself when the router stops answering; NetworkManager alone runs the network ([#120](https://github.com/Supermaxman/couchbox/issues/120)) ([424ea61](https://github.com/Supermaxman/couchbox/commit/424ea61e3adb486f78792f962b5858a64e26992d))

## [0.20.3](https://github.com/Supermaxman/couchbox/compare/v0.20.2...v0.20.3) (2026-11-09)


### Fixed

* **jellyfin:** the picture again when the web layer comes up white over the video ([#117](https://github.com/Supermaxman/couchbox/issues/117)) ([8563aa4](https://github.com/Supermaxman/couchbox/commit/8563aa477798a4265dcdcbe2639d29d5fbf8bf45))
* **youtube:** cards scrolled off a row's left edge fade out as in YouTube's TV app ([#119](https://github.com/Supermaxman/couchbox/issues/119)) ([3d6395d](https://github.com/Supermaxman/couchbox/commit/3d6395d798076996699f63e0f43ef3e7491210eb))
* **youtube:** Home's "Explore more topics" as YouTube's TV app has it: small topic cards, OK searches the topic ([#116](https://github.com/Supermaxman/couchbox/issues/116)) ([9b0a407](https://github.com/Supermaxman/couchbox/commit/9b0a407a82778e58d6d2ca659e6ca2e7d0bda94b))

## [0.20.2](https://github.com/Supermaxman/couchbox/compare/v0.20.1...v0.20.2) (2026-11-09)


### Fixed

* **youtube:** comments you can like (every comment opens), no silent first video, the end screen as YouTube's ([#113](https://github.com/Supermaxman/couchbox/issues/113)) ([bf869d1](https://github.com/Supermaxman/couchbox/commit/bf869d1b477d744912a289e98f29503798bc131a))
* **youtube:** Home ends with YouTube's Refresh tile again, and a new Home that came late is no longer thrown away ([#114](https://github.com/Supermaxman/couchbox/issues/114)) ([82f967c](https://github.com/Supermaxman/couchbox/commit/82f967c5d233f5344390c122efa82c060fc0cd27))

## [0.20.1](https://github.com/Supermaxman/couchbox/compare/v0.20.0...v0.20.1) (2026-11-09)


### Fixed

* **youtube:** a smoother app: the card menu opens whole, comments that hold still, no last frame of the video before ([#111](https://github.com/Supermaxman/couchbox/issues/111)) ([eac498c](https://github.com/Supermaxman/couchbox/commit/eac498c8133f4ee1a8d5ff5524435a54d8cde0c7))

## [0.20.0](https://github.com/Supermaxman/couchbox/compare/v0.19.1...v0.20.0) (2026-11-08)


### New

* **youtube:** channel pages as YouTube's TV app; Not interested again; a video opened from outside no longer stays paused ([#108](https://github.com/Supermaxman/couchbox/issues/108)) ([ff1b667](https://github.com/Supermaxman/couchbox/commit/ff1b66733f6b6fdd8ab52dd5110f818e810ab68d))
* **youtube:** one YouTube tile that opens Couchbox's own app, VacuumTube the fallback ([#110](https://github.com/Supermaxman/couchbox/issues/110)) ([7e0632c](https://github.com/Supermaxman/couchbox/commit/7e0632c5df757625050441585bf8d31ca048ed17))


### Fixed

* **youtube:** a video opened while another card was preloaded no longer stays paused at 0:00 ([ff1b667](https://github.com/Supermaxman/couchbox/commit/ff1b66733f6b6fdd8ab52dd5110f818e810ab68d))

## [0.19.1](https://github.com/Supermaxman/couchbox/compare/v0.19.0...v0.19.1) (2026-11-08)


### Fixed

* **youtube:** captions as YouTube shows them; the TV's refresh rate left alone in YouTube, and every switch said on screen ([#106](https://github.com/Supermaxman/couchbox/issues/106)) ([b3adaba](https://github.com/Supermaxman/couchbox/commit/b3adaba3a899a40077e129fb34d99b97fb4f32eb))
* **youtube:** the player's Up as the old app's: the controls, then the bar, then back to the video ([#105](https://github.com/Supermaxman/couchbox/issues/105)) ([c28442d](https://github.com/Supermaxman/couchbox/commit/c28442d43b133621403472251a4742f8dbb285de))

## [0.19.0](https://github.com/Supermaxman/couchbox/compare/v0.18.2...v0.19.0) (2026-11-06)


### New

* couchbox-record, screen recordings of the TV (and screenshots fixed for KWin's authorization) ([#103](https://github.com/Supermaxman/couchbox/issues/103)) ([f4e52ec](https://github.com/Supermaxman/couchbox/commit/f4e52ecb32a09a39ffcc68afd952dd6f5d2506ba))
* native YouTube app (beta tile): Leanback look, signed-in feeds, SponsorBlock and extras, casting, live DVR ([#102](https://github.com/Supermaxman/couchbox/issues/102)) ([340be10](https://github.com/Supermaxman/couchbox/commit/340be10388d0cf91fa730fed15e361590393c6a2))

## [0.18.2](https://github.com/Supermaxman/couchbox/compare/v0.18.1...v0.18.2) (2026-11-05)


### Fixed

* **youtube:** round 2: the box's key path, focus that stays put, Settings ([#100](https://github.com/Supermaxman/couchbox/issues/100)) ([15bc01e](https://github.com/Supermaxman/couchbox/commit/15bc01e3a2c8958a8acf471f54ac12458749488e))

## [0.18.1](https://github.com/Supermaxman/couchbox/compare/v0.18.0...v0.18.1) (2026-11-05)


### Fixed

* **youtube:** round 1 of the judge's findings against Leanback ([#98](https://github.com/Supermaxman/couchbox/issues/98)) ([8c93ff3](https://github.com/Supermaxman/couchbox/commit/8c93ff3d0d0b4bc316d811db18f1ec025d36bf6e))

## [0.18.0](https://github.com/Supermaxman/couchbox/compare/v0.17.0...v0.18.0) (2026-11-05)


### New

* **youtube:** Shorts, chapters, Description, comments, captions and the settings menu (M3) ([#93](https://github.com/Supermaxman/couchbox/issues/93)) ([77ea4b4](https://github.com/Supermaxman/couchbox/commit/77ea4b4705dc1344bc0dd000c3283a0feebe5320))


### Fixed

* **playback:** the refresh-rate guard runs in its own unit, so it outlives the app ([#95](https://github.com/Supermaxman/couchbox/issues/95)) ([6db9da3](https://github.com/Supermaxman/couchbox/commit/6db9da3178cdb2f8f42729170df2d497ffe19fae))

## [0.17.0](https://github.com/Supermaxman/couchbox/compare/v0.16.2...v0.17.0) (2026-11-05)


### New

* YouTube (beta), a native TV app built to replace VacuumTube (M1) ([#88](https://github.com/Supermaxman/couchbox/issues/88)) ([46be918](https://github.com/Supermaxman/couchbox/commit/46be918461e0c4be98eccabef6ce3287e687e18f))
* **youtube:** sign-in, accounts and the signed-in pages (M2) ([#90](https://github.com/Supermaxman/couchbox/issues/90)) ([7f82123](https://github.com/Supermaxman/couchbox/commit/7f8212361ed05a8ddc6fa5a07826336662b034b0))


### Fixed

* give the TV's refresh rate back when a paused video is out of sight ([#91](https://github.com/Supermaxman/couchbox/issues/91)) ([75d30e7](https://github.com/Supermaxman/couchbox/commit/75d30e75cf676378950b3a0c636f9a66ee267890))

## [0.16.2](https://github.com/Supermaxman/couchbox/compare/v0.16.1...v0.16.2) (2026-11-05)


### Fixed

* match the refresh rate in our own player (read mpv properties, trust the declared rate) ([#86](https://github.com/Supermaxman/couchbox/issues/86)) ([29e4d76](https://github.com/Supermaxman/couchbox/commit/29e4d76bad998d54e0b40113b381b260586e387e))

## [0.16.1](https://github.com/Supermaxman/couchbox/compare/v0.16.0...v0.16.1) (2026-11-05)


### Fixed

* **home:** updates reach the running home screen ([#85](https://github.com/Supermaxman/couchbox/issues/85)) ([66d9161](https://github.com/Supermaxman/couchbox/commit/66d916120efa186d2ad207a21fce181d03470d1f))

## [0.16.0](https://github.com/Supermaxman/couchbox/compare/v0.15.0...v0.16.0) (2026-11-05)


### New

* Continue watching on the home screen, "On this TV" in Search ([#83](https://github.com/Supermaxman/couchbox/issues/83)) ([83ec9d9](https://github.com/Supermaxman/couchbox/commit/83ec9d9752417720b3af85af1d513d568c5ecc49))
* playback settings: match the TV's refresh rate, night mode, surround passthrough ([#82](https://github.com/Supermaxman/couchbox/issues/82)) ([5989a48](https://github.com/Supermaxman/couchbox/commit/5989a48b4c09d12f4ac57bf1d4fed76e2a4bcb75))

## [0.15.0](https://github.com/Supermaxman/couchbox/compare/v0.14.0...v0.15.0) (2026-11-05)


### New

* **phone:** send to TV, a link from the phone opens in its app ([#80](https://github.com/Supermaxman/couchbox/issues/80)) ([6a82e16](https://github.com/Supermaxman/couchbox/commit/6a82e16dc4d804e22ab87e160f83c6b24d8e095a))
* **settings:** System shows what the box is doing right now ([#79](https://github.com/Supermaxman/couchbox/issues/79)) ([6bd3a39](https://github.com/Supermaxman/couchbox/commit/6bd3a3990676212aeeeff40b4a9c913de85eb62e))

## [0.14.0](https://github.com/Supermaxman/couchbox/compare/v0.13.0...v0.14.0) (2026-11-05)


### New

* couchbox-screenshot and couchbox-remote, to check the TV without anyone there ([#77](https://github.com/Supermaxman/couchbox/issues/77)) ([611a248](https://github.com/Supermaxman/couchbox/commit/611a24886f97d9f95eebdd3a0114f9fd61fe201b))

## [0.13.0](https://github.com/Supermaxman/couchbox/compare/v0.12.1...v0.13.0) (2026-11-05)


### New

* **frigate:** camera pop-up over whatever is playing ([#75](https://github.com/Supermaxman/couchbox/issues/75)) ([68b12df](https://github.com/Supermaxman/couchbox/commit/68b12df5d4c31c88f7ec9462967eaef983e4903e))

## [0.12.1](https://github.com/Supermaxman/couchbox/compare/v0.12.0...v0.12.1) (2026-11-04)


### Fixed

* holding OK on a tile opens its menu without picking the tile up; idle cleanup closes every app ([#73](https://github.com/Supermaxman/couchbox/issues/73)) ([5e3585d](https://github.com/Supermaxman/couchbox/commit/5e3585ddb8a57ce150d3329601c3f1b08df6a2b4))

## [0.12.0](https://github.com/Supermaxman/couchbox/compare/v0.11.3...v0.12.0) (2026-11-04)


### New

* quiet fan curve and lighter video drawing, both in Settings ([#71](https://github.com/Supermaxman/couchbox/issues/71)) ([22588aa](https://github.com/Supermaxman/couchbox/commit/22588aa70be0354d8105c3eeec99709639466af7))

## [0.11.3](https://github.com/Supermaxman/couchbox/compare/v0.11.2...v0.11.3) (2026-11-02)


### Fixed

* **memory:** give any app leaking open files its full limit, and log it ([#69](https://github.com/Supermaxman/couchbox/issues/69)) ([d374dcb](https://github.com/Supermaxman/couchbox/commit/d374dcb18387752a88a23658ad4142ef194cdbe7))

## [0.11.2](https://github.com/Supermaxman/couchbox/compare/v0.11.1...v0.11.2) (2026-11-02)


### Fixed

* **jellyfin:** raise the open-file limit so movies don't crash every few minutes ([#64](https://github.com/Supermaxman/couchbox/issues/64)) ([de33685](https://github.com/Supermaxman/couchbox/commit/de33685a84a4ae18f74a75fc4d202b8796efd6b7))
* **jellyfin:** silence shellcheck's POSIX ulimit warning (dash supports it) ([#67](https://github.com/Supermaxman/couchbox/issues/67)) ([4c6a10e](https://github.com/Supermaxman/couchbox/commit/4c6a10ed5d22375ada2e9585dc67b437277838f6))
* **media:** stop Jellyfin Desktop leaking a GL fence per frame ([#65](https://github.com/Supermaxman/couchbox/issues/65)) ([be61ca4](https://github.com/Supermaxman/couchbox/commit/be61ca4820a912ecc5c592989f50edc0a5dc2098))

## [0.11.1](https://github.com/Supermaxman/couchbox/compare/v0.11.0...v0.11.1) (2026-10-26)


### Fixed

* the remote's Back key goes back again (Movies, Twitch/Dropout/Nebula, Spotify) ([#61](https://github.com/Supermaxman/couchbox/issues/61)) ([e8645d0](https://github.com/Supermaxman/couchbox/commit/e8645d0d54b3cf9b4e1e6f344b96bb622230a5da))
* **ui:** focused cards and rows no longer get cut off at the edges ([#58](https://github.com/Supermaxman/couchbox/issues/58)) ([63d7600](https://github.com/Supermaxman/couchbox/commit/63d76008bc7581a96e73af9d7eb77ad923f9ea1c))
* **ui:** sharp icons, posters and thumbnails when the TV runs scaled ([#62](https://github.com/Supermaxman/couchbox/issues/62)) ([23a64a2](https://github.com/Supermaxman/couchbox/commit/23a64a27df6d37ce368a5fc2b403ec08b32106d1))

## [0.11.0](https://github.com/Supermaxman/couchbox/compare/v0.10.1...v0.11.0) (2026-10-26)


### New

* **remote:** Play/Pause, Rewind and Fast-forward control whatever is playing ([#59](https://github.com/Supermaxman/couchbox/issues/59)) ([8adba9b](https://github.com/Supermaxman/couchbox/commit/8adba9b5421d2cf918701fff518167f73bf6bf0b))


### Fixed

* **settings:** focused rows no longer grow past the list's edges ([#55](https://github.com/Supermaxman/couchbox/issues/55)) ([8e8ec1a](https://github.com/Supermaxman/couchbox/commit/8e8ec1ac292d91721d39d97eebaa34a94666281d))
* **spotify:** sharp covers, and Now Playing shows the art, artists and length ([#57](https://github.com/Supermaxman/couchbox/issues/57)) ([1f99073](https://github.com/Supermaxman/couchbox/commit/1f9907384f5389a6996de9fa814bbc4c000a8598))
* **twitch:** stop signing out after an hour ([#56](https://github.com/Supermaxman/couchbox/issues/56)) ([468993c](https://github.com/Supermaxman/couchbox/commit/468993c07f9b3e9980edeb4e393673534f8e9c9a))

## [0.10.1](https://github.com/Supermaxman/couchbox/compare/v0.10.0...v0.10.1) (2026-10-26)


### Fixed

* **spotify:** say when Spotify refuses the Soloist key ([#53](https://github.com/Supermaxman/couchbox/issues/53)) ([845dfa6](https://github.com/Supermaxman/couchbox/commit/845dfa69a120ea65f23c3c05ad03f3c836613804))

## [0.10.0](https://github.com/Supermaxman/couchbox/compare/v0.9.1...v0.10.0) (2026-10-26)


### New

* **weather:** air quality and pollen ([#52](https://github.com/Supermaxman/couchbox/issues/52)) ([24d1ef6](https://github.com/Supermaxman/couchbox/commit/24d1ef60d7330dcbf6c97d7e3cdf1e88f44ca8fe))
* **weather:** rain radar page ([#49](https://github.com/Supermaxman/couchbox/issues/49)) ([f2f9035](https://github.com/Supermaxman/couchbox/commit/f2f903572aa1db81f0b9fd064e1be61d080e3f52))

## [0.9.1](https://github.com/Supermaxman/couchbox/compare/v0.9.0...v0.9.1) (2026-10-26)


### Fixed

* **voice:** send movie facts to the movies tool, not the model's memory ([#47](https://github.com/Supermaxman/couchbox/issues/47)) ([8e8fc79](https://github.com/Supermaxman/couchbox/commit/8e8fc794416e89a5a20319557a9ec0d0d59e5196))

## [0.9.0](https://github.com/Supermaxman/couchbox/compare/v0.8.0...v0.9.0) (2026-10-26)


### New

* **movies:** Movies & TV, an IMDb-style guide to movies, shows and people ([#42](https://github.com/Supermaxman/couchbox/issues/42)) ([747abbb](https://github.com/Supermaxman/couchbox/commit/747abbbefa62e828a9e65e4731c41ab3c6257df6))

## [0.8.0](https://github.com/Supermaxman/couchbox/compare/v0.7.0...v0.8.0) (2026-10-26)


### New

* **maps:** a Maps app for the TV: drive times, directions and when to leave ([#41](https://github.com/Supermaxman/couchbox/issues/41)) ([fca7a56](https://github.com/Supermaxman/couchbox/commit/fca7a5620a550264992434c1633122792475123d))
* **spotify:** a native Spotify app, played on the TV by Spotify's own player ([#44](https://github.com/Supermaxman/couchbox/issues/44)) ([e5a3a7a](https://github.com/Supermaxman/couchbox/commit/e5a3a7a91bad1f1ed7f46d6c96e2c65c72370a1f))

## [0.7.0](https://github.com/Supermaxman/couchbox/compare/v0.6.0...v0.7.0) (2026-10-26)


### New

* **search:** Google from the couch, with a reader and assistant summaries ([#39](https://github.com/Supermaxman/couchbox/issues/39)) ([751e96a](https://github.com/Supermaxman/couchbox/commit/751e96ad748b836eb9bdc357186c7ded67046ecf))

## [0.6.0](https://github.com/Supermaxman/couchbox/compare/v0.5.3...v0.6.0) (2026-10-26)


### New

* **weather:** a Weather app for the TV, and the assistant's weather tool ([#37](https://github.com/Supermaxman/couchbox/issues/37)) ([fef7cd5](https://github.com/Supermaxman/couchbox/commit/fef7cd50dd98ae4942791a2c3aa22e501ac56e11))

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
