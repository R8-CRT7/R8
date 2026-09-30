"""Page scaffolding + shared UI context."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QScrollArea, QVBoxLayout, QWidget

from smart360.services import Services
from smart360.ui.bridge import EngineBridge
from smart360.ui.theme import C, S, T
from smart360.ui.widgets.controls import GlassCard, caption, hbox, label


def _noop() -> None:
    return None


def _noop_toast(text: str, kind: str = "info") -> None:
    return None


@dataclass
class UiContext:
    services: Services
    bridge: EngineBridge
    # callbacks wired by the app controller
    open_calibration: Callable[[], None] = _noop
    apply_appearance: Callable[[], None] = _noop
    apply_engine_config: Callable[[], None] = _noop
    toast: Callable[..., None] = _noop_toast
    extra: dict = field(default_factory=dict)


class Page(QScrollArea):
    title = "Page"
    subtitle = ""

    def __init__(self, ctx: UiContext):
        super().__init__()
        self.ctx = ctx
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.body = QVBoxLayout(inner)
        self.body.setContentsMargins(S.XXL, S.XL, S.XXL, S.XXL)
        self.body.setSpacing(S.LG)
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(label(self.title, T.display(), C.TEXT))
        if self.subtitle:
            head.addWidget(label(self.subtitle, T.body(), C.TEXT_2))
        self.header_row = hbox(head, None)
        self.body.addLayout(self.header_row)
        self.body.addSpacing(S.SM)
        self.setWidget(inner)
        self.viewport().setAutoFillBackground(False)
        inner.setAutoFillBackground(False)

    def refresh(self) -> None:
        """Called when the page becomes visible and on the dashboard tick."""

    def section(self, title: str, subtitle: str = "", accent=None) -> GlassCard:  # type: ignore[no-untyped-def]
        card = GlassCard(accent=accent)
        if title:
            card.lay.addWidget(caption(title))
        if subtitle:
            card.lay.addWidget(label(subtitle, T.small(), C.TEXT_2, wrap=True))
        self.body.addWidget(card)
        return card

    @staticmethod
    def grid(spacing: int = S.LG) -> QGridLayout:
        g = QGridLayout()
        g.setSpacing(spacing)
        g.setContentsMargins(0, 0, 0, 0)
        return g
