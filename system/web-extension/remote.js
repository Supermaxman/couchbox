// couchbox TV remote helper, loaded into every web app page (Chromium runs with
// --enable-spatial-navigation, so the arrows move focus between focusable elements).
// - Clickable things that aren't focusable (div/img cards with a click handler) get
//   tabindex=0, so the arrows can reach them, and OK (Enter) clicks them.
// - Back (Esc) goes back a page unless it closed a dialog or menu.
(() => {
  const SELECTOR = "[onclick], [role=button], [role=link], [role=tab], [role=menuitem], [role=option], " +
    "[role=checkbox], [role=switch], [role=radio], summary, [data-a-target], [data-testid]";
  const FOCUSABLE = "a[href], button, input, select, textarea, iframe, [tabindex], [contenteditable=true], video[controls]";

  function clickable(el) {
    if (el.matches(SELECTOR)) {
      // data-* attributes only count when the element also looks clickable
      if (el.matches("[data-a-target], [data-testid]") && !el.matches("[onclick], [role]")) {
        if (getComputedStyle(el).cursor !== "pointer") return false;
      }
      return true;
    }
    return getComputedStyle(el).cursor === "pointer" &&
      (!el.parentElement || getComputedStyle(el.parentElement).cursor !== "pointer");
  }

  function tag(root) {
    const els = root.querySelectorAll(SELECTOR + ", div, li, img, span, article, figure, section, label");
    for (const el of els) {
      if (el.hasAttribute("tabindex") || el.matches(FOCUSABLE) || el.closest(FOCUSABLE)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 24 || r.height < 18) continue;
      if (!clickable(el)) continue;
      el.setAttribute("tabindex", "0");
      el.setAttribute("data-couchbox-nav", "");
    }
  }

  let timer = null;
  const schedule = () => {
    if (timer) return;
    timer = setTimeout(() => {
      timer = null;
      (window.requestIdleCallback || (f => f()))(() => document.body && tag(document.body), {timeout: 500});
    }, 600);
  };

  const watch = () => {
    new MutationObserver(schedule).observe(document.documentElement, {childList: true, subtree: true});
    schedule();
  };
  if (document.documentElement) watch(); else document.addEventListener("DOMContentLoaded", watch);

  // OK on a tagged element: click it (only real buttons and links do that by themselves)
  document.addEventListener("keydown", ev => {
    if (ev.key === "Enter" && !ev.defaultPrevented && ev.target.hasAttribute &&
        ev.target.hasAttribute("data-couchbox-nav")) {
      ev.preventDefault();
      ev.target.click();
    }
  });

  // Back: let the page use Esc first (close a menu or dialog, leave full screen). If no
  // dialog or open menu was showing, or the page left it open, go back a page.
  const OVERLAY = "dialog[open], [role=dialog], [role=alertdialog], [aria-modal=true], [role=menu], " +
    "[role=listbox], [aria-expanded=true]";
  const overlays = () => [...document.querySelectorAll(OVERLAY)].filter(el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== "hidden";
  }).length;
  window.addEventListener("keydown", ev => {
    if (ev.key !== "Escape" || ev.defaultPrevented || document.fullscreenElement) return;
    const t = ev.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) {
      t.blur();                         // first Back leaves a text field
      return;
    }
    const before = overlays(), url = location.href;
    const back = () => { if (location.href === url && history.length > 1) history.back(); };
    if (!before) return back();
    setTimeout(() => { if (overlays() >= before) back(); }, 200);
  });
})();
