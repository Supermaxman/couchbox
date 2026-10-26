// couchbox-search: run on every page once it loads. Makes the page work from the remote:
//  - the arrows hop between links, buttons and fields (the nearest one that way on screen,
//    with a big focus ring); with nothing near that way, Up/Down scroll the page instead, so
//    long articles read with just Down
//  - a field is only selected by the arrows, not edited: OK on it asks the app for its
//    keyboard pop-up ("couchbox:edit" + its text on the console) and the app puts the text
//    back with couchboxSetText(); a phone's typing goes straight in
//  - Up at the top of the page, with nothing above, asks the app for its toolbar ("couchbox:top")
//  - on Google's results page the first result is selected to start
(() => {
  if (window.__couchbox) return;
  window.__couchbox = true;
  // the ring: a box over the page that follows the selected element (an outline on the
  // element itself is often clipped by its container, or turned off by the site's styles)
  const ring = document.createElement("div");
  ring.style.cssText = "position:fixed;pointer-events:none;z-index:2147483647;border:4px solid #2dd4bf;border-radius:10px;" +
                       "box-shadow:0 0 0 3px rgba(0,0,0,.45),0 0 18px rgba(45,212,191,.55);display:none;transition:all .12s ease-out";
  (document.body || document.documentElement).appendChild(ring);
  const place = () => {
    if (!current || !document.contains(current)) { ring.style.display = "none"; return; }
    const r = current.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) { ring.style.display = "none"; return; }
    Object.assign(ring.style, {display: "block", left: (r.left - 7) + "px", top: (r.top - 7) + "px", width: (r.width + 6) + "px", height: (r.height + 6) + "px"});
  };
  addEventListener("scroll", place, true);
  addEventListener("resize", place);
  setInterval(place, 400);                                               // pages that move things around

  const FOCUSABLE = "a[href],button,input:not([type=hidden]),select,textarea,summary,[tabindex]:not([tabindex='-1']),[role=button],[role=link],[role=tab],[role=menuitem],[contenteditable=true]";
  const editable = el => el && (el.isContentEditable || el.tagName === "TEXTAREA" ||
    (el.tagName === "INPUT" && /^(text|search|email|url|tel|number|password|)$/i.test(el.type || "")));
  let current = null;

  const shown = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return null;
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || +s.opacity === 0) return null;
    if (el.closest("[aria-hidden=true],[inert]")) return null;
    return r;
  };
  const mark = el => {
    current = el;
    place();
    if (!el) return;
    // a field only gets the ring: focusing it would start editing (and open Google's suggestions)
    if (editable(el)) { if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); }
    else el.focus({preventScroll: true});
    const r = el.getBoundingClientRect(), h = innerHeight;
    if (r.top < h * 0.12 || r.bottom > h * 0.88) scrollBy({top: r.top - h * 0.35, behavior: "smooth"});
    setTimeout(place, 250);
  };

  // the nearest candidate in the direction (within about a screen), or null
  function next(dir) {
    const h = innerHeight, w = innerWidth;
    let from = current && document.contains(current) ? current.getBoundingClientRect() : null;
    if (from && (from.bottom < 0 || from.top > h)) from = null;              // scrolled away: start from the screen's edge
    const o = from ? {x: from.left + from.width / 2, y: from.top + from.height / 2, l: from.left, r: from.right, t: from.top, b: from.bottom}
                   : {x: w / 2, y: dir === "up" ? h : 0, l: 0, r: w, t: dir === "up" ? h : 0, b: dir === "up" ? h : 0};
    let best = null, score = Infinity;
    for (const el of document.querySelectorAll(FOCUSABLE)) {
      if (el === current || el.disabled) continue;
      const r = shown(el);
      if (!r) continue;
      if (r.bottom < -h * 0.2 || r.top > h * 1.2) continue;          // about a screen away at most
      const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      let main, side;
      if (dir === "down" || dir === "up") {
        if (dir === "down" ? r.top < o.b - 2 : r.bottom > o.t + 2) continue;
        main = dir === "down" ? r.top - o.b : o.t - r.bottom;
        side = Math.max(0, r.left - o.r, o.l - r.right);
      } else {
        if (dir === "right" ? r.left < o.r - 2 : r.right > o.l + 2) continue;
        if (r.bottom < o.t - h * 0.08 || r.top > o.b + h * 0.08) continue;   // roughly the same row
        main = dir === "right" ? r.left - o.r : o.l - r.right;
        side = Math.abs(cy - o.y);
      }
      const s = Math.max(0, main) + side * 2.5 + (dir === "up" || dir === "down" ? Math.abs(cx - o.x) * 0.05 : 0);
      if (s < score) { score = s; best = el; }
    }
    if (best && (dir === "up" || dir === "down") && score > h * 0.7) return null;   // far: scroll first
    return best;
  }

  window.couchboxSetText = (text, submit) => {
    const el = current && editable(current) ? current : document.activeElement;
    if (!editable(el)) return false;
    el.focus();
    if (el.isContentEditable) el.innerText = text;
    else {
      const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
    }
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
    if (submit && el.form) { if (el.form.requestSubmit) el.form.requestSubmit(); else el.form.submit(); }
    return true;
  };

  document.addEventListener("keydown", ev => {
    if (ev.altKey || ev.ctrlKey || ev.metaKey) return;
    const dir = {ArrowUp: "up", ArrowDown: "down", ArrowLeft: "left", ArrowRight: "right"}[ev.key];
    if (dir) {
      if (document.querySelector("select:focus")) return;                 // an open list: its own arrows
      ev.preventDefault(); ev.stopImmediatePropagation();
      const sel = current && document.contains(current) && shown(current);
      if (dir === "up" && !sel && scrollY <= 2) { console.log("couchbox:top"); return; }   // nothing selected, at the top
      const el = next(dir);
      if (el) { mark(el); return; }
      if (dir === "up" || dir === "down") {
        if (dir === "up" && scrollY <= 2) { console.log("couchbox:top"); return; }
        scrollBy({top: (dir === "down" ? 1 : -1) * innerHeight * 0.6, behavior: "smooth"});
      }
      return;
    }
    if (ev.key === "Escape" || ev.key === "GoBack" || ev.key === "BrowserBack") {   // the remote's Back: the app's
      ev.preventDefault(); ev.stopImmediatePropagation();
      console.log("couchbox:back");
      return;
    }
    if (current && editable(current) && document.activeElement !== current && (ev.key.length === 1 || ev.key === "Backspace")) {
      current.focus({preventScroll: true});                                // typing (from a phone) goes into the selected field
      return;
    }
    if (ev.key === "Enter" && ev.code !== "NumpadEnter" && !ev.isComposing) {   // the remote's OK (the phone's Enter is the keypad's)
      const el = current && document.contains(current) ? current : document.activeElement;
      if (editable(el)) {
        ev.preventDefault(); ev.stopImmediatePropagation();
        console.log("couchbox:edit " + JSON.stringify({text: el.isContentEditable ? el.innerText : el.value, password: el.type === "password",
                                                      label: el.getAttribute("aria-label") || el.placeholder || el.name || ""}));
        return;
      }
      if (el && el !== document.body && !/^(A|BUTTON|SUMMARY|SELECT|INPUT)$/.test(el.tagName)) {
        ev.preventDefault(); ev.stopImmediatePropagation();
        el.click();
      }
    }
  }, true);

  // Google's results: start on the first result (its title link), without scrolling past the top
  if (/^(www\.)?google\.[a-z.]+$/.test(location.hostname) && location.pathname === "/search") {
    const first = [...document.querySelectorAll("#search a h3, #rso a h3")].map(h => h.closest("a")).find(a => a && shown(a));
    const r = first && first.getBoundingClientRect();
    if (r && r.top > 0 && r.bottom < innerHeight) { current = first; first.focus({preventScroll: true}); place(); }
  }
  console.log("couchbox:ready");
})()
