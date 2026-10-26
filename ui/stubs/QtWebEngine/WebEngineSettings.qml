// Stand-in for Qt WebEngine's page settings (off-screen screenshots, qmllint in CI).
import QtQml

QtObject {
    property bool spatialNavigationEnabled: false
    property bool focusOnNavigationEnabled: false
    property bool playbackRequiresUserGesture: true
    property bool showScrollBars: true
    property bool javascriptCanOpenWindows: true
}
