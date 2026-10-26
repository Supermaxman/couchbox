# Spotify

A native TV app (`ui/spotify`, `bin/couchbox-spotify`) to browse, search and play your Spotify
music, plus a background service that plays it on this box. What follows is why it's built the
way it is (as of October 2026), and what each household has to do once.

## Playing music: Spotify Soloist

Spotify shipped **Soloist** in August 2026: its own headless Spotify Connect player for Linux,
including Raspberry Pi (aarch64), with PipeWire output and a local WebSocket API
([docs](https://developer.spotify.com/documentation/soloist)). Couchbox uses it, not librespot:

| | Soloist | librespot |
|---|---|---|
| Who makes it | Spotify | reverse-engineered, community |
| Accounts | Free and Premium can play; the key's owner needs Premium | Premium only |
| Audio | Spotify's engine (lossless, normalization) | open re-implementation |
| Control | WebSocket: play any URI, queue, seek, volume, events | Connect only |
| Catch | not redistributable; a per-user API key; builds expire after 90 days | breaks when Spotify changes things |

So Couchbox never ships the binary. When the user presses **Download** in the app's Setup, the
box fetches Spotify's current aarch64 build from `soloist-builds.spotifycdn.com` into the TV
user's `~/.local/share/couchbox-spotify/soloist/` (only the `soloist` program is taken from the
archive). `couchbox-spotify --connect` (the `couchbox-spotify-connect.service` user unit, enabled
by Setup) runs it as `--device-name <AirPlay name or device name> --ws 127.0.0.1:0`, fetches a
newer build once the installed one is 60 days old, and again whenever it exits with code 10
(expired). It also serves MPRIS (the remote's play/pause, `couchbox-pause-all`) and the voice
assistant's control socket, and keeps playing when the app is closed.

Soloist signs in through Spotify Connect: once, the user picks the TV in the Spotify app on a
phone on the same network. After that phones can also send music to it.

## Browsing: the Web API with the user's own developer app

Soloist plays; it doesn't browse. Search, library, playlists, likes and artist pages come from
the Spotify Web API, which needs a developer app (a client ID). Couchbox can't share one: a
development-mode app allows 5 users and its owner needs Premium (February 2026), and extended
quota is for organizations with 250k monthly users (May 2025). So each household makes its own
(free) app; its owner can add up to 4 more household members under User Management.

A development-mode app can't do everything Spotify's own apps do. What's missing, and what the
app does instead:

| Missing for new development-mode apps | Since | Instead |
|---|---|---|
| Recommendations, related artists, audio features | Nov 2024 | not shown |
| Algorithmic and editorial playlists' contents (Discover Weekly, Release Radar, Daily Mix…) | Nov 2024 | **Made for you** lists the ones you saved, plus the ones that played on this TV (the player reports their names). They **play** fine (Soloist plays any URI); their song lists can't be shown. |
| Featured playlists, categories, new releases | Nov 2024 / Feb 2026 | **New from your artists**: the last 8 weeks of albums and singles from artists you follow and play most (cached 6 h) |
| An artist's top tracks | Feb 2026 | **Popular**: a search for the artist's songs (ranked by popularity), filtered to that artist |
| Other people's playlists' songs | Feb 2026 | shown and playable, without the song list |
| Batch fetches; 50 search results | Feb 2026 | one request each; 10 results per kind |
| `/me/tracks` etc. | Feb 2026 | `/me/library` (every call falls back to the old endpoint for older apps) |

The other path some open-source clients take (ncspot, spotify-player) is a token from a
librespot session with **Spotify's own client ID**, which reaches everything above. It means
presenting as Spotify's desktop app, against Spotify's Developer Terms; Couchbox doesn't do it.

Refresh tokens are single use and, since July 2026, last six months from sign-in. The app and
the background service both refresh, so `spotify.py` locks `~/.local/share/couchbox-spotify/
.lock` and re-reads the session file first (the lesson from Twitch). After six months the app
says Spotify signed it out and shows the sign-in QR code again.

## Signing in from a phone (OAuth with PKCE)

Spotify has no device-code sign-in for apps like this, and its redirect addresses must be
https, or `http://127.0.0.1`. So the TV shows a QR code to the phone page's `/spotify/login`,
which forwards to Spotify's sign-in page, and:

- **With Tailscale** serving the phone page, Spotify sends the phone back to
  `https://<box>.<tailnet>/spotify/callback`. The phone page hands the code to the app (or the
  background service), which finishes the sign-in. Nothing to type.
- **Without it**, the redirect is `http://127.0.0.1:8792/callback`, which a phone can't open: the
  user copies that address from the phone's address bar and types it into Setup with the phone
  remote page.

Both addresses go in the developer app's Redirect URIs; Setup shows the exact ones.

## Voice

The `spotify` tool (through `couchbox-spotify --connect`): play a song, artist, album or one of
your playlists ("my Discover Weekly", "liked songs"), what's playing, like or unlike it, add it
to a playlist, and make a playlist from songs the assistant picks ("Artist - Title"): each is
searched on Spotify and added. Spotify's Developer Terms (v10) forbid feeding Spotify content
into an AI model, so the model gets only short replies ("Made 90s Rock with 24 songs"), never
search results or catalogue data.

## What a household does, once

1. Spotify Premium for the person setting it up.
2. developer.spotify.com/dashboard/soloist (**Spotify Soloist API Key** in the dashboard, not inside
   the app) → Generate. It isn't the app's Client ID or Client secret. A wrong key starts fine and
   only fails when a phone picks the TV (the phone stays on "Connecting…"); the player logs
   `login failed: make sure --api-key is valid`, and `--connect` turns that line into a
   `login_error` in the player's status, which Setup and Now Playing show until a login works or
   the key changes. Setup also refuses the app's client ID as the key.
3. developer.spotify.com → Dashboard → **Create app**: any name; Redirect URIs as Setup shows them;
   API: Web API. Copy its **Client ID**. Others in the home: User Management.
4. On the TV: Spotify → Setup: type the client ID and the key (the phone remote page types), press
   **Download** (Spotify's player), pick the TV in the Spotify app on a phone, scan the QR code.

Files (the TV user's, mode 0600): `~/.local/share/couchbox-spotify/{config.json (client ID),
soloist.key, session.json (tokens), contexts.json (what played here), cache.json}` and
`soloist/` (the player and its Connect session).
