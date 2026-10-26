// couchbox-search: the results on a Google results page (title, site, snippet), as JSON, for
// the optional AI answer above them. Read from the page as shown; nothing else is fetched.
(() => {
  const out = [], seen = new Set();
  for (const h of document.querySelectorAll("#search a h3, #rso a h3")) {
    const a = h.closest("a");
    if (!a || !a.href || seen.has(a.href)) continue;
    // results link through Google (/url, /goto) or straight to the site; anything else on google.* isn't a result
    if (/^https?:\/\/(www\.)?google\.[a-z.]+\//.test(a.href) && !/^https?:\/\/(www\.)?google\.[a-z.]+\/(url|goto)\?/.test(a.href)) continue;
    seen.add(a.href);
    const box = h.closest("div[data-hveid], .g, .MjjYud") || a.parentElement;
    const title = h.innerText.trim();
    let snippet = "";
    const s = box && box.querySelector("[data-sncf], .VwiC3b, [style*='-webkit-line-clamp']");
    if (s) snippet = s.innerText.trim();
    else if (box) snippet = box.innerText.replace(title, "").trim().split("\n").filter(l => l.length > 40).join(" ");
    let site = "";
    const cite = box && box.querySelector("cite");
    const shown = cite ? cite.innerText.split(/\s|›/)[0] : a.href;     // the address Google shows under the title
    try { site = new URL(/^https?:/.test(shown) ? shown : "https://" + shown).hostname.replace(/^www\./, ""); } catch (e) {}
    out.push({title: title, site: site, url: a.href, snippet: snippet.slice(0, 400)});
    if (out.length >= 8) break;
  }
  return JSON.stringify(out);
})()
