"""Movies & TV: look up movies, shows and the people in them, for the TV app (couchbox-movies)
and the voice assistant's movies tool.

Data comes from TMDB (The Movie Database), either through the box's Seerr (which proxies TMDB
and also knows what's already in Jellyfin) or, on a box without Seerr, with a TMDB API key
(Settings → Apps → Movies & TV). Seerr is preferred when it's set up.

The TV app runs as the TV user, which can't read the root-only keys, so it goes through
couchbox-voice's allow-listed proxy on 127.0.0.1:8790 (/seerr/... and /tmdb/...), which adds
them. The voice assistant runs as root and calls Seerr / TMDB directly.

IMDb ratings come from IMDb's own non-commercial dataset (title.ratings.tsv.gz, refreshed
daily, free for personal use): the app downloads it at most once a day into a small index
(ImdbRatings) and looks titles up by their IMDb id, which TMDB provides. Movies also get Rotten
Tomatoes (and IMDb, when the index is missing) from Seerr's ratings endpoint.

Everything is normalised into a few plain shapes (card, title, person, season) so the QML
and the voice tool don't care where the data came from."""

import gzip
import mmap
import os
import re
import struct
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

IMG = "https://image.tmdb.org/t/p/"
PROXY = "http://127.0.0.1:8790"
TMDB_API = "https://api.themoviedb.org/3"
IMDB_RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
CREDIT_IMDB = "Information courtesy of IMDb (https://www.imdb.com). Used with permission."
CREDIT_TMDB = "This product uses the TMDB API but is not endorsed or certified by TMDB."
# the paths the TV app may read from TMDB through couchbox-voice's proxy
TMDB_GET = ("/trending/", "/movie/", "/tv/", "/person/", "/search/", "/discover/", "/genre/", "/configuration")
TALK = {10767, 10763}  # TMDB's talk and news genres: not what someone is "known for"


class NotSetUp(Exception):
    """Neither Seerr nor a TMDB key is set up."""


def snake(o):
    """Seerr's camelCase keys as TMDB's snake_case ones (Seerr passes TMDB's data through)."""
    if isinstance(o, list):
        return [snake(x) for x in o]
    if isinstance(o, dict):
        return {re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", k).lower(): snake(v) for k, v in o.items()}
    return o


def img(path, size="w342"):
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return IMG + size + "/" + path.lstrip("/")


def year(date):
    return (date or "")[:4]


# ------------------------------------------------------------------ getters
def proxy_get(prefix, timeout=20):
    """GET through couchbox-voice's proxy (the TV app): prefix is "/seerr" or "/tmdb"."""

    def get(path):
        r = requests.get(PROXY + prefix + path, headers={"X-Couchbox": "1"}, timeout=timeout)
        try:
            body = r.json()
        except ValueError:
            body = {}
        if r.status_code >= 400 or (isinstance(body, dict) and "error" in body and len(body) == 1):
            raise RuntimeError(body.get("error") if isinstance(body, dict) else f"HTTP {r.status_code}")
        return body

    return get


def tmdb_get(path, token, timeout=20):
    """TMDB directly: a v4 read access token (Bearer) or a v3 API key (api_key=)."""
    if not path.startswith(TMDB_GET) or ".." in urllib.parse.unquote(path):
        raise RuntimeError("not allowed")
    headers, url = {"Accept": "application/json"}, TMDB_API + path
    if token.startswith("eyJ"):
        headers["Authorization"] = "Bearer " + token
    else:
        url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(token)
    r = requests.get(url, headers=headers, timeout=timeout)
    if r.status_code == 401:
        raise RuntimeError("TMDB refused the key (Settings → Apps → Movies & TV).")
    if r.status_code >= 400:
        raise RuntimeError(f"TMDB said {r.status_code}")
    return r.json()


# ------------------------------------------------------------------ sources (raw TMDB-shaped data)
class Seerr:
    name = "seerr"

    def __init__(self, get):
        self._get = get

    def get(self, path):
        return snake(self._get(path))

    def trending(self):
        return self.get("/discover/trending")["results"]

    def popular(self, kind):
        return self.get("/discover/movies" if kind == "movie" else "/discover/tv")["results"]

    def top_rated(self, kind, page=1):
        votes = 3000 if kind == "movie" else 800
        base = "/discover/movies" if kind == "movie" else "/discover/tv"
        return self.get(f"{base}?page={page}&sortBy=vote_average.desc&voteCountGte={votes}")["results"]

    def upcoming(self):
        return self.get("/discover/movies/upcoming")["results"]

    def search(self, query):
        return self.get("/search?query=" + urllib.parse.quote(query) + "&page=1")["results"]

    def detail(self, kind, tid):
        with ThreadPoolExecutor(4) as pool:
            d = pool.submit(self.get, f"/{kind}/{tid}")
            rec = pool.submit(self._list, f"/{kind}/{tid}/recommendations")
            sim = pool.submit(self._list, f"/{kind}/{tid}/similar")
            rat = pool.submit(self._ratings, kind, tid)
            out = d.result()
            out["recommendations"], out["similar"], out["seerr_ratings"] = rec.result(), sim.result(), rat.result()
        return out

    def _list(self, path):
        try:
            return self.get(path)["results"]
        except Exception:
            return []

    def _ratings(self, kind, tid):
        try:
            if kind == "movie":
                return self.get(f"/movie/{tid}/ratingscombined")
            return {"rt": self.get(f"/tv/{tid}/ratings")}
        except Exception:
            return {}

    def season(self, tid, n):
        return self.get(f"/tv/{tid}/season/{n}")

    def person(self, pid):
        with ThreadPoolExecutor(2) as pool:
            p = pool.submit(self.get, f"/person/{pid}")
            c = pool.submit(self.get, f"/person/{pid}/combined_credits")
            out = p.result()
            out["combined_credits"] = c.result()
        return out


class Tmdb:
    name = "tmdb"

    def __init__(self, get):
        self.get = get

    def trending(self):
        return self.get("/trending/all/week")["results"]

    def popular(self, kind):
        return self.get(f"/{kind}/popular")["results"]

    def top_rated(self, kind, page=1):
        return self.get(f"/{kind}/top_rated?page={page}")["results"]

    def upcoming(self):
        return self.get("/movie/upcoming")["results"]

    def search(self, query):
        return self.get("/search/multi?include_adult=false&query=" + urllib.parse.quote(query))["results"]

    def detail(self, kind, tid):
        extra = "release_dates" if kind == "movie" else "content_ratings"
        d = self.get(f"/{kind}/{tid}?append_to_response=credits,external_ids,recommendations,similar,videos,{extra}")
        d["recommendations"] = (d.get("recommendations") or {}).get("results", [])
        d["similar"] = (d.get("similar") or {}).get("results", [])
        d["related_videos"] = [dict(v, url="") for v in (d.get("videos") or {}).get("results", [])]
        return d

    def season(self, tid, n):
        return self.get(f"/tv/{tid}/season/{n}")

    def person(self, pid):
        return self.get(f"/person/{pid}?append_to_response=combined_credits,external_ids")


# ------------------------------------------------------------------ IMDb ratings (IMDb's dataset)
class ImdbRatings:
    """IMDb's title.ratings dataset as a sorted file of (tconst, rating x10, votes) records,
    looked up by binary search. Refreshed at most once a day (refresh())."""

    REC = struct.Struct("<IHI")
    MIN_VOTES = 5

    def __init__(self, path):
        self.path = Path(path)

    def age(self):
        try:
            return time.time() - self.path.stat().st_mtime
        except OSError:
            return float("inf")

    def refresh(self, max_age=86400, url=IMDB_RATINGS_URL):
        """Download and index the dataset if ours is older than max_age. True if it changed."""
        if self.age() < max_age:
            return False
        rows = []
        req = urllib.request.Request(url, headers={"User-Agent": "Couchbox"})
        with urllib.request.urlopen(req, timeout=120) as r, gzip.GzipFile(fileobj=r) as g:
            next(g, None)  # the header line
            for line in g:
                t, _, rest = line.partition(b"\t")
                rating, _, votes = rest.partition(b"\t")
                try:
                    n, v = int(t[2:]), int(votes)
                except ValueError:
                    continue
                if v >= self.MIN_VOTES:
                    rows.append((n, round(float(rating) * 10), v))
        if not rows:
            raise RuntimeError("IMDb's ratings file was empty")
        rows.sort()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            for row in rows:
                f.write(self.REC.pack(*row))
        os.replace(tmp, self.path)
        return True

    def get(self, imdb_id):
        """{"rating": 7.9, "votes": 883621} for "tt2543164", or None."""
        m = re.fullmatch(r"tt(\d+)", imdb_id or "")
        if not m:
            return None
        want = int(m.group(1))
        size = self.REC.size
        try:
            with open(self.path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                lo, hi = 0, len(mm) // size
                while lo < hi:
                    mid = (lo + hi) // 2
                    n, rating, votes = self.REC.unpack_from(mm, mid * size)
                    if n == want:
                        return {"rating": rating / 10, "votes": votes}
                    if n < want:
                        lo = mid + 1
                    else:
                        hi = mid
        except (OSError, ValueError):
            pass
        return None


def ratings_path(home=None):
    home = Path(home or os.path.expanduser("~"))
    return home / ".cache/couchbox-movies/imdb-ratings.bin"


# ------------------------------------------------------------------ normalising
def card(x, kind=None):
    """One poster (or person) in a row: {type, id, title, year, poster, score, ...}."""
    t = x.get("media_type") or kind or ("tv" if "first_air_date" in x or "name" in x and "title" not in x else "movie")
    if t == "person":
        known = [k.get("title") or k.get("name") for k in (x.get("known_for") or []) if k.get("title") or k.get("name")]
        return {
            "type": "person",
            "id": x.get("id"),
            "title": x.get("name") or "",
            "image": img(x.get("profile_path"), "w185"),
            "sub": ", ".join(known[:2]) or x.get("known_for_department") or "",
            "dept": x.get("known_for_department") or "",
            "popularity": x.get("popularity") or 0,
        }
    date = x.get("release_date") or x.get("first_air_date") or ""
    votes = x.get("vote_count") or 0
    return {
        "type": t,
        "id": x.get("id"),
        "title": x.get("title") or x.get("name") or "",
        "year": year(date),
        "date": date,
        "poster": img(x.get("poster_path")),
        "backdrop": img(x.get("backdrop_path"), "w780"),
        "score": round(x.get("vote_average") or 0, 1) if votes else None,
        "votes": votes,
        "overview": x.get("overview") or "",
        "popularity": x.get("popularity") or 0,
    }


def cards(xs, kind=None, limit=20):
    out, seen = [], set()
    for x in xs or []:
        if x.get("adult") or not x.get("id"):
            continue
        c = card(x, kind)
        if (c["type"], c["id"]) in seen or c["type"] not in ("movie", "tv", "person"):
            continue
        seen.add((c["type"], c["id"]))
        out.append(c)
        if len(out) >= limit:
            break
    return out


def certification(d, kind):
    """The US rating (PG-13, TV-MA), from release_dates / content_ratings (TMDB) or releases (Seerr)."""
    if kind == "movie":
        for block in (d.get("release_dates") or d.get("releases") or {}).get("results") or []:
            if block.get("iso_3166_1") == "US":
                for r in block.get("release_dates") or []:
                    if r.get("certification"):
                        return r["certification"]
    else:
        for r in (d.get("content_ratings") or {}).get("results") or []:
            if r.get("iso_3166_1") == "US" and r.get("rating"):
                return r["rating"]
    return ""


WRITING = ("Screenplay", "Writer", "Story", "Novel", "Teleplay", "Characters", "Book", "Author")
KEY_CREW = (
    "Director",
    "Screenplay",
    "Writer",
    "Story",
    "Novel",
    "Creator",
    "Producer",
    "Executive Producer",
    "Original Music Composer",
    "Director of Photography",
    "Editor",
)


def people(xs, job=None, jobs=None, limit=12):
    out, seen = [], set()
    for c in xs or []:
        if (job and c.get("job") != job) or (jobs and c.get("job") not in jobs):
            continue
        if c.get("id") in seen:
            continue
        seen.add(c.get("id"))
        out.append({"id": c.get("id"), "name": c.get("name") or "", "image": img(c.get("profile_path"), "w185")})
        if len(out) >= limit:
            break
    return out


def title_detail(d, kind, source, imdb=None):
    """A movie or show, everything the title page shows."""
    credits = d.get("credits") or {}
    crew = credits.get("crew") or []
    imdb_id = d.get("imdb_id") or (d.get("external_ids") or {}).get("imdb_id") or ""
    cast = []
    for c in (credits.get("cast") or [])[:24]:
        role = c.get("character") or ", ".join(r.get("character", "") for r in c.get("roles") or [] if r.get("character"))
        cast.append({"id": c.get("id"), "name": c.get("name") or "", "role": role, "image": img(c.get("profile_path"), "w185")})
    key_crew, seen = [], set()
    for job in KEY_CREW:
        for c in crew:
            if c.get("job") == job and (c.get("id"), job) not in seen and len(key_crew) < 14:
                seen.add((c.get("id"), job))
                key_crew.append({"id": c.get("id"), "name": c.get("name") or "", "role": job, "image": img(c.get("profile_path"), "w185")})
    seasons = [
        {
            "n": s.get("season_number"),
            "name": s.get("name") or f"Season {s.get('season_number')}",
            "year": year(s.get("air_date")),
            "episodes": s.get("episode_count") or 0,
            "poster": img(s.get("poster_path")),
        }
        for s in d.get("seasons") or []
        if s.get("season_number") is not None
    ]
    seasons.sort(key=lambda s: (s["n"] == 0, s["n"]))  # Specials last
    trailer = ""
    for v in d.get("related_videos") or []:
        if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser") and v.get("key"):
            trailer = v["key"]
            if v.get("type") == "Trailer":
                break
    sr = d.get("seerr_ratings") or {}
    rt = sr.get("rt") or {}
    ratings = {"tmdb": {"score": round(d.get("vote_average") or 0, 1), "votes": d.get("vote_count") or 0} if d.get("vote_count") else None}
    ratings["imdb"] = (imdb.get(imdb_id) if imdb else None) or None
    if not ratings["imdb"] and (sr.get("imdb") or {}).get("critics_score"):
        ratings["imdb"] = {"rating": sr["imdb"]["critics_score"], "votes": sr["imdb"].get("critics_score_count") or 0}
    ratings["rt"] = (
        {"critics": rt.get("critics_score"), "audience": rt.get("audience_score"), "fresh": rt.get("critics_rating") or ""}
        if rt.get("critics_score") is not None
        else None
    )
    media = d.get("media_info") or {}
    status = {5: "available", 4: "partial", 3: "requested", 2: "requested", 1: ""}.get(media.get("status"), "")
    runtime = d.get("runtime") or (d.get("episode_run_time") or [0])[0] or 0
    end = d.get("last_air_date") if kind == "tv" and d.get("status") in ("Ended", "Canceled") else ""
    return {
        "type": kind,
        "id": d.get("id"),
        "title": d.get("title") or d.get("name") or "",
        "original": d.get("original_title") or d.get("original_name") or "",
        "year": year(d.get("release_date") or d.get("first_air_date")),
        "end_year": year(end),
        "date": d.get("release_date") or d.get("first_air_date") or "",
        "runtime": runtime,
        "genres": [g.get("name") for g in d.get("genres") or [] if g.get("name")],
        "overview": d.get("overview") or "",
        "tagline": d.get("tagline") or "",
        "poster": img(d.get("poster_path"), "w500"),
        "backdrop": img(d.get("backdrop_path"), "w1280"),
        "certification": certification(d, kind),
        "status": d.get("status") or "",
        "networks": [n.get("name") for n in d.get("networks") or [] if n.get("name")],
        "seasons_count": d.get("number_of_seasons") or 0,
        "episodes_count": d.get("number_of_episodes") or 0,
        "ratings": ratings,
        "imdb_id": imdb_id,
        "directors": people(crew, job="Director", limit=4),
        "creators": [
            {"id": c.get("id"), "name": c.get("name") or "", "image": img(c.get("profile_path"), "w185")} for c in d.get("created_by") or []
        ],
        "writers": people(crew, jobs=WRITING, limit=4),
        "cast": cast,
        "crew": key_crew,
        "seasons": seasons,
        "recommendations": cards(d.get("recommendations"), kind),
        "similar": cards(d.get("similar"), kind),
        "trailer": trailer,
        "available": status,
        "jellyfin_id": media.get("jellyfin_media_id") or "",
        "source": source,
    }


DEPTS = (
    "Acting",
    "Directing",
    "Writing",
    "Production",
    "Creator",
    "Sound",
    "Camera",
    "Editing",
    "Art",
    "Crew",
    "Visual Effects",
    "Costume & Make-Up",
    "Lighting",
)


def person_detail(p, imdb=None):
    """A person: facts, bio, what they're known for, and their work by department, newest first."""
    cc = p.get("combined_credits") or {}
    by = {}

    def add(dept, x, role):
        c = card(x)
        if c["type"] not in ("movie", "tv") or x.get("adult"):
            return
        c["role"] = role or ""
        c["episodes"] = x.get("episode_count") or 0
        c["talk"] = bool(set(x.get("genre_ids") or []) & TALK) or role in ("Self", "Himself", "Herself")
        lst = by.setdefault(dept, [])
        for old in lst:  # one row per title: several jobs, or several characters, join up
            if old["type"] == c["type"] and old["id"] == c["id"]:
                if c["role"] and c["role"] not in old["role"].split(", "):
                    old["role"] = ", ".join(r for r in (old["role"], c["role"]) if r)
                old["episodes"] = max(old["episodes"], c["episodes"])
                return
        lst.append(c)

    for x in cc.get("cast") or []:
        add("Acting", x, x.get("character"))
    for x in cc.get("crew") or []:
        add(x.get("department") or "Crew", x, x.get("job"))
    for lst in by.values():  # newest first; titles with no date yet (in development) on top
        lst.sort(key=lambda c: c["date"] or "9999", reverse=True)
    dept = p.get("known_for_department") or "Acting"
    tabs = sorted(by, key=lambda d: (d != dept, DEPTS.index(d) if d in DEPTS else 99))
    pool = [c for c in by.get(dept) or [c for d in by.values() for c in d] if not c["talk"]]
    known, seen = [], set()
    for c in sorted(pool, key=lambda c: (c["votes"] or 0), reverse=True):
        if (c["type"], c["id"]) not in seen:
            seen.add((c["type"], c["id"]))
            known.append(c)
        if len(known) >= 16:
            break
    imdb_id = p.get("imdb_id") or (p.get("external_ids") or {}).get("imdb_id") or ""
    return {
        "type": "person",
        "id": p.get("id"),
        "name": p.get("name") or "",
        "image": img(p.get("profile_path"), "h632"),
        "bio": (p.get("biography") or "").strip(),
        "born": p.get("birthday") or "",
        "died": p.get("deathday") or "",
        "place": p.get("place_of_birth") or "",
        "dept": dept,
        "imdb_id": imdb_id,
        "known_for": known,
        "credits": {d: by[d] for d in tabs},
        "tabs": [{"dept": d, "count": len(by[d])} for d in tabs],
    }


def season_detail(s, tid):
    eps = []
    for e in s.get("episodes") or []:
        eps.append(
            {
                "n": e.get("episode_number"),
                "name": e.get("name") or "",
                "date": e.get("air_date") or "",
                "overview": e.get("overview") or "",
                "score": round(e.get("vote_average") or 0, 1) if e.get("vote_count") else None,
                "runtime": e.get("runtime") or 0,
                "still": img(e.get("still_path"), "w300"),
            }
        )
    return {
        "id": tid,
        "n": s.get("season_number"),
        "name": s.get("name") or "",
        "overview": s.get("overview") or "",
        "year": year(s.get("air_date")),
        "poster": img(s.get("poster_path")),
        "episodes": eps,
    }


# ------------------------------------------------------------------ the service
class Movies:
    def __init__(self, source=None, ratings=None):
        self.source = source
        self.ratings = ratings

    @classmethod
    def for_app(cls, seerr_url="", demo=False):
        """The TV app: Seerr (through the proxy) if Seerr is set up, else TMDB (through the proxy)."""
        if demo:
            import tempfile

            return cls(Demo(), demo_ratings(Path(tempfile.gettempdir()) / "couchbox-movies-demo/imdb-ratings.bin"))
        src = Seerr(proxy_get("/seerr")) if seerr_url else Tmdb(proxy_get("/tmdb"))
        return cls(src, ImdbRatings(ratings_path()))

    @classmethod
    def for_root(cls):
        """The voice assistant (root): Seerr or TMDB directly, and the TV user's IMDb index."""
        from couchbox import home, secrets, settings

        st = settings.load()
        rp = ImdbRatings(ratings_path(home.tv_home()))
        if st["media.seerr.url"] and secrets.is_set("media.seerr.api_key"):
            from couchbox.voice import tools

            return cls(Seerr(lambda path: tools.seerr_api("GET", path)), rp)
        token = secrets.get("media.tmdb.token")
        if token:
            return cls(Tmdb(lambda path: tmdb_get(path, token)), rp)
        raise NotSetUp("Movies & TV needs Seerr or a TMDB API key (Settings → Apps → Movies & TV).")

    @property
    def name(self):
        return self.source.name

    def status(self):
        try:
            self.source.trending()
            return {"ok": True, "source": self.name}
        except Exception as err:
            if self.name == "seerr":  # Seerr without its key: try TMDB
                tm = Tmdb(proxy_get("/tmdb"))
                try:
                    tm.trending()
                    self.source = tm
                    return {"ok": True, "source": "tmdb"}
                except Exception:
                    pass
            return {"ok": False, "source": self.name, "problem": str(err)}

    def home(self):
        s = self.source
        rows = [
            ("trending", "Trending this week", lambda: cards(s.trending())),
            ("popular-movies", "Popular movies", lambda: cards(s.popular("movie"), "movie")),
            ("popular-tv", "Popular shows", lambda: cards(s.popular("tv"), "tv")),
            ("top-movies", "Top rated movies", lambda: cards(s.top_rated("movie"), "movie")),
            ("top-tv", "Top rated shows", lambda: cards(s.top_rated("tv"), "tv")),
            ("upcoming", "Coming soon", lambda: cards(s.upcoming(), "movie")),
        ]
        with ThreadPoolExecutor(6) as pool:
            futs = [(k, t, pool.submit(f)) for k, t, f in rows]
            out = []
            for k, t, fut in futs:
                try:
                    items = [c for c in fut.result() if c["type"] != "person"]
                except Exception:
                    items = []
                if items:
                    out.append({"key": k, "title": t, "items": items})
        if not out:
            raise RuntimeError("Couldn't load anything: " + ("is Seerr up?" if self.name == "seerr" else "is the TMDB key right?"))
        return {"rows": out}

    def top(self, kind, pages=3):
        out = []
        for page in range(1, pages + 1):
            try:
                out += self.source.top_rated(kind, page)
            except Exception:
                break
        items = cards(out, kind, limit=60)
        for i, c in enumerate(items):
            c["rank"] = i + 1
        return {"items": items}

    def search(self, query):
        res = self.source.search(query)
        found = cards(res, limit=60)
        return {
            "query": query,
            "people": [c for c in found if c["type"] == "person"][:20],
            "movies": [c for c in found if c["type"] == "movie"][:20],
            "tv": [c for c in found if c["type"] == "tv"][:20],
        }

    def title(self, kind, tid):
        if kind not in ("movie", "tv"):
            raise ValueError("kind is movie or tv")
        return title_detail(self.source.detail(kind, int(tid)), kind, self.name, self.ratings)

    def season(self, tid, n):
        return season_detail(self.source.season(int(tid), int(n)), int(tid))

    def person(self, pid):
        return person_detail(self.source.person(int(pid)), self.ratings)

    def find(self, query, kind=None):
        """The best match for a spoken name: exact titles first, then the most popular."""
        res = cards(self.source.search(query), limit=40)
        if kind:
            res = [c for c in res if c["type"] == kind] or res
        if not res:
            return None
        q = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
        exact = [c for c in res if re.sub(r"[^a-z0-9]+", " ", c["title"].lower()).strip() == q]
        pool = exact or res[:5]
        return max(pool, key=lambda c: (c.get("votes") or 0) + (c.get("popularity") or 0) * 10)

    def refresh_ratings(self):
        if self.ratings:
            try:
                self.ratings.refresh()
            except Exception as err:
                print(f"IMDb ratings: {err}", flush=True)


# ------------------------------------------------------------------ demo data (tests, screenshots)
DEMO_TITLES = [
    ("movie", 101, "The Long Harbor", "2024-03-08", 8.1, 5400, [18, 9648]),
    ("movie", 102, "Signal Over Ashby", "2023-10-20", 7.4, 3100, [878, 53]),
    ("movie", 103, "Paper Orchards", "2025-06-13", 7.8, 2200, [18]),
    ("movie", 104, "Night Ferry to Corvo", "2022-01-14", 6.9, 1800, [53, 80]),
    ("movie", 105, "A Quiet Kind of Thunder", "2024-11-01", 8.4, 9100, [18, 10749]),
    ("movie", 106, "Lanterns", "2021-07-09", 7.1, 4100, [16, 10751]),
    ("movie", 107, "The Cartographer's Daughter", "2026-12-18", 0, 0, [12, 14]),
    ("tv", 201, "Saltmarsh", "2022-02-17", 8.6, 2800, [18, 9648]),
    ("tv", 202, "The Ninth Floor", "2023-09-05", 8.0, 1500, [35]),
    ("tv", 203, "Low Orbit", "2024-04-11", 7.7, 900, [10765, 18]),
    ("tv", 204, "Kitchen Table", "2021-05-02", 7.3, 600, [35, 10751]),
    ("tv", 205, "Borderlands Patrol", "2020-08-30", 6.8, 750, [80, 18]),
]
DEMO_PEOPLE = [
    (301, "Mara Ellison", "Acting"),
    (302, "Tomas Reyes", "Acting"),
    (303, "Ines Okafor", "Directing"),
    (304, "Wren Haddad", "Acting"),
    (305, "Jonah Achterberg", "Writing"),
    (306, "Priya Lindqvist", "Acting"),
]
DEMO_ROLES = ["Nell Harrow", "Captain Ade", "Dr. Ruth Calder", "Simon", "The Ferryman", "Ana", "Detective Moss"]


def _demo_item(t):
    kind, tid, title, date, score, votes, genres = t
    d = {
        "id": tid,
        "media_type": kind,
        "overview": f"{title}: a made-up {('film' if kind == 'movie' else 'series')} for screenshots and tests.",
        "vote_average": score,
        "vote_count": votes,
        "genre_ids": genres,
        "popularity": votes / 100,
        "poster_path": None,
        "backdrop_path": None,
    }
    d["title" if kind == "movie" else "name"] = title
    d["release_date" if kind == "movie" else "first_air_date"] = date
    return d


class Demo:
    """Made-up titles and people in TMDB's shapes (no network)."""

    name = "demo"

    def trending(self):
        return [_demo_item(t) for t in DEMO_TITLES[::2] + DEMO_TITLES[1::2]]

    def popular(self, kind):
        return [_demo_item(t) for t in DEMO_TITLES if t[0] == kind]

    def top_rated(self, kind, page=1):
        if page > 1:
            return []
        return sorted(self.popular(kind), key=lambda d: -d["vote_average"])

    def upcoming(self):
        return [_demo_item(t) for t in DEMO_TITLES if t[0] == "movie"][::-1]

    def search(self, query):
        q = query.lower()
        out = [_demo_item(t) for t in DEMO_TITLES if q in t[2].lower()]
        out += [
            {
                "id": i,
                "media_type": "person",
                "name": n,
                "known_for_department": d,
                "profile_path": None,
                "known_for": [_demo_item(DEMO_TITLES[i % 7])],
            }
            for i, n, d in DEMO_PEOPLE
            if q in n.lower()
        ]
        return out or [_demo_item(t) for t in DEMO_TITLES[:6]]

    def detail(self, kind, tid):
        t = next((t for t in DEMO_TITLES if t[1] == tid), DEMO_TITLES[0] if kind == "movie" else DEMO_TITLES[7])
        d = _demo_item(t)
        d.update(
            {
                "runtime": 118 if kind == "movie" else 0,
                "episode_run_time": [52] if kind == "tv" else [],
                "genres": [{"name": n} for n in (["Drama", "Mystery"] if t[6][0] == 18 else ["Science Fiction", "Thriller"])],
                "tagline": "Every tide brings something back.",
                "imdb_id": f"tt{9000000 + tid}",
                "status": "Ended" if kind == "tv" else "Released",
                "last_air_date": "2025-03-20",
                "number_of_seasons": 3,
                "number_of_episodes": 26,
                "networks": [{"name": "Northlight"}] if kind == "tv" else [],
                "created_by": [{"id": 305, "name": "Jonah Achterberg"}] if kind == "tv" else [],
                "release_dates": {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "PG-13"}]}]},
                "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]},
                "credits": {
                    "cast": [
                        {"id": i, "name": n, "character": DEMO_ROLES[k % len(DEMO_ROLES)], "profile_path": None}
                        for k, (i, n, _) in enumerate(DEMO_PEOPLE)
                    ],
                    "crew": [
                        {"id": 303, "name": "Ines Okafor", "job": "Director"},
                        {"id": 305, "name": "Jonah Achterberg", "job": "Screenplay"},
                        {"id": 303, "name": "Ines Okafor", "job": "Producer"},
                    ],
                },
                "seasons": [
                    {"season_number": n, "name": f"Season {n}", "air_date": f"{2021 + n}-02-17", "episode_count": 8 + n} for n in (1, 2, 3)
                ]
                if kind == "tv"
                else [],
                "recommendations": [_demo_item(x) for x in DEMO_TITLES if x[0] == kind and x[1] != tid],
                "similar": [_demo_item(x) for x in DEMO_TITLES if x[0] == kind and x[1] != tid][::-1],
                "related_videos": [],
                "seerr_ratings": {
                    "rt": {"critics_score": 91, "audience_score": 84, "critics_rating": "Certified Fresh"},
                    "imdb": {"critics_score": 7.9, "critics_score_count": 48210},
                },
                "media_info": {"status": 5 if tid % 2 else 1, "jellyfin_media_id": "demo" if tid % 2 else None},
            }
        )
        return d

    def season(self, tid, n):
        return {
            "season_number": n,
            "name": f"Season {n}",
            "air_date": f"{2021 + n}-02-17",
            "overview": "The tide turns.",
            "episodes": [
                {
                    "episode_number": e,
                    "name": t,
                    "air_date": f"{2021 + n}-0{1 + e // 4}-{10 + e:02d}",
                    "overview": "Nell finds a letter that shouldn't exist, and the harbour master starts asking questions.",
                    "vote_average": 7.2 + e / 10,
                    "vote_count": 40,
                    "runtime": 52,
                }
                for e, t in enumerate(
                    ["Low Water", "The Letter", "Harbour Lights", "Undertow", "Ashore", "Salt", "The Keeper", "High Water"], 1
                )
            ],
        }

    def person(self, pid):
        i, name, dept = next((p for p in DEMO_PEOPLE if p[0] == pid), DEMO_PEOPLE[0])
        cast = [
            dict(_demo_item(t), character=DEMO_ROLES[k % len(DEMO_ROLES)], episode_count=8 if t[0] == "tv" else 0)
            for k, t in enumerate(DEMO_TITLES)
            if (k + i) % 3
        ]
        crew = [dict(_demo_item(t), department="Directing", job="Director") for t in DEMO_TITLES[:3]] if dept == "Directing" else []
        return {
            "id": i,
            "name": name,
            "known_for_department": dept,
            "birthday": "1988-04-12",
            "place_of_birth": "Galway, Ireland",
            "biography": f"{name} is a made-up {dept.lower()} talent for Couchbox's screenshots. Trained on stage before a "
            "breakout role in The Long Harbor, and has since moved between film and television, with a soft spot for slow-burn mysteries.",
            "profile_path": None,
            "imdb_id": f"nm{8000000 + i}",
            "combined_credits": {"cast": cast, "crew": crew},
        }


def demo_ratings(path):
    """An IMDb index with the demo titles in it (screenshots, tests)."""
    r = ImdbRatings(path)
    if r.age() == float("inf"):
        r.path.parent.mkdir(parents=True, exist_ok=True)
        with open(r.path, "wb") as f:
            for t in sorted(DEMO_TITLES, key=lambda t: t[1]):
                f.write(ImdbRatings.REC.pack(9000000 + t[1], round((t[4] or 7) * 10 + 2), t[5] * 9 + 120))
    return r
