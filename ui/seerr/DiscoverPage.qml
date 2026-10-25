// Discover: the website's home rows, in its order.
import QtQuick

VPage {
    id: page
    // the website's studio and network rows (TMDB company / network ids)
    readonly property var studios: [{id: 2, name: "Disney"}, {id: 127928, name: "20th Century Studios"}, {id: 34, name: "Sony Pictures"},
        {id: 174, name: "Warner Bros. Pictures"}, {id: 33, name: "Universal"}, {id: 4, name: "Paramount"}, {id: 3, name: "Pixar"},
        {id: 521, name: "DreamWorks"}, {id: 420, name: "Marvel Studios"}, {id: 9993, name: "DC"}, {id: 41077, name: "A24"}]
    readonly property var networks: [{id: 213, name: "Netflix"}, {id: 2739, name: "Disney+"}, {id: 1024, name: "Prime Video"},
        {id: 2552, name: "Apple TV+"}, {id: 453, name: "Hulu"}, {id: 49, name: "HBO"}, {id: 4330, name: "Paramount+"},
        {id: 3353, name: "Peacock"}, {id: 64, name: "Discovery"}, {id: 174, name: "AMC"}, {id: 67, name: "Showtime"},
        {id: 318, name: "Starz"}, {id: 2, name: "ABC"}, {id: 6, name: "NBC"}, {id: 16, name: "CBS"}, {id: 19, name: "FOX"},
        {id: 56, name: "Cartoon Network"}, {id: 80, name: "Adult Swim"}, {id: 13, name: "Nickelodeon"}]
    property var movieGenres: []
    property var tvGenres: []
    Component.onCompleted: {
        S.get("/discover/genreslider/movie", r => movieGenres = r);
        S.get("/discover/genreslider/tv", r => tvGenres = r);
    }

    Column {
        width: parent.width
        y: 128 * S.u
        spacing: 22 * S.u
        Shelf { title: "Recently Added"; kind: "media"; path: "/media?filter=allavailable&sort=mediaAdded" }
        Shelf { title: "Recent Requests"; kind: "requests"; path: "/request?filter=all&sort=added"; more: "requests" }
        Shelf { title: "Your Watchlist"; kind: "watchlist"; path: "/discover/watchlist"; more: "/discover/watchlist"; maxPages: 1 }
        Shelf { title: "Trending"; path: "/discover/trending"; more: "/discover/trending" }
        Shelf { title: "Popular Movies"; path: "/discover/movies"; mediaType: "movie"; more: "/discover/movies" }
        Shelf { title: "Movie Genres"; kind: "genres"; mediaType: "movie"; items: page.movieGenres; visible: page.movieGenres.length > 0 }
        Shelf { title: "Upcoming Movies"; path: "/discover/movies/upcoming"; mediaType: "movie"; more: "/discover/movies/upcoming" }
        Shelf { title: "Studios"; kind: "companies"; mediaType: "movie"; items: page.studios }
        Shelf { title: "Popular Series"; path: "/discover/tv"; mediaType: "tv"; more: "/discover/tv" }
        Shelf { title: "Series Genres"; kind: "genres"; mediaType: "tv"; items: page.tvGenres; visible: page.tvGenres.length > 0 }
        Shelf { title: "Upcoming Series"; path: "/discover/tv/upcoming"; mediaType: "tv"; more: "/discover/tv/upcoming" }
        Shelf { title: "Networks"; kind: "companies"; mediaType: "tv"; items: page.networks }
    }
}
