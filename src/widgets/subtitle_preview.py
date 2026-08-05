"""Live subtitle preview panel.

Left: a scrollable list of cues (timestamp + first line). Right: the exact
styling the captions will have — dark band, centred white text — rendered by
the pure-HTML :func:`subtitle_preview_generator`. Selecting a cue highlights
it in the render.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..subtitles.formatter import format_srt_time
from ..subtitles.model import SubtitleCue
from ..subtitles.preview_generator import render_preview_html


class SubtitlePreview(QWidget):
    """Cue list + styled caption preview."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cues: list[SubtitleCue] = []
        self.setObjectName("SubtitlePreview")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.cue_list = QListWidget()
        self.cue_list.setObjectName("SubtitleCueList")
        self.cue_list.setMinimumWidth(220)
        self.cue_list.currentRowChanged.connect(self._on_select)
        layout.addWidget(self.cue_list, 1)

        self.preview_browser = QTextBrowser()
        self.preview_browser.setObjectName("SubtitlePreviewBrowser")
        self.preview_browser.setOpenExternalLinks(False)
        layout.addWidget(self.preview_browser, 2)

    # -- API -----------------------------------------------------------------
    def set_cues(self, cues: list[SubtitleCue]) -> None:
        """Show a cue list; select the first cue."""
        self._cues = list(cues)
        self.cue_list.clear()
        for cue in self._cues:
            first_line = cue.text.split("\n", 1)[0] if cue.text else ""
            item = QListWidgetItem(
                f"{format_srt_time(cue.start)}  {first_line[:34]}"
            )
            item.setData(Qt.ItemDataRole.UserRole, cue.index)
            item.setToolTip(cue.text)
            self.cue_list.addItem(item)
        if self._cues:
            self.cue_list.setCurrentRow(0)
        else:
            self.preview_browser.setHtml(
                render_preview_html([])
            )

    def clear(self) -> None:
        self._cues = []
        self.cue_list.clear()
        self.preview_browser.setHtml(render_preview_html([]))

    def cue_count(self) -> int:
        return len(self._cues)

    # -- internals -------------------------------------------------------------
    def _on_select(self, row: int) -> None:
        if not (0 <= row < len(self._cues)):
            return
        selected_index = self._cues[row].index
        self.preview_browser.setHtml(
            render_preview_html(self._cues, selected_index=selected_index)
        )
