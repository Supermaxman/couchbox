"""YouTube on a new box: yt-dlp comes with the apps once the box is online, after the YouTube app
may have started. Until then the app is told "not ready" (it waits with a spinner and asks
again), and once yt-dlp is there it's used, without restarting the app."""

import zipfile

import pytest

from couchbox.services import ytstream


@pytest.fixture
def no_ytdlp(tmp_path, monkeypatch):
    z = tmp_path / "yt-dlp"
    monkeypatch.setattr(ytstream, "YTDLP_ZIP", str(z))
    monkeypatch.delenv("COUCHBOX_YTDLP", raising=False)
    monkeypatch.setattr(ytstream, "_module", None)
    monkeypatch.setattr(ytstream, "_ydl", None)
    import sys

    real = sys.modules.pop("yt_dlp", None)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if "yt_dlp" not in p and "yt-dlp" not in p])
    monkeypatch.setattr(sys, "meta_path", [f for f in sys.meta_path])
    yield z
    sys.modules.pop("yt_dlp", None)
    if real is not None:
        sys.modules["yt_dlp"] = real


def test_missing_yt_dlp_is_not_ready_then_found(no_ytdlp, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def only_from_the_zip(name, *a, **kw):  # the test machine may have yt-dlp installed: ignore it
        if name == "yt_dlp":
            import sys

            if not any(p == str(no_ytdlp) for p in sys.path):
                raise ImportError(name)
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", only_from_the_zip)
    assert ytstream.module() is None
    with pytest.raises(ytstream.NotReady):
        ytstream._downloader()
    assert ytstream.module() is None  # still not there: no error, still not ready
    with zipfile.ZipFile(no_ytdlp, "w") as z:  # it arrives (a stand-in release)
        z.writestr("yt_dlp/__init__.py", "MARK = 'arrived'\n")
    m = ytstream.module()
    assert m is not None and m.MARK == "arrived"
