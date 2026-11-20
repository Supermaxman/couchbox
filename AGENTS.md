# Notes for coding agents

## The dev box: test there, not on the household box

The owner has a second box for development, the dev box ([docs/dev-box.md](docs/dev-box.md)). It runs all day for testing.

- Run every on-box test, UI check, screenshot, recording and pushed build on the dev box. Use the household box only when the owner asks for it.
- Drive the dev box entirely with the tools: `ci/box-push.sh`, `ci/box-check.sh`, `ci/box-reset.sh`, `ci/box-wifi-check.sh`, and `couchbox-remote` and `couchbox-screenshot` on the box. Never need the owner at it.
  - Keep its Ethernet connected: it's the way back in.
  - Don't run a full reset (`ci/box-reset.sh --image`) unless you can see the box's console if its start fails.
- Copying credentials is approved: logins and settings the dev box needs for a test (Frigate, Jellyfin, Seerr, the voice endpoints, a test YouTube sign-in) may be copied from the household box onto the dev box over SSH. Copy them box to box; never print, commit or log them.
- The boxes' names and addresses are the owner's private setup (your own notes and SSH config), never in this repo.

## The household box

The family watches TV on the owner's household box every day. It isn't a test box: touch it only when the owner asks, or to read credentials for the dev box (above).

- When the TV is in use (the remote was pressed recently, something is playing, or an app other than the home screen is in front), don't touch it, and don't ask the owner to free it or tell you when it's free. Wait it out on your own: retry later, or schedule a check-in, and carry on with work that doesn't need the TV. Ask only when the owner explicitly asks you to.
- Before every scripted step on the box, check again that it's idle; mute during tests and restore the sound as you found it.
