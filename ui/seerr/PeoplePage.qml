// Full cast or crew of a movie or show (the website's /movie/<id>/cast and /crew):
// everyone as a person card, with their character or jobs.
import QtQuick

FocusScope {
    id: page
    property string title: ""
    property string path: ""                 // people/<movie|tv>/<id>/<cast|crew>
    ListModel { id: model }

    Component.onCompleted: {
        const bits = path.split("/");
        S.details(bits[1], parseInt(bits[2]), r => {
            const credits = r.credits || {};
            if (bits[3] === "cast") {
                for (const c of credits.cast || [])
                    model.append({pid: c.id, name: c.name, role: c.character || "", photo: c.profilePath || ""});
            } else {
                const byPerson = {}, order = [];
                for (const c of credits.crew || []) {
                    if (!byPerson[c.id]) { byPerson[c.id] = {pid: c.id, name: c.name, role: c.job, photo: c.profilePath || ""}; order.push(c.id); }
                    else if (byPerson[c.id].role.indexOf(c.job) < 0) byPerson[c.id].role += ", " + c.job;
                }
                for (const id of order) model.append(byPerson[id]);
            }
            heading.text = (r.title || r.name) + "  ·  " + page.title;
        });
    }

    Text {
        id: heading
        y: 124 * S.u
        text: page.title
        color: S.heading
        font.family: S.font
        font.pixelSize: 46 * S.u
        font.weight: Font.Bold
    }

    GridView {
        id: grid
        anchors { left: parent.left; right: parent.right; top: heading.bottom; bottom: parent.bottom; topMargin: 24 * S.u }
        cellWidth: S.cardW + S.rowGap
        cellHeight: S.cardH + 36 * S.u
        focus: true
        clip: true
        model: model
        cacheBuffer: 1500
        highlightMoveDuration: 150
        highlightRangeMode: GridView.ApplyRange
        preferredHighlightBegin: 40 * S.u
        preferredHighlightEnd: height - S.cardH - 40 * S.u
        topMargin: 22 * S.u
        leftMargin: 18 * S.u
        delegate: Item {
            required property int pid
            required property string name
            required property string role
            required property string photo
            width: grid.cellWidth
            height: grid.cellHeight
            focus: GridView.isCurrentItem
            PersonCard { focus: true; personId: pid; name: parent.name; role: parent.role; photo: parent.photo }
        }
    }
}
