"""Fire TV remote microphone over hidraw (verified on the 0171:0427 remote).

Holding the mic button sends the Search key (HID consumer usage 0x0221, report 02) and
releasing it clears it. While it's held the host turns the mic on with output report F2 01
(off: F2 00); audio then arrives as input report F0, 80 bytes every 20 ms, each one Opus
packet (CELT wideband, 16 kHz mono). Reading hidraw doesn't take the keys away from
couchbox-input, which reads the same remote through evdev."""

import ctypes
import glob
import os
import select
import time

RATE = 16000
MAX_SECONDS = 20  # the mic is closed after this even if the button is still held


class Opus:
    def __init__(self):
        self.lib = ctypes.CDLL("libopus.so.0")
        self.lib.opus_decoder_create.restype = ctypes.c_void_p
        err = ctypes.c_int()
        self.dec = ctypes.c_void_p(self.lib.opus_decoder_create(RATE, 1, ctypes.byref(err)))
        self.buf = (ctypes.c_int16 * 5760)()

    def decode(self, packet):
        n = self.lib.opus_decode(self.dec, packet, len(packet), self.buf, 5760, 0)
        return bytes(self.buf)[: n * 2] if n > 0 else b""


def find_hidraw():
    for h in glob.glob("/sys/class/hidraw/hidraw*"):
        try:
            if "HID_ID=0005:00000171" in open(h + "/device/uevent").read():
                return "/dev/" + os.path.basename(h)
        except OSError:
            pass
    return None


def run(on_press, on_release, log, on_connect=lambda: None):
    """Forever: watch the remote; on_press() when the mic button goes down, then
    on_release(pcm) with the recorded 16 kHz s16le audio when it's released;
    on_connect() each time the remote (re)appears."""
    opus = None
    fd = None
    held = False
    pcm = bytearray()
    started = 0.0
    while True:
        if fd is None:
            path = find_hidraw()
            if not path:
                time.sleep(2)
                continue
            try:
                fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
            except OSError as err:
                log(f"cannot open {path}: {err}")
                time.sleep(5)
                continue
            log(f"listening to the remote on {path}")
            on_connect()
        try:
            if not select.select([fd], [], [], 1)[0]:
                if held and time.monotonic() - started > MAX_SECONDS:
                    raise TimeoutError
                continue
            report = os.read(fd, 256)
        except BlockingIOError:
            continue
        except TimeoutError:
            report = b"\x02\x00\x00\x00\x00"  # treat as released
        except OSError:
            log("remote disconnected")
            os.close(fd)
            fd = None
            if held:
                held = False
                on_release(bytes(pcm))
            continue
        if report[0] == 0x02:
            search = any(report[i : i + 2] == b"\x21\x02" for i in (1, 3))
            if search and not held:
                held, pcm, started = True, bytearray(), time.monotonic()
                opus = opus or Opus()
                os.write(fd, b"\xf2\x01")
                on_press()
            elif not search and held:
                held = False
                try:
                    os.write(fd, b"\xf2\x00")
                except OSError:
                    pass
                on_release(bytes(pcm))
        elif report[0] == 0xF0 and held:
            pcm += opus.decode(report[1:])
            if time.monotonic() - started > MAX_SECONDS:
                held = False
                os.write(fd, b"\xf2\x00")
                on_release(bytes(pcm))
