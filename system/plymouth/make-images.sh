#!/bin/bash
# Couchbox boot screen: draws the theme's images (system/plymouth/couchbox/*.png) at their
# 3840x2160 size. Needs rsvg-convert. The PNGs are committed; re-run after changing this file.
set -euo pipefail
D=$(cd "$(dirname "$0")" && pwd)/couchbox
svg() { rsvg-convert -o "$D/$1.png" /dev/stdin; }

# The logo: docs/icon.svg's TV-and-couch strokes, without the app-icon square behind them.
svg logo <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="300" height="270" viewBox="28 40 200 180">
  <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7aa2ff"/><stop offset="1" stop-color="#a98bff"/></linearGradient></defs>
  <g fill="none" stroke="url(#g)" stroke-width="12" stroke-linecap="round" stroke-linejoin="round">
    <rect x="40" y="52" width="176" height="104" rx="14"/>
    <path d="M52 196v-28a14 14 0 0 1 14-14h124a14 14 0 0 1 14 14v28"/>
    <path d="M40 174h28v34M216 174h-28v34"/>
  </g>
</svg>
X
# The progress bar: track, fill (the logo's gradient) and the amber fill for "needs you".
svg bar-track <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="10"><rect width="720" height="10" rx="5" fill="#fff" fill-opacity=".12"/></svg>
X
svg bar-fill <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="10"><defs><linearGradient id="g"><stop offset="0" stop-color="#7aa2ff"/><stop offset="1" stop-color="#a98bff"/></linearGradient></defs><rect width="720" height="10" rx="5" fill="url(#g)"/></svg>
X
svg bar-warn <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="720" height="10"><defs><linearGradient id="g"><stop offset="0" stop-color="#ffc35c"/><stop offset="1" stop-color="#ff9f4a"/></linearGradient></defs><rect width="720" height="10" rx="5" fill="url(#g)"/></svg>
X
# The bar's leading edge: a soft light that breathes while a step runs.
svg bar-glow <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96"><defs><radialGradient id="r"><stop offset="0" stop-color="#c9b8ff" stop-opacity=".9"/><stop offset=".35" stop-color="#a98bff" stop-opacity=".35"/><stop offset="1" stop-color="#a98bff" stop-opacity="0"/></radialGradient></defs><circle cx="48" cy="48" r="48" fill="url(#r)"/></svg>
X
# The passphrase field and its dots.
svg field <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="128"><rect x="1.5" y="1.5" width="1037" height="125" rx="62.5" fill="#fff" fill-opacity=".06" stroke="#fff" stroke-opacity=".22" stroke-width="3"/></svg>
X
svg dot <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="26" height="26"><circle cx="13" cy="13" r="13" fill="#f5f6f8"/></svg>
X
# The log panel: near-opaque background (stretched to size) and its top edge.
svg panel <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16" fill="#07080c" fill-opacity=".94"/></svg>
X
svg panel-edge <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="2"><rect width="16" height="2" fill="#fff" fill-opacity=".10"/></svg>
X
# The on-screen keyboard (the remote types the passphrase with it): a key 1-4 units wide (a unit
# is 116 px with 14 px between keys), plain, focused (the logo's gradient) and lit (Shift on),
# and the Shift and Delete icons, light and dark (on the focused key).
for w in 1 2 3 4; do
    px=$((w * 116 + (w - 1) * 14))
    svg "key-$w" <<X
<svg xmlns="http://www.w3.org/2000/svg" width="$px" height="116"><rect width="$px" height="116" rx="22" fill="#fff" fill-opacity=".07"/></svg>
X
    svg "key-$w-on" <<X
<svg xmlns="http://www.w3.org/2000/svg" width="$px" height="116"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#7aa2ff"/><stop offset="1" stop-color="#a98bff"/></linearGradient></defs><rect width="$px" height="116" rx="22" fill="url(#g)"/></svg>
X
done
svg key-2-lit <<'X'
<svg xmlns="http://www.w3.org/2000/svg" width="246" height="116"><rect width="246" height="116" rx="22" fill="#fff" fill-opacity=".2"/></svg>
X
for c in light:f5f6f8 dark:0b0d12; do
    svg "icon-shift-${c%%:*}" <<X
<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" viewBox="0 0 24 24"><path d="M12 3.5 3.5 12.5H8v8h8v-8h4.5z" fill="none" stroke="#${c#*:}" stroke-width="2" stroke-linejoin="round"/></svg>
X
    svg "icon-del-${c%%:*}" <<X
<svg xmlns="http://www.w3.org/2000/svg" width="60" height="52" viewBox="0 0 28 24"><g fill="none" stroke="#${c#*:}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M9 4.5h15.5v15H9L2.5 12z"/><path d="m13 9 6 6m0-6-6 6"/></g></svg>
X
done
