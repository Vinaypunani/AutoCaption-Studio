"""Tiny UI helper: consistent content cards used across pages."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


def make_card(title: str | None, content: QWidget, object_name: str = "Card") -> QFrame:
    """Wrap ``content`` in a styled card with an optional title."""
    card = QFrame()
    card.setObjectName(object_name)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 14, 18, 16)
    layout.setSpacing(10)
    if title:
        label = QLabel(title)
        label.setObjectName("CardTitle")
        layout.addWidget(label)
    layout.addWidget(content)
    return card
