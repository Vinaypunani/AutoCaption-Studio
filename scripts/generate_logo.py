"""Generate the application logo (assets/logo.png + assets/images/logo.png).

Run once from the project root:  python scripts/generate_logo.py
Requires PySide6 (the project's only dependency).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
SIZE = 512


def render_logo() -> QPixmap:
    pixmap = QPixmap(SIZE, SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Rounded tile with an indigo→violet gradient
    gradient = QLinearGradient(0, 0, SIZE, SIZE)
    gradient.setColorAt(0.0, QColor("#6c8cff"))
    gradient.setColorAt(1.0, QColor("#8b5cf6"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(QRectF(20, 20, SIZE - 40, SIZE - 40), 110, 110)

    # Subtle top highlight
    painter.setBrush(QColor(255, 255, 255, 26))
    painter.drawRoundedRect(QRectF(20, 20, SIZE - 40, SIZE - 40), 110, 110)

    # Play triangle (caption it — literally the product)
    triangle = QPainterPath()
    triangle.moveTo(196, 168)
    triangle.lineTo(196, 344)
    triangle.lineTo(356, 256)
    triangle.closeSubpath()
    painter.setBrush(QColor("#ffffff"))
    painter.drawPath(triangle)

    # Subtitle caption bars
    painter.setBrush(QColor("#ffffff"))
    painter.drawRoundedRect(QRectF(138, 384, 236, 26), 13, 13)
    painter.setBrush(QColor(255, 255, 255, 150))
    painter.drawRoundedRect(QRectF(160, 424, 164, 18), 9, 9)

    painter.end()
    return pixmap


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841  (needed for QPixmap on some platforms)
    pixmap = render_logo()

    assets = ROOT / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "images").mkdir(parents=True, exist_ok=True)

    pixmap.save(str(assets / "logo.png"))
    pixmap.save(str(assets / "images" / "logo.png"))
    print(f"Logo written to {assets / 'logo.png'} and {assets / 'images' / 'logo.png'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
