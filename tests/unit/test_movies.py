"""Movies & TV's back end: Seerr's and TMDB's data become the same titles, people and seasons;
IMDb's ratings file is indexed and looked up; spoken names find the right title; TMDB is only
reached on its allowed paths."""

import gzip

import pytest

from couchbox.services import movies

ARRIVAL = {  # as Seerr sends it (camelCase): TMDB's data passed through, plus mediaInfo
    "id": 329865,
    "title": "Arrival",
    "originalTitle": "Arrival",
    "releaseDate": "2016-11-10",
    "runtime": 116,
    "imdbId": "tt2543164",
    "voteAverage": 7.6,
    "voteCount": 20087,
    "posterPath": "/p.jpg",
    "backdropPath": "/b.jpg",
    "genres": [{"id": 18, "name": "Drama"}, {"id": 878, "name": "Science Fiction"}],
    "overview": "A linguist is recruited.",
    "releases": {
        "results": [
            {"iso_3166_1": "FR", "release_dates": [{"certification": "TP"}]},
            {"iso_3166_1": "US", "release_dates": [{"certification": ""}, {"certification": "PG-13"}]},
        ]
    },
    "credits": {
        "cast": [
            {"id": 9273, "name": "Amy Adams", "character": "Louise Banks", "profilePath": "/a.jpg"},
            {"id": 17604, "name": "Jeremy Renner", "character": "Ian Donnelly", "profilePath": None},
        ],
        "crew": [
            {"id": 137427, "name": "Denis Villeneuve", "job": "Director"},
            {"id": 115033, "name": "Eric Heisserer", "job": "Screenplay"},
            {"id": 1, "name": "Someone", "job": "Grip"},
        ],
    },
    "relatedVideos": [{"site": "YouTube", "type": "Teaser", "key": "tease"}, {"site": "YouTube", "type": "Trailer", "key": "trail"}],
    "mediaInfo": {"status": 5, "jellyfinMediaId": "abc123"},
}


class FakeSeerr:
    def __init__(self):
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        if path == "/movie/329865":
            return ARRIVAL
        if path == "/movie/329865/ratingscombined":
            return {
                "rt": {"criticsScore": 94, "audienceScore": 83, "criticsRating": "Certified Fresh"},
                "imdb": {"criticsScore": 7.9, "criticsScoreCount": 883621},
            }
        if path.endswith(("/recommendations", "/similar")):
            return {
                "results": [
                    {"id": 2103, "mediaType": "movie", "title": "Solaris", "releaseDate": "1972-03-20", "voteAverage": 8, "voteCount": 900}
                ]
            }
        if path.startswith("/search?"):
            return {
                "results": [
                    {
                        "id": 10547,
                        "mediaType": "movie",
                        "title": "The Arrival",
                        "releaseDate": "1996-05-31",
                        "voteCount": 600,
                        "popularity": 3,
                    },
                    {
                        "id": 329865,
                        "mediaType": "movie",
                        "title": "Arrival",
                        "releaseDate": "2016-11-10",
                        "voteCount": 20087,
                        "popularity": 26,
                    },
                    {
                        "id": 1373737,
                        "mediaType": "person",
                        "name": "Florence Pugh",
                        "knownForDepartment": "Acting",
                        "popularity": 40,
                        "knownFor": [{"title": "Midsommar"}, {"title": "Little Women"}],
                    },
                    {"id": 9, "mediaType": "movie", "title": "Adult thing", "adult": True},
                ]
            }
        raise RuntimeError(f"unexpected {path}")


def test_seerr_title_is_normalised():
    get = FakeSeerr()
    m = movies.Movies(movies.Seerr(get))
    t = m.title("movie", 329865)
    assert t["title"] == "Arrival" and t["year"] == "2016" and t["runtime"] == 116
    assert t["certification"] == "PG-13" and t["genres"] == ["Drama", "Science Fiction"]
    assert [p["name"] for p in t["directors"]] == ["Denis Villeneuve"]
    assert [p["name"] for p in t["writers"]] == ["Eric Heisserer"]
    assert t["cast"][0] == {"id": 9273, "name": "Amy Adams", "role": "Louise Banks", "image": movies.IMG + "w185/a.jpg"}
    assert "Grip" not in [c["role"] for c in t["crew"]]
    assert t["poster"].endswith("w500/p.jpg") and t["trailer"] == "trail"
    assert t["ratings"]["imdb"] == {"rating": 7.9, "votes": 883621}  # Seerr's, with no IMDb index yet
    assert t["ratings"]["rt"] == {"critics": 94, "audience": 83, "fresh": "Certified Fresh"}
    assert t["ratings"]["tmdb"] == {"score": 7.6, "votes": 20087}
    assert t["available"] == "available" and t["jellyfin_id"] == "abc123"
    assert t["recommendations"][0]["title"] == "Solaris" and t["source"] == "seerr"


def test_imdb_index_wins_over_seerr(tmp_path):
    r = ratings_file(tmp_path, [("tt2543164", "8.0", "900000")])
    t = movies.Movies(movies.Seerr(FakeSeerr()), r).title("movie", 329865)
    assert t["ratings"]["imdb"] == {"rating": 8.0, "votes": 900000}


def test_search_sorts_people_and_titles_and_drops_adult():
    r = movies.Movies(movies.Seerr(FakeSeerr())).search("arrival")
    assert [c["title"] for c in r["movies"]] == ["The Arrival", "Arrival"]
    assert r["people"][0]["title"] == "Florence Pugh" and r["people"][0]["sub"] == "Midsommar, Little Women"
    assert r["tv"] == []


def test_find_prefers_the_exact_title_then_the_popular_one():
    m = movies.Movies(movies.Seerr(FakeSeerr()))
    assert m.find("arrival")["id"] == 329865
    assert m.find("Arrival!")["id"] == 329865
    assert m.find("florence pugh", "person")["id"] == 1373737


def test_tmdb_source_gives_the_same_shapes():
    seen = []

    def get(path):
        seen.append(path)
        d = movies.snake(dict(ARRIVAL))
        d.pop("releases")
        d.pop("media_info")
        d.pop("related_videos")
        d["release_dates"] = {"results": [{"iso_3166_1": "US", "release_dates": [{"certification": "PG-13"}]}]}
        d["recommendations"] = {"results": [{"id": 2103, "title": "Solaris", "release_date": "1972-03-20"}]}
        d["similar"] = {"results": []}
        d["videos"] = {"results": [{"site": "YouTube", "type": "Trailer", "key": "trail"}]}
        return d

    t = movies.Movies(movies.Tmdb(get)).title("movie", 329865)
    assert "append_to_response=credits,external_ids,recommendations,similar,videos,release_dates" in seen[0]
    assert t["certification"] == "PG-13" and t["trailer"] == "trail" and t["recommendations"][0]["title"] == "Solaris"
    assert t["available"] == "" and t["ratings"]["rt"] is None and t["source"] == "tmdb"


def test_person_work_by_department():
    p = movies.person_detail(
        {
            "id": 137427,
            "name": "Denis Villeneuve",
            "known_for_department": "Directing",
            "biography": " Canadian. ",
            "combined_credits": {
                "cast": [
                    {
                        "id": 5,
                        "media_type": "tv",
                        "name": "Late Show",
                        "first_air_date": "2016-01-01",
                        "character": "Self",
                        "genre_ids": [10767],
                        "vote_count": 99999,
                        "episode_count": 2,
                    }
                ],
                "crew": [
                    {
                        "id": 1,
                        "media_type": "movie",
                        "title": "Arrival",
                        "release_date": "2016-11-10",
                        "job": "Director",
                        "department": "Directing",
                        "vote_count": 20000,
                    },
                    {
                        "id": 2,
                        "media_type": "movie",
                        "title": "Dune: Part Three",
                        "release_date": "",
                        "job": "Director",
                        "department": "Directing",
                        "vote_count": 0,
                    },
                    {
                        "id": 3,
                        "media_type": "movie",
                        "title": "Prisoners",
                        "release_date": "2013-09-19",
                        "job": "Director",
                        "department": "Directing",
                        "vote_count": 12000,
                    },
                    {
                        "id": 4,
                        "media_type": "movie",
                        "title": "Dune",
                        "release_date": "2021-09-15",
                        "job": "Screenplay",
                        "department": "Writing",
                        "vote_count": 15000,
                    },
                    {
                        "id": 4,
                        "media_type": "movie",
                        "title": "Dune",
                        "release_date": "2021-09-15",
                        "job": "Writer",
                        "department": "Writing",
                        "vote_count": 15000,
                    },
                ],
            },
        }
    )
    assert [t["dept"] for t in p["tabs"]] == ["Directing", "Acting", "Writing"]
    assert [c["title"] for c in p["credits"]["Directing"]] == ["Dune: Part Three", "Arrival", "Prisoners"]  # undated (upcoming) first
    assert p["credits"]["Writing"] == [dict(p["credits"]["Writing"][0], role="Screenplay, Writer")] and len(p["credits"]["Writing"]) == 1
    assert [c["title"] for c in p["known_for"]] == ["Arrival", "Prisoners", "Dune: Part Three"]  # their department, no talk shows
    assert p["bio"] == "Canadian."


def ratings_file(tmp_path, rows):
    src = tmp_path / "title.ratings.tsv.gz"
    with gzip.open(src, "wt") as f:
        f.write("tconst\taverageRating\tnumVotes\n")
        for row in rows:
            f.write("\t".join(row) + "\n")
    r = movies.ImdbRatings(tmp_path / "cache/imdb-ratings.bin")
    assert r.refresh(url=src.as_uri())
    return r


def test_imdb_ratings_index(tmp_path):
    r = ratings_file(
        tmp_path,
        [
            ("tt0000009", "5.3", "220"),
            ("tt2543164", "7.9", "883621"),
            ("tt0000001", "5.7", "2100"),
            ("tt0000002", "5.5", "3"),
            ("bad", "x", "y"),
        ],
    )
    assert r.get("tt2543164") == {"rating": 7.9, "votes": 883621}
    assert r.get("tt0000001") == {"rating": 5.7, "votes": 2100} and r.get("tt0000009")["votes"] == 220
    assert r.get("tt0000002") is None  # too few votes to keep
    assert r.get("tt7777777") is None and r.get("") is None and r.get("nm123") is None
    assert r.refresh(url="file:///nonexistent") is False  # fresh enough: no download


def test_tmdb_get_allows_reads_only(monkeypatch):
    calls = []

    class R:
        status_code = 200

        def json(self):
            return {"ok": 1}

    monkeypatch.setattr(movies.requests, "get", lambda url, headers, timeout: calls.append((url, headers)) or R())
    assert movies.tmdb_get("/movie/1?append_to_response=credits", "eyJlong.jwt.token") == {"ok": 1}
    assert calls[-1] == (
        movies.TMDB_API + "/movie/1?append_to_response=credits",
        {"Accept": "application/json", "Authorization": "Bearer eyJlong.jwt.token"},
    )
    movies.tmdb_get("/search/multi?query=x", "v3key")
    assert calls[-1][0].endswith("/search/multi?query=x&api_key=v3key")
    for bad in ("/account", "/authentication/token/new", "/movie/../account", "/movie/%2e%2e/x"):
        with pytest.raises(RuntimeError):
            movies.tmdb_get(bad, "k")


def test_demo_has_every_screen(tmp_path):
    m = movies.Movies(movies.Demo(), movies.demo_ratings(tmp_path / "d.bin"))
    assert len(m.home()["rows"]) == 6
    t = m.title("tv", 201)
    assert t["seasons"][0]["n"] == 1 and t["creators"] and t["ratings"]["imdb"]["rating"] > 8
    assert len(m.season(201, 1)["episodes"]) == 8
    p = m.person(303)
    assert p["tabs"][0]["dept"] == "Directing" and p["known_for"]
    assert m.top("movie")["items"][0]["rank"] == 1
