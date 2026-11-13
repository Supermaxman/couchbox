#!/usr/bin/env python3
"""analyze.py RUNDIR [-v]: what the probe logged, as numbers.
Per key press: how long until the app got it, until its first new frame, and how the frames that
followed were paced (wall-clock gap between frames; how far the animation clock moved per frame)."""

import statistics as st
import sys


def load(path, conv):
    out = []
    try:
        for line in open(path):
            p = line.strip().split(",")
            if len(p) >= 2:
                out.append(conv(p))
    except OSError:
        pass
    return out


def pct(xs, q):
    if not xs:
        return float("nan")
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main():
    d = sys.argv[1]
    verbose = "-v" in sys.argv
    frames = load(f"{d}/frames.csv", lambda p: (int(p[0]) / 1e6, float(p[1])))
    keys = [k for k in load(f"{d}/keys.csv", lambda p: (int(p[0]) / 1e6, p[1], int(p[2]), int(p[3]))) if k[1] == "p" and not k[3]]
    sent = load(f"{d}/sent.csv", lambda p: (int(p[0]) / 1e6, p[1]))
    ft = [f[0] for f in frames]
    in_lat, resp, bursts, moves = [], [], [], []
    all_wall, all_err, steps = [], [], []
    import bisect

    for i, (kt, _, _, _) in enumerate(keys):
        nxt = keys[i + 1][0] if i + 1 < len(keys) else kt + 2000
        s = [x for x in sent if 0 <= kt - x[0] < 400]
        name = s[-1][1] if s else "?"
        if s:
            in_lat.append(kt - s[-1][0])
        j = bisect.bisect_right(ft, kt)
        if j >= len(ft) or ft[j] - kt > 300:
            if verbose:
                print(f"  {name:6} no frame after it")
            continue
        resp.append(ft[j] - kt)
        # the burst: frames after the key until a gap of 60 ms or the next key
        b = [frames[j]]
        k = j + 1
        while k < len(frames) and frames[k][0] < nxt and frames[k][0] - b[-1][0] < 60:
            b.append(frames[k])
            k += 1
        wall = [b[n + 1][0] - b[n][0] for n in range(len(b) - 1)]
        anim = [b[n + 1][1] - b[n][1] for n in range(len(b) - 1)]
        err = [a - w for a, w in zip(anim, wall, strict=False)]
        bursts.append((name, len(b), b[-1][0] - b[0][0], wall, anim))
        # the move itself: the first 230 ms after the key (the apps' moves take 140-220 ms)
        mv = [(w, a) for n, (w, a) in enumerate(zip(wall, anim, strict=False)) if b[n + 1][0] - kt <= 230]
        if len(mv) >= 4:
            moves.append((any(w > 25 for w, _ in mv), any(abs(a - w) > 8 for w, a in mv[1:])))
        all_wall += wall
        all_err += err
        steps += anim
        if verbose:
            print(
                f"  {name:6} in {in_lat[-1] if s else -1:5.1f} ms  first frame {resp[-1]:5.1f} ms  {len(b):3} frames {b[-1][0] - b[0][0]:5.0f} ms  "
                f"wall max {max(wall, default=0):5.1f}  anim steps {' '.join(str(int(round(a))) for a in anim[:24])}"
            )
    n = len(all_wall)
    if not n:
        print("no frames after keys")
        return
    late = sum(1 for w in all_wall if w > 25)
    uneven = sum(1 for a in steps if a < 12 or a > 21)
    print(f"{d.rstrip('/').split('/')[-1]}: {len(keys)} presses, {len(frames)} frames")
    print(f"  remote -> app:        median {st.median(in_lat):.1f} ms, p95 {pct(in_lat, 0.95):.1f}" if in_lat else "  (no sent.csv)")
    print(f"  key -> first frame:   median {st.median(resp):.1f} ms, p95 {pct(resp, 0.95):.1f}, max {max(resp):.1f}")
    print(
        f"  frame gaps (wall):    median {st.median(all_wall):.1f} ms, p95 {pct(all_wall, 0.95):.1f}, max {max(all_wall):.1f}; late (>25 ms) {late}/{n} = {100 * late / n:.1f}%"
    )
    if moves:
        print(
            f"  during the move itself (first 230 ms): {sum(m[0] for m in moves)}/{len(moves)} moves dropped a frame, "
            f"{sum(m[1] for m in moves)}/{len(moves)} had a step out of time with the screen (>8 ms off)"
        )
    print(
        f"  animation per frame:  median {st.median(steps):.0f} ms, uneven steps (<12 or >21 ms) {uneven}/{n} = {100 * uneven / n:.1f}%; "
        f"error vs wall: sd {st.pstdev(all_err):.1f} ms, p95 |e| {pct([abs(e) for e in all_err], 0.95):.1f}"
    )


main()
