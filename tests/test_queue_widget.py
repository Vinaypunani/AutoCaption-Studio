"""QueueWidget / JobRow: stage display, selection, removal."""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from src.models.job_model import Job, ProcessStage
from src.widgets.queue_widget import JobRow, QueueWidget


def _click(widget):
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(20, 20),
        QPointF(20, 20),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)


def test_row_shows_stage(qapp):
    job = Job(filename="clip.mp4", path="C:/clip.mp4", stage=ProcessStage.VALIDATING)
    row = JobRow(job)
    assert row.chip.text() == "Validating"


def test_row_shows_ready_stage(qapp):
    job = Job(filename="clip.mp4", path="C:/clip.mp4", stage=ProcessStage.READY)
    row = JobRow(job)
    assert row.chip.text() == "Ready"


def test_row_selection_emits_and_styles(qapp):
    job_a = Job(filename="a.mp4", path="C:/a.mp4")
    job_b = Job(filename="b.mp4", path="C:/b.mp4")
    queue = QueueWidget(show_header=False)

    selected: list[str] = []
    queue.job_selected.connect(selected.append)
    queue.set_jobs([job_a, job_b])

    row = queue._rows[job_a.job_id]
    _click(row)

    assert selected == [job_a.job_id]
    assert row.is_selected()
    assert not queue._rows[job_b.job_id].is_selected()


def test_removed_rows_disappear(qapp):
    job = Job(filename="a.mp4", path="C:/a.mp4")
    queue = QueueWidget(show_header=False)
    queue.set_jobs([job])
    assert queue.job_count() == 1

    queue.set_jobs([])
    assert queue.job_count() == 0
