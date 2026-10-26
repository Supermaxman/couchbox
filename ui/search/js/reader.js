// couchbox-search reader: the article on this page, as JSON (run with runJavaScript; the
// result is the last expression). A small readability-style pass: find the block with the
// most paragraph text, then take its headings, paragraphs, list items, quotes and code in
// order, skipping navigation, asides, forms, hidden and link-heavy parts.
(() => {
  const SKIP = "nav,aside,footer,header,form,button,script,style,noscript,svg,figure figcaption,[role=navigation],[role=banner],[role=complementary],[aria-hidden=true],.share,.social,.comments,.related,.newsletter,.advert,.ad";
  const visible = el => { const s = getComputedStyle(el); return s.display !== "none" && s.visibility !== "hidden"; };
  const textLen = el => (el.innerText || "").trim().length;
  const linkLen = el => [...el.querySelectorAll("a")].reduce((n, a) => n + (a.innerText || "").length, 0);
  let best = document.querySelector("article") || document.querySelector("[role=main]") || document.querySelector("main");
  if (!best || textLen(best) < 400) {
    let score = 0;
    for (const p of document.querySelectorAll("p")) {
      const parent = p.parentElement;
      if (!parent) continue;
      const s = [...parent.children].filter(c => c.tagName === "P").reduce((n, c) => n + textLen(c), 0);
      if (s > score) { score = s; best = parent; }
    }
  }
  best = best || document.body;
  const blocks = [];
  const walk = el => {
    for (const c of el.children) {
      if (c.matches(SKIP) || !visible(c)) continue;
      const tag = c.tagName;
      const t = (c.innerText || "").trim();
      if (/^H[1-4]$/.test(tag)) { if (t) blocks.push({k: "h", t: t}); continue; }
      if (tag === "P") { if (t && linkLen(c) < t.length * 0.6) blocks.push({k: "p", t: t}); continue; }
      if (tag === "LI") { if (t && linkLen(c) < t.length * 0.6 && !c.querySelector("p,li")) { blocks.push({k: "li", t: t}); continue; } }
      if (tag === "BLOCKQUOTE") { if (t) blocks.push({k: "quote", t: t}); continue; }
      if (tag === "PRE") { if (t) blocks.push({k: "pre", t: c.innerText}); continue; }
      walk(c);
    }
  };
  walk(best);
  if (blocks.filter(b => b.k === "p").length < 2) {   // no article: the page's own text, by lines
    blocks.length = 0;
    for (const line of (document.body.innerText || "").split("\n")) if (line.trim().length > 40) blocks.push({k: "p", t: line.trim()});
  }
  const og = n => (document.querySelector(`meta[property="og:${n}"]`) || {}).content;
  return JSON.stringify({title: og("title") || document.title, site: og("site_name") || location.hostname.replace(/^www\./, ""),
                         url: location.href, blocks: blocks.slice(0, 1500)});
})()
