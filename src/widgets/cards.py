"""Tiny UI helpers: content cards and labelled fields used across pages."""

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


def make_field(label_text: str, widget: QWidget) -> QWidget:
    """Wrap a control with a small caption label directly above it."""
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    label = QLabel(label_text)
    label.setObjectName("FieldLabel")
    layout.addWidget(label)
    layout.addWidget(widget)
    return row
