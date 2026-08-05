"""Drop zone: video-only drag & drop (UI acceptance, no processing).

Note: we use a lightweight *stub* event instead of a real ``QDropEvent``.
Since Qt 6.8 a Python-constructed ``QDropEvent`` takes ownership of its
``QMimeData`` and deletes it on destruction, which causes use-after-free
access violations on Windows. The widget only calls ``mimeData()`` /
``acceptProposedAction()`` / ``ignore()`` on the event, so a stub exercises
the exact same code paths safely on every platform.
"""

from pathlib import Path

from PySide6.QtCore import QEvent, QMimeData, QPointF, QUrl, Qt
from PySide6.QtGui import QMouseEvent

from src.widgets.drop_zone import DropZone, is_supported_video


class _FakeDropEvent:
    """Minimal drop-event stand-in exposing the methods DropZone uses."""

    def __init__(self, mime: QMimeData) -> None:
        self._mime = mime
        self.accepted = False

    def mimeData(self) -> QMimeData:
        return self._mime

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.accepted = False


def _mime_with_file(path: str) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(path)])
    return mime


def test_is_supported_video():
    assert is_supported_video("clip.MP4")  # case-insensitive
    assert is_supported_video(Path("clip.webm"))
    assert is_supported_video("C:/videos/movie.mkv")
    assert not is_supported_video("notes.txt")
    assert not is_supported_video("photo.png")


def test_drop_zone_accepts_video_file(qapp):
    zone = DropZone()
    received = []
    # files_dropped emits a *list* of paths; extend flattens it.
    zone.files_dropped.connect(received.extend)

    event = _FakeDropEvent(_mime_with_file("C:/videos/clip.mp4"))
    zone.dragEnterEvent(event)
    assert event.accepted

    zone.dropEvent(event)
    assert received == ["C:/videos/clip.mp4"]


def test_drop_zone_rejects_non_video(qapp):
    zone = DropZone()
    event = _FakeDropEvent(_mime_with_file("C:/docs/notes.txt"))
    zone.dragEnterEvent(event)
    assert not event.accepted


def test_drop_zone_ignores_non_file_urls(qapp):
    zone = DropZone()
    mime = QMimeData()
    mime.setUrls([QUrl("https://example.com/video.mp4")])
    event = _FakeDropEvent(mime)
    zone.dragEnterEvent(event)
    assert not event.accepted


def test_drop_zone_click_emits_browse(qapp):
    zone = DropZone()
    clicked = []
    zone.browse_clicked.connect(lambda: clicked.append(True))

    press = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    zone.mousePressEvent(press)
    assert clicked


def test_home_drop_queues_jobs_without_processing(qapp, config, app_state, theme_service):
    from src.views.home import HomeView

    home = HomeView(app_state, theme_service, config)
    home.drop_zone.files_dropped.emit(["C:/videos/a.mp4", "C:/videos/b.mkv"])

    assert len(app_state.jobs()) == 2
    assert app_state.jobs()[0].filename == "a.mp4"
    assert app_state.jobs()[0].status.value == "waiting"  # queued, not processed
    assert app_state.recent_files() == ["C:/videos/b.mkv", "C:/videos/a.mp4"]
