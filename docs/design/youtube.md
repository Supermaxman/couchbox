# YouTube (native)

A native YouTube TV app (`ui/youtube`, `bin/couchbox-yt`), built to replace VacuumTube (YouTube's
own TV web app in a Chromium shell): YouTube's TV layout drawn in QML, videos played by mpv, with
no ads and VacuumTube's extras. What follows is how it's put together (as of November 2026) and
why.

## The pieces

| Piece | What it does |
|---|---|
| `ui/youtube/*.qml` | The pages: Who's watching, Home and the guide's tabs, Search, Subscriptions, Library, a channel, a playlist, the player (its controls, panels, Description, comments, chapters), Shorts, Settings |
| `bin/couchbox-yt` | The app: the QML window, its backend (every call the pages make), the control socket (`--open`, the voice assistant, the box check) |
| `couchbox.services.youtube` | InnerTube as the TV app talks to it (`youtubei/v1/...`, the `TVHTML5` client): pages, search, watch pages, accounts, likes, subscriptions, playlists, history; a guest or a signed-in profile |
| `couchbox.services.ytauth` | Signing in with a TV code (YouTube's device sign-in), each Google account's channels (brand accounts too), the tokens (mode 600 files, never logged) |
| `couchbox.services.ytworker` | A separate process for the streams: yt-dlp (a guest's videos) and deciphering a signed-in `/player` answer; a small cache of what each video plays |
| `couchbox.services.ytstream` | From a `/player` answer (or yt-dlp's) to what mpv opens: H.264 DASH (video and sound as one EDL), live HLS, captions, storyboards, chapters |
| `couchbox.services.ytjs` | YouTube's signature and "n" challenges, solved by a persistent JavaScript runtime: QuickJS in a bubblewrap sandbox, else node |
| `couchbox.services.ytlive` | A live stream from its adaptive formats (segments joined into one MP4 for mpv, on 127.0.0.1): when there's no HLS, and to go back through the DVR window |
| `couchbox.services.ytextras` | SponsorBlock and DeArrow (hash-prefix lookups), Return YouTube Dislike, and the app's settings |
| `couchbox.player` | mpv in the QML scene (shared with the other native apps): preload, captions, the TV's refresh rate (`couchbox.playback`) |

## Playing a video

Signed in, the app asks `/player` itself as the TV client, with the profile's token: a Premium
account gets no ads planned, so the DASH formats play at once (no waiting out ads that are never
shown). The worker deciphers the formats' addresses (`ytjs`) and picks H.264 up to 1080p60 (the
Pi decodes it in hardware; VP9 and AV1 with Settings → Video → H.264 only off). A guest's videos
go through yt-dlp. Live streams play their HLS; without one, or to rewind past what mpv has read,
their segments through `ytlive` (Left adds up 10 s steps, a moment later the stream comes from
that far back, up to its DVR window).

The focused card's stream is worked out and preloaded (paused, muted) so OK starts it in about
0.1 s; part-watched videos start where YouTube says they were left, and what's watched is
reported back so History and "resume" follow on every device.

## What's YouTube's and what's extra

As YouTube's TV app: Who's watching, Home, the guide's tabs (Music, Gaming, News, Podcasts,
Movies & TV, Live, Sports), Search with its keys and suggestions, Subscriptions, Library and its
lists, channels, the player's controls (like, dislike, save, captions, quality and speed,
chapters with their pictures, the storyboard while scrubbing, Description, comments and their
replies, the channel's panel and notifications), the card menu (hold OK), Shorts, Cast from
phones and Link with TV code, Restricted mode and a parent code, Autoplay next video.

Extras (VacuumTube's, in Settings): no ads, SponsorBlock (the marked parts on the bar, skipped by
kind), DeArrow, Return YouTube Dislike, Hide Shorts, H.264 only, Unlock resolution, Remove Super
Resolution, Show remaining time, Pause on blur, Block "Continue watching?", the guide's tabs,
Always show captions (English first: the video's own, generated, or YouTube's translation).

The TV's refresh rate stays as it is by default: each change blanks the TV for a second or two,
too often for YouTube. Settings → Video → Match the TV to the video's frame rate: Film only
follows a film (23.976, 24, 25 or 50 fps, over 5 minutes; not 59.94 or 29.97), Always every
video; either way the TV stays as it is between videos while the player is open, and the
indicator says so before and after each switch.

## Privacy

- Each profile, a guest too, has its own recent searches; pages and searches start afresh when
  the profile changes. The guest's visitor id goes with a guest's requests only.
- Tokens stay in mode-600 files under the TV user's data directory and are never logged.
- SponsorBlock and DeArrow are asked by a 4-character hash prefix of the video's id, never the id
  itself; Return YouTube Dislike (off unless turned on) is asked with the video's id.
- Comments, likes and subscriptions are only changed when you press them.

## Checking it on the box

`ci/yt-box-check.py` drives the app on the TV with the remote's keys and reads what has the
focus through the control socket (screenshots beside each step). Signed in (`--profile`), it only
reads: Who's watching, Home, Subscriptions, Library, a video (descriptions, seeks, captions,
comments and their replies, the channel), Shorts, the tabs and a live stream (rewound), Settings,
Search as a guest. `--clean-history RUNDIR` takes the videos it played out of today's History
again; `--menu-test` (a write, undone) saves a video to a playlist through the card menu and
takes it out; `--perf` times starting, videos and Home against the targets. The probes
(`menuProbe`, `pageProbe`, `commentsProbe`, `shortProbe`, `premiumProbe`) show how YouTube sends a
page to this profile: key names, short words and icon names, never tokens.
