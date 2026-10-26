// Stand-in for Qt WebEngine's profile (off-screen screenshots, qmllint in CI).
import QtQml

QtObject {
    property string storageName: ""
    property bool offTheRecord: true
    property int httpCacheMaximumSize: 0
    property string httpUserAgent: "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
}
