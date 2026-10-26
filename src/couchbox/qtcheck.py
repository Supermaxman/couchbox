"""Screenshot checks: a focused card that grows (scale > 1) must fit inside everything that clips
it (a list with clip: true, a page, the window). Every app's --shot calls clipped() before saving,
and ci/screenshots.sh fails on the "focus-clip:" lines it prints."""

import sys

from PySide6.QtCore import QRectF

SLACK = 0.5  # px: rounding


def _name(item):
    n = item.objectName() or item.metaObject().className()
    try:
        src = item.property("source") if n.endswith("Image") else None
    except Exception:  # noqa: BLE001
        src = None
    return f"{n} ({src})" if src else n


def _extent(item):
    """The item's scene rectangle with its scale, and its direct children's (a focus ring
    drawn just outside it counts)."""
    r = item.mapRectToScene(item.boundingRect())
    for c in item.childItems():
        if c.isVisible() and c.opacity() > 0:
            r = r.united(c.mapRectToScene(c.boundingRect()))
    return r


def _grown(item, out):
    if not item.isVisible() or item.opacity() <= 0:
        return
    if item.scale() > 1.001:
        out.append(item)
    for c in item.childItems():
        _grown(c, out)


def clipped(window, log=None):
    """[(item, clipper, (left, top, right, bottom) px cut off)] for each grown item that sticks out
    of a clipping ancestor or the window. Printed as "focus-clip: ..." lines."""
    log = log or (lambda s: print(s, file=sys.stderr, flush=True))
    root = window.contentItem()
    found = []
    items = []
    _grown(root, items)
    win = QRectF(0, 0, window.width(), window.height())
    for it in items:
        r = _extent(it)
        p = it.parentItem()
        while p is not None:
            box = p.mapRectToScene(p.boundingRect()) if p is not root else win
            if p.clip() or p is root:
                cut = (box.left() - r.left(), box.top() - r.top(), r.right() - box.right(), r.bottom() - box.bottom())
                if any(c > SLACK for c in cut):
                    found.append((it, p, tuple(round(max(0.0, c), 1) for c in cut)))
                    log(
                        f"focus-clip: {_name(it)} (scale {it.scale():.2f}) is cut off by {_name(p)}: left/top/right/bottom {found[-1][2]} px"
                    )
                    break
            p = p.parentItem()
    return found
