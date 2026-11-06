# Recording the TV screen

`couchbox-record` records what's on the TV as an MP4: for testing, for demos, and for clips in the README or the release notes. It runs over SSH, with nobody at the TV. Recordings land in the TV user's `~/Videos/couchbox/`.

- [A clip for the README](#a-clip-for-the-readme)
- [Recording by hand](#recording-by-hand)
- [Options](#options)
- [Limits](#limits)
- [How it works](#how-it-works)
- [When something goes wrong](#when-something-goes-wrong)

The tools are in `/usr/lib/couchbox/bin`:

```sh
R=/usr/lib/couchbox/bin/couchbox-record
```

## A clip for the README

1. **Record exactly the presses you want to show.** `--remote` starts the recording, presses the buttons (as `couchbox-remote` does), keeps recording `--tail` seconds for the last press's result, and stops:

   ```sh
   $R start --remote "wait:1 right wait:1 right wait:1 ok wait:4 back wait:1"
   # /home/tv/Videos/couchbox/couchbox-20261105-201530.mp4 (0:11, 2.1 MB; the --remote script ended)
   ```

   Buttons are `couchbox-remote`'s: `up down left right ok back home menu playpause rewind forward mic volup voldown mute power settings`. `ok@1.2` holds a button down, and `wait:2` waits.
2. **Cut it down and make it small:**

   ```sh
   $R export /home/tv/Videos/couchbox/couchbox-20261105-201530.mp4 --mp4 --from 0.5 --to 10
   # /home/tv/Videos/couchbox/couchbox-20261105-201530-small.mp4 (0.9 MB)
   ```

   - `--mp4` is the format to use: H.264 at 720p at most, which GitHub plays inline (drag it into the README or a release's notes).
   - `--webm` (VP9) is smaller still, but GitHub doesn't play it in Markdown.
   - `--gif` (640 wide, 12 fps) suits only a few seconds. A GIF of moving video runs to tens of MB, and the export warns above 10 MB.
3. **Copy it off the box.** The files are the TV user's: `ssh BOX sudo cat /home/tv/Videos/couchbox/…-small.mp4 > clip.mp4`.

`export` is ffmpeg, so it also runs on a PC, which is faster: copy the recording over and run the same command with `bin/couchbox-record export` from a checkout.

## Recording by hand

```sh
$R start                    # in the background: 720p30, no sound, up to 10 minutes
$R status                   # recording …, 0:42 of 10:00, 12.3 MB, 1280x720 at 30 fps, encoder CPU 115%
$R stop                     # finishes the file and prints it
```

Only one recording runs at a time. `start` refuses a second one, and `status` and `stop` work from any SSH session.

## Options

| `start` option | Default | |
|---|---|---|
| `FILE` | `~/Videos/couchbox/couchbox-DATE-TIME.mp4` | A folder puts a timestamped name in it. An existing file isn't overwritten |
| `--seconds N` | 600 | Stops by itself after N seconds (at most 3600) |
| `--width W` | 1280 | Never wider than the screen. `--width 1920` for 1080p (see the CPU note below) |
| `--fps F` | 30 | |
| `--audio` | off | The TV's sound: PipeWire's monitor of the default output |
| `--cursor` | off | The mouse pointer |
| `--preset P`, `--crf Q` | `ultrafast`, 23 | libx264's speed and quality |
| `--max-mb N` | 2048 | Stops by itself at this size |
| `--remote "BUTTONS"`, `--tail S` | | Press the buttons, record S seconds more (default 1), stop |

| `export` option | | |
|---|---|---|
| `--mp4`, `--webm`, `--gif` | `--gif` | The format |
| `--width W` | 1280 (GIF 640) | Never larger than the recording |
| `--fps F` | the recording's (GIF 12) | |
| `--from S`, `--to S` or `--seconds N` | the whole file | The part to keep |
| `OUT` | beside the recording | |

## Limits

- **CPU:** the Pi 5 has no H.264 encoder, so libx264 encodes in software at nice 10, and the TV's own video keeps the CPU first. Beside a 1080p60 video, the encoder takes about 115% of a core at 720p and about 190% at 1080p.
- **Length and disk:** a recording stops by itself at its `--seconds`, at `--max-mb`, or when less than 1 GB of disk is left.
- **If the recorder dies:** the file still plays, up to the last second. The MP4's index is rewritten every second. `status` says the recorder stopped, and `stop` saves the file.

## How it works

KWin lets a program capture the screen only if a `.desktop` file names the program's executable along with KWin's interface for it.

- `couchbox-screencast` (`/usr/lib/couchbox/libexec`) is a small C helper, authorized by `couchbox-screencast.desktop` for `zkde_screencast_unstable_v1`. It asks KWin for a PipeWire stream of the screen and holds it while the recording runs. Each stream is logged: `journalctl -t couchbox-screencast`.
- The stream is encoded by GStreamer: `pipewiresrc` → a clock-driven compositor (it repeats the last frame while the screen is idle, since KWin sends frames only when something changes) → `x264enc` → `mp4mux`.
- `couchbox-screenshot` works the same way for stills. It uses KWin's ScreenShot2 interface, through its own link to Python (`/usr/lib/couchbox/libexec/couchbox-capture-python`).

More in [design/ci-and-testing.md](design/ci-and-testing.md#on-the-box-the-remote-screenshots-and-recordings).

## When something goes wrong

- **Logs:** the last recording's log is `/run/user/<tv's uid>/couchbox-record/log`, and `journalctl -t couchbox-record -t couchbox-screencast` has the rest.
- **"KWin doesn't let couchbox-screencast record":** KWin hasn't seen the `.desktop` file yet. Run `kbuildsycoca6` as the TV user, or restart the TV session.
- **"…GStreamer didn't finish in 10 s…" in `stop`'s output:** the file is fine up to its last second. Please report it with the log.
