# Notes for coding agents

## Testing on the owner's TV box

The family watches TV on the owner's Couchbox box every day, and development tests run on that same box.

- When the TV is in use (the remote was pressed recently, something is playing, or an app other than the home screen is in front), don't touch it, and don't ask the owner to free it or tell you when it's free. Wait it out on your own: retry later, or schedule a check-in, and carry on with work that doesn't need the TV. Ask only when the owner explicitly asks you to.
- Before every scripted step on the box, check again that it's idle; mute during tests and restore the sound as you found it.
