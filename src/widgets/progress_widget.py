"""Animated progress bar.

Custom-painted (not QProgressBar) so the highlight animation and the
theme accent colors stay fully under our control. Supports a determinate
mode (0-100) and an indeterminate "bouncing" mode.
"""

from __future__ import annotations

from PySide6.QtCore import Property, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ..services.theme_service import accent_color, track_color


class ProgressWidget(QWidget):
    """Slim animated progress indicator."""

    def __init__(self, indeterminate: bool = False, height: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._indeterminate = indeterminate
        self._offset = 0.0
        self.setFixedHeight(height)

        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(1500)
        self._anim.setLoopCount(-1)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self.update)

    # -- animated offset property (for QPropertyAnimation) -----------------
    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value

    offset = Property(float, _get_offset, _set_offset)  # noqa: N815 (Qt naming)

    # -- public API --------------------------------------------------------
    def set_value(self, value: float) -> None:
        clamped = max(0.0, min(100.0, float(value)))
        if abs(clamped - self._value) > 0.01:
            self._value = clamped
            self.update()

    def value(self) -> float:
        return self._value

    def set_indeterminate(self, flag: bool) -> None:
        if flag != self._indeterminate:
            self._indeterminate = flag
            self.update()

    def start_animation(self) -> None:
        if self._anim.state() != QPropertyAnimation.State.Running:
            self._anim.start()

    def stop_animation(self) -> None:
        self._anim.stop()

    # -- rendering ---------------------------------------------------------
    def showEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.start_animation()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        self.stop_animation()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        radius = height / 2.0
        track = QColor(track_color())
        fill = QColor(accent_color())

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(track)
        painter.drawRoundedRect(0, 0, width, height, radius, radius)

        if self._indeterminate:
            span = max(40.0, width * 0.3)
            x = -span + (width + span) * self._offset
            painter.setBrush(fill)
            painter.drawRoundedRect(int(x), 0, int(span), height, radius, radius)
            painter.end()
            return

        if self._value > 0:
            fill_width = max(radius * 2, width * self._value / 100.0)
            painter.setBrush(fill)
            painter.drawRoundedRect(0, 0, int(fill_width), height, radius, radius)

            # soft moving shine on top of the filled portion
            shine_width = width * 0.18
            shine_x = -shine_width + (width + shine_width) * self._offset
            if shine_x < fill_width:
                shine = QColor(255, 255, 255, 45)
                painter.setBrush(shine)
                painter.drawRoundedRect(int(max(0, shine_x)), 0, int(shine_width), height, radius, radius)

        painter.end()
