// The ratings in a row: IMDb (★ 7.9/10 · 884K), Rotten Tomatoes (critics, audience), TMDB.
import QtQuick

Row {
    id: scores
    property var ratings: ({})
    spacing: 34 * M.u
    readonly property var imdb: ratings ? ratings.imdb : null
    readonly property var rt: ratings ? ratings.rt : null
    readonly property var tmdb: ratings ? ratings.tmdb : null

    component Score: Column {
        id: sc
        property string label: ""
        property string value: ""
        property string unit: ""
        property string sub: ""
        property color tint: M.accent
        property string mark: ""
        spacing: 2 * M.u
        Text { text: sc.label; color: M.faint; font.family: M.font; font.pixelSize: 18 * M.u; font.weight: Font.Bold; font.letterSpacing: 1.5 * M.u }
        Row {
            spacing: 8 * M.u
            Text { visible: !!sc.mark; text: sc.mark; color: sc.tint; font.pixelSize: 30 * M.u; anchors.verticalCenter: big.verticalCenter }
            Text { id: big; text: sc.value; color: M.text; font.family: M.font; font.pixelSize: 36 * M.u; font.weight: Font.Bold }
            Text { visible: !!sc.unit; text: sc.unit; color: M.dim; font.family: M.font; font.pixelSize: 22 * M.u; anchors.baseline: big.baseline }
        }
        Text { visible: !!sc.sub; text: sc.sub; color: M.dim; font.family: M.font; font.pixelSize: 19 * M.u }
    }

    Score { visible: !!scores.imdb; label: "IMDB"; mark: "★"; value: scores.imdb ? Number(scores.imdb.rating).toFixed(1) : ""; unit: "/10"
            sub: scores.imdb && scores.imdb.votes ? M.votes(scores.imdb.votes) + " votes" : "" }
    Score { visible: !!(scores.rt && scores.rt.critics !== null && scores.rt.critics !== undefined); label: "CRITICS"; mark: "●"; tint: M.rt
            value: scores.rt ? scores.rt.critics + "%" : ""; sub: scores.rt ? (scores.rt.fresh || "Rotten Tomatoes") : "" }
    Score { visible: !!(scores.rt && scores.rt.audience); label: "AUDIENCE"; mark: "●"; tint: "#f59e0b"
            value: scores.rt && scores.rt.audience ? scores.rt.audience + "%" : ""; sub: "Rotten Tomatoes" }
    Score { visible: !!scores.tmdb; label: "TMDB"; value: scores.tmdb ? Math.round(scores.tmdb.score * 10) + "%" : ""; tint: M.good
            sub: scores.tmdb ? M.votes(scores.tmdb.votes) + " votes" : "" }
}
