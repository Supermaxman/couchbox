#!/bin/sh
# Render every Settings page and the setup wizard off screen (demo mode: a fake system),
# into $1 (default build/shots). Fails on QML errors, and on a focused card that grows past whatever
# clips it (src/couchbox/qtcheck.py).
set -eu
OUT=${1:-build/shots}
make -s stage >/dev/null
mkdir -p "$OUT"
export COUCHBOX_SHARE="$PWD/build/share" PYTHONPATH="$PWD/src" QT_QPA_PLATFORM=offscreen LANG=C.UTF-8
fail=0
shot() {  # shot NAME APP ARGS...
  name=$1; app=$2; shift 2
  case "$name" in ${ONLY:-}*) ;; *) return 0;; esac   # ONLY=spotify: just those
  if ! python3 "bin/$app" --demo --shot "$OUT/$name.png" "$@" >"$OUT/$name.log" 2>&1 || grep -qE "qrc:|file:.*(Error|TypeError|ReferenceError)|is not defined|Cannot assign|Unable to assign|focus-clip:" "$OUT/$name.log"; then
    echo "!! $name"; grep -E "Error|error|not defined|Cannot|focus-clip:" "$OUT/$name.log" | head -5; fail=1
  else
    echo "ok $name"
  fi
}
for p in network home apps voice remote display time access security updates system; do
  shot "settings-$p" couchbox-settings --page "$p" --in
done
# the Frigate app with made-up cameras: dashboard, a camera full screen (and its strip),
# review, a recording, the timeline (the group's lanes, one camera), sign-in
shot frigate-live couchbox-frigate
shot frigate-camera couchbox-frigate --keys down,ok
shot frigate-camera-strip couchbox-frigate --keys down,ok,down
shot frigate-review couchbox-frigate --open review
shot frigate-recording couchbox-frigate --open review --keys right,ok
shot frigate-timeline couchbox-frigate --open timeline
shot frigate-timeline-camera couchbox-frigate --open timeline:driveway
shot frigate-signin couchbox-frigate --signin
# its Pop-ups page (the top, a camera switched off, scrolled to the last rows), and the pop-up itself over a
# stand-in for the TV (a matching alert; a test, small, bottom left; snapshots, large)
d30=down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down,down
shot frigate-popups couchbox-frigate --open popups
shot frigate-popups-camera couchbox-frigate --open popups --keys down,down,down,down,ok
shot frigate-popups-last couchbox-frigate --open popups --keys $d30
shot frigate-popup couchbox-frigate-popup
shot frigate-popup-test couchbox-frigate-popup --test --size small --position bottom-left
# weather in the same corner: rain due soon, an official warning, snow in a small one
shot weather-popup-rain couchbox-frigate-popup --weather rain
shot weather-popup-warning couchbox-frigate-popup --weather warning
shot weather-popup-snow couchbox-frigate-popup --weather snow --size small --position bottom-left
shot frigate-popup-snapshots couchbox-frigate-popup --picture snapshots --size large --position top-left
# the Weather app with a made-up fortnight: Today, the 14 days, a day in detail (from an hour
# picked on Today, and from the list), the alert, the radar (playing; paused a frame back, zoomed in)
shot weather-today couchbox-weather
shot weather-week couchbox-weather --open week --keys down,down
shot weather-day couchbox-weather --open day:tomorrow
shot weather-day-hour couchbox-weather --keys right,right,right,ok
shot weather-alerts couchbox-weather --open alerts
shot weather-radar couchbox-weather --open radar
shot weather-radar-paused couchbox-weather --open radar --keys up,ok,left,left
# Search with made-up pages: the start page, results (with the AI answer and On this TV), On this
# TV in focus, the toolbar, the reader and a summary
shot search-start couchbox-search
shot search-results couchbox-search --open "search:eiffel tower height"
shot search-on-this-tv couchbox-search --open "search:eiffel tower height" --keys up,right
shot search-toolbar couchbox-search --open "search:eiffel tower height" --keys up,up
shot search-reader couchbox-search --open reader
shot search-summary couchbox-search --open summary
# the Spotify app with made-up music: home, search, library, an album, a playlist Spotify won't
# list, an artist, Now Playing, the song menu, adding to a playlist, setup
shot spotify-home couchbox-spotify
shot spotify-search couchbox-spotify --open search:midnight --keys down
shot spotify-library couchbox-spotify --open library
shot spotify-album couchbox-spotify --open album:al0 --keys right,right,right,down
shot spotify-playlist-made-for-you couchbox-spotify --open playlist:pl10
shot spotify-artist couchbox-spotify --open artist:ar1 --keys down
shot spotify-now-playing couchbox-spotify --open now
shot spotify-menu couchbox-spotify --open menu
shot spotify-add-to-playlist couchbox-spotify --open picker
shot spotify-setup couchbox-spotify --setup --keys down,down,down,down
# Maps with made-up places (OpenStreetMap, then as Google: traffic, transit): places and drive
# times, search, directions (routes, the turns, the map moving), leave by, a place's actions
shot maps-places couchbox-maps
shot maps-place-actions couchbox-maps --keys right,ok
shot maps-search couchbox-maps --open search:ferry
shot maps-directions couchbox-maps --open 'to:{"place":{"name":"Ferry Building","address":"1 Ferry Building, San Francisco","lat":37.7955,"lon":-122.3937}}'
shot maps-directions-steps couchbox-maps --open 'to:{"place":{"name":"Ferry Building","lat":37.7955,"lon":-122.3937}}' --keys down,down,down,down
shot maps-directions-map couchbox-maps --open 'to:{"place":{"name":"Ferry Building","lat":37.7955,"lon":-122.3937}}' --keys right,ok,up
export COUCHBOX_MAPS_DEMO_GOOGLE=1
shot maps-google-places couchbox-maps
shot maps-google-transit couchbox-maps --open 'to:{"place":{"name":"Airport","lat":37.6213,"lon":-122.379},"mode":"transit"}'
shot maps-leave-by couchbox-maps --open 'leave:{"place":{"name":"Airport","address":"San Francisco International Airport","lat":37.6213,"lon":-122.379}}'
unset COUCHBOX_MAPS_DEMO_GOOGLE
# the home screen's Continue watching row under the apps (made-up items): the apps in focus, a
# card in focus, and without anything to continue
shot home-continue couchbox-ontv
shot home-continue-card couchbox-ontv --keys down,right
shot home-continue-empty couchbox-ontv --empty
# Movies & TV with made-up titles: home, a movie, a show (and its seasons row), a season,
# a person (known for, a filmography), search, the top-rated grid
shot movies-home couchbox-movies
shot movies-movie couchbox-movies --open movie:101
shot movies-movie-cast couchbox-movies --open movie:101 --keys down
shot movies-show couchbox-movies --open tv:201 --keys down,down,down
shot movies-season couchbox-movies --open season:201:1
shot movies-person couchbox-movies --open person:303
shot movies-person-work couchbox-movies --open person:303:directing
shot movies-search couchbox-movies --open search:harbor
shot movies-top couchbox-movies --open top:movie
# YouTube with made-up videos: Home, the guide open, a tab, Search (the keys, typing),
# results and down to the chips, a channel, the player (controls, the related rows, the bar),
# Settings
shot yt-home couchbox-yt
shot yt-guide couchbox-yt --keys left
# a row scrolled two cards: the passed card at 10% under the guide's fade; that row under the current one (passed cards gone)
shot yt-home-passed couchbox-yt --keys right,right
shot yt-home-passed-below couchbox-yt --keys down,right,right,up
# Home's end: "Explore more topics" (under the current row, current, its second card), YouTube's
# Refresh tile (current), and Home again after OK on it
shot yt-home-topics-below couchbox-yt --keys down,down,down
shot yt-home-topics couchbox-yt --keys down,down,down,down
shot yt-home-topics-second couchbox-yt --keys down,down,down,down,right
shot yt-home-refresh couchbox-yt --keys down,down,down,down,down
shot yt-home-refreshed couchbox-yt --keys down,down,down,down,down,ok,wait:1
shot yt-guide-tab couchbox-yt --keys left,down,down,down,down,down,down
shot yt-gaming couchbox-yt --open gaming
shot yt-search couchbox-yt --keys left,up,ok
shot yt-search-typed couchbox-yt --open typing:sky --keys down
shot yt-results couchbox-yt --open "search:sky"
shot yt-results-chips couchbox-yt --open "search:sky" --keys down
shot yt-channel couchbox-yt --open channel:UCdemo0000000000000orbit
shot yt-player couchbox-yt --open video:demo0000003
shot yt-player-related couchbox-yt --open video:demo0000003 --keys down
shot yt-player-bar couchbox-yt --open video:demo0000003 --keys up,right,right
shot yt-settings couchbox-yt --open settings
# ... signed in (made-up profiles): Who's watching (and its gear's menu), adding an account, Home as a
# guest, Subscriptions (the channels, the feed), Library (its tiles, History), the player's panels
# (the channel, notifications, Save), the open guide down to Settings
shot yt-profiles couchbox-yt --profile pick
shot yt-profiles-menu couchbox-yt --profile pick --keys down,ok
shot yt-signin couchbox-yt --open signin
shot yt-home-guest couchbox-yt --profile guest
shot yt-subscriptions couchbox-yt --open subscriptions
shot yt-subscriptions-feed couchbox-yt --open subscriptions --keys down,right
shot yt-library couchbox-yt --open library
shot yt-library-history couchbox-yt --open library --keys ok
shot yt-player-channel couchbox-yt --open video:demo0000006 --keys left,left,left,left,ok
shot yt-player-notify couchbox-yt --open video:demo0000006 --keys left,left,ok
shot yt-player-save couchbox-yt --open video:demo0000006 --keys right,right,right,right,right,right,ok
shot yt-guide-settings couchbox-yt --keys left,down,down,down,down,down,down,down,down,down,down,down
# ... the player's M3 parts: Shorts (and its buttons), seeking with the chapters' pictures (and picking
# one), the Description panel, comments, the settings menu (quality), captions on, the end screen with
# Up next; a card's menu (Play next, Add to queue); the Movies & TV tab's large title and posters, and
# Music's square albums
shot yt-shorts couchbox-yt --open shorts:
shot yt-shorts-side couchbox-yt --open shorts: --keys right
shot yt-player-seek couchbox-yt --open video:demo0000003 --keys up
shot yt-player-chapters couchbox-yt --open video:demo0000003 --keys up,up,right,right
shot yt-player-description couchbox-yt --open video:demo0000003 --keys left,left,left,ok
shot yt-player-comments couchbox-yt --open video:demo0000003 --keys left,left,left,ok,down,down,down,ok
# a comment's own page (OK on it): Like, Dislike and Report under it, the focus on Like, then the
# mobile-app row and the replies; liked (OK); a reply's own page (Down past the row to it, OK); a
# comment without replies opens too (Right: Dislike)
shot yt-player-comment-open couchbox-yt --open video:demo0000003 --keys left,left,left,ok,down,down,down,ok,down,down,ok
shot yt-player-comment-liked couchbox-yt --open video:demo0000003 --keys left,left,left,ok,down,down,down,ok,down,down,ok,wait:1,ok
shot yt-player-comment-reply couchbox-yt --open video:demo0000003 --keys left,left,left,ok,down,down,down,ok,down,down,ok,wait:1,down,down,ok
shot yt-player-comment-plain couchbox-yt --open video:demo0000003 --keys left,left,left,ok,down,down,down,ok,down,down,down,down,ok,wait:1,right
shot yt-player-settings couchbox-yt --open video:demo0000003 --keys right,right,right,right,right,right,right,right,right,ok
shot yt-player-quality couchbox-yt --open video:demo0000003 --keys right,right,right,right,right,right,right,right,right,ok,ok
shot yt-player-cc couchbox-yt --open video:demo0000003 --keys right,right,right,right,right,right,right,right,ok
shot yt-player-end couchbox-yt --open video:demo0000003@3598
# ... its Replay focused (Left), the row of more videos (Down)
shot yt-player-end-replay couchbox-yt --open video:demo0000003@3598 --keys wait:3,left
shot yt-player-end-more couchbox-yt --open video:demo0000003@3598 --keys wait:3,down,right
shot yt-card-menu couchbox-yt --keys menu
shot yt-movies couchbox-yt --open movies
shot yt-music couchbox-yt --open music
# ... round 1's fixes: scrubbing with the controls hidden (the chapters' strip over the bar), the
# search results' channel section (the large card, the list in columns), the shelf under Search's
# keys, the open guide scrolled down to Movies & TV (Settings kept at the bottom)
shot yt-player-scrub couchbox-yt --open video:demo0000003@1500 --keys back,right
shot yt-results-cluster couchbox-yt --open "search:sky" --keys down,down,right
shot yt-search-landing couchbox-yt --keys left,up,ok,down,down,down
shot yt-guide-movies couchbox-yt --keys left,down,down,down,down,down,down,down,down
# ... round 2's, with the keys as the box sends them (press, release, gaps; ok@1.5 held with its
# repeats): Search opened from the guide with OK held (nothing typed), typing on a keyboard and
# Enter, Description and Back (the focus on Description), the related row and Up, the Shorts tab
# straight into Shorts, Settings beside the open guide, a guest's Library tiles
shot yt-search-held couchbox-yt --keys left,up,ok@1.5
shot yt-search-enter couchbox-yt --keys left,up,ok,t:sky,enter
shot yt-player-description-back couchbox-yt --open video:demo0000003 --keys left,left,left,ok,back
shot yt-player-related-up couchbox-yt --open video:demo0000003 --keys down,up
shot yt-shorts-tab couchbox-yt --keys left,down,ok
shot yt-library-guest couchbox-yt --profile guest --open library
# what the voice assistant, links sent to the TV and Continue watching open; the tile's app choice
shot yt-history couchbox-yt --open history
shot yt-playlist couchbox-yt --open playlist:PLdemo123
shot settings-apps-youtube couchbox-settings --page apps --in --wait 4500 --keys down,down,down,ok
# ... M4: Settings' SponsorBlock rows (switches), the player skipping a sponsor (the notice, OK to
# undo) and the bar with the segments in SponsorBlock's colours
shot yt-settings-sponsorblock couchbox-yt --open settings --keys down,down,down,ok
shot yt-player-sponsor-skip couchbox-yt --open video:demo0000003@1799 --keys wait:3
shot yt-player-segments couchbox-yt --open video:demo0000003@1700 --keys up
# focus at the edges: the first, last and bottom cards and rows (each shot also fails if a
# focused card grows past whatever clips it)
d13=down,down,down,down,down,down,down,down,down,down,down,down,down
r6=right,right,right,right,right,right
shot edge-weather-week-last couchbox-weather --open week --keys $d13
shot edge-weather-hours-first couchbox-weather --keys down
shot edge-weather-hours-far couchbox-weather --keys down,$r6,$r6,$r6
shot edge-frigate-live-last couchbox-frigate --keys down,down,down,$r6
shot edge-frigate-review-last couchbox-frigate --open review --keys $r6,down,down,down
shot edge-spotify-home-far couchbox-spotify --keys down,$r6,$r6
shot edge-spotify-artist-shelves couchbox-spotify --open artist:ar1 --keys down,down,down,right
shot edge-maps-places-last couchbox-maps --keys $r6,down,down,down
shot edge-movies-home-rows couchbox-movies --keys down,down,$r6
shot edge-movies-top-last couchbox-movies --open top:movie --keys $d13,$r6
shot edge-movies-person-work couchbox-movies --open person:303 --keys down,$r6
shot edge-search-recent couchbox-search --keys down,down
shot edge-search-on-this-tv-last couchbox-search --open "search:eiffel tower height" --keys up,$r6,$r6
shot edge-home-continue-last couchbox-ontv --keys down,$r6,$r6
shot edge-yt-home-far couchbox-yt --keys $r6,$r6,down,down,down
shot edge-yt-results-far couchbox-yt --open "search:sky" --keys $r6,$r6
[ -f bin/couchbox-setup ] && for s in 0 1 2 3 4 5 6 7 8 9 10; do shot "setup-$s" couchbox-setup --step "$s"; done
# the remote's Back key on every app's pages: it goes back a level or closes the app
python3 ci/back_check.py "$OUT/back" || fail=1
exit $fail
