#!/bin/sh
# Render every Settings page and the setup wizard off screen (demo mode: a fake system),
# into $1 (default build/shots). Fails on QML errors.
set -eu
OUT=${1:-build/shots}
make -s stage >/dev/null
mkdir -p "$OUT"
export COUCHBOX_SHARE="$PWD/build/share" PYTHONPATH="$PWD/src" QT_QPA_PLATFORM=offscreen LANG=C.UTF-8
fail=0
shot() {  # shot NAME APP ARGS...
  name=$1; app=$2; shift 2
  if ! python3 "bin/$app" --demo --shot "$OUT/$name.png" "$@" >"$OUT/$name.log" 2>&1 || grep -qE "qrc:|file:.*(Error|TypeError|ReferenceError)|is not defined|Cannot assign|Unable to assign" "$OUT/$name.log"; then
    echo "!! $name"; grep -E "Error|error|not defined|Cannot" "$OUT/$name.log" | head -5; fail=1
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
# the Weather app with a made-up fortnight: Today, the 14 days, a day in detail (from an hour
# picked on Today, and from the list), the alert, the radar (playing; paused a frame back, zoomed in)
shot weather-today couchbox-weather
shot weather-week couchbox-weather --open week --keys down,down
shot weather-day couchbox-weather --open day:tomorrow
shot weather-day-hour couchbox-weather --keys right,right,right,ok
shot weather-alerts couchbox-weather --open alerts
shot weather-radar couchbox-weather --open radar
shot weather-radar-paused couchbox-weather --open radar --keys up,ok,left,left
# Search with made-up pages: the start page, results (with the AI answer), the toolbar, the
# reader and a summary
shot search-start couchbox-search
shot search-results couchbox-search --open "search:eiffel tower height"
shot search-toolbar couchbox-search --open "search:eiffel tower height" --keys up
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
[ -f bin/couchbox-setup ] && for s in 0 1 2 3 4 5 6 7 8 9 10; do shot "setup-$s" couchbox-setup --step "$s"; done
exit $fail
