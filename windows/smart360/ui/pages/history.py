"""History + Insights pages."""

from __future__ import annotations

import time

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QLineEdit, QListView, QStyle, QStyledItemDelegate, QWidget

from smart360.ai.schema import TOPICS
from smart360.core.models import Decision, HistoryEntry
from smart360.storage.history import HistoryFilter
from smart360.ui.icons import draw_icon
from smart360.ui.pages.base import Page, UiContext
from smart360.ui.theme import ALIGN_LEFT, ALIGN_RIGHT, C, S, T, with_alpha
from smart360.ui.widgets.controls import (
    Chip,
    EmptyState,
    GlassCard,
    HBar,
    caption,
    clear_layout,
    confidence_color,
    hbox,
    label,
    vbox,
)

DECISION_COLORS = {
    Decision.ACCEPTED: C.SUCCESS,
    Decision.REJECTED: C.ERROR,
    Decision.SKIPPED: C.TEXT_3,
    Decision.FAILED: C.WARNING,
}


class HistoryModel(QAbstractListModel):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[HistoryEntry] = []

    def set_rows(self, rows: list[HistoryEntry]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # type: ignore[no-untyped-def]  # noqa: B008
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):  # type: ignore[no-untyped-def]
        if role == Qt.ItemDataRole.UserRole and index.isValid():
            return self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole and index.isValid():
            return self.rows[index.row()].question_text
        return None


class HistoryDelegate(QStyledItemDelegate):
    H = 76

    def sizeHint(self, option, index) -> QSize:  # type: ignore[no-untyped-def]
        return QSize(option.rect.width(), self.H)

    def paint(self, p: QPainter, option, index) -> None:  # type: ignore[no-untyped-def]
        e: HistoryEntry = index.data(Qt.ItemDataRole.UserRole)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect).adjusted(0, 3, 0, -3)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        p.setPen(QPen(QColor(255, 255, 255, 22 if not hover else 40), 1))
        p.setBrush(QColor(255, 255, 255, 8 if not hover else 16))
        p.drawRoundedRect(r, 12, 12)
        x = r.left() + 16
        # time + topic
        p.setFont(T.telemetry(11.5))
        p.setPen(C.TEXT_3)
        p.drawText(
            QRectF(x, r.top() + 12, 120, 16),
            ALIGN_LEFT,
            time.strftime("%d.%m. %H:%M", time.localtime(e.timestamp)),
        )
        p.setFont(T.caption())
        p.setPen(C.SECONDARY)
        fm_c = QFontMetrics(p.font())
        p.drawText(
            QRectF(x, r.top() + 44, 128, 16),
            ALIGN_LEFT,
            fm_c.elidedText(e.topic or "—", Qt.TextElideMode.ElideRight, 128),
        )
        # question
        right_w = 300
        qx = x + 146
        qw = r.width() - (qx - r.left()) - right_w
        p.setFont(T.body_medium())
        p.setPen(C.TEXT)
        fm = QFontMetrics(p.font())
        text = e.question_text or "(question text not stored - privacy mode)"
        p.drawText(
            QRectF(qx, r.top() + 10, qw, 20),
            ALIGN_LEFT,
            fm.elidedText(text, Qt.TextElideMode.ElideRight, int(qw)),
        )
        p.setFont(T.small())
        p.setPen(C.TEXT_2)
        rec = " + ".join(str(a) for a in e.recommended) or "—"
        src = {"ai": "AI", "cache": "Cache", "mock": "Demo"}.get(e.source, e.source)
        detail = f"Recommended {rec}   ·   {src}   ·   {e.processing_ms / 1000:.1f} s"
        if e.uncertain:
            detail += "   ·   uncertain"
        p.drawText(QRectF(qx, r.top() + 40, qw, 18), ALIGN_LEFT, detail)
        # confidence
        cx = r.right() - right_w + 20
        col = confidence_color(e.confidence)
        p.setFont(T.telemetry(16))
        p.setPen(col)
        p.drawText(QRectF(cx, r.top() + 12, 70, 22), ALIGN_LEFT, f"{e.confidence * 100:.0f}%")
        track = QRectF(cx, r.top() + 44, 110, 5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18))
        p.drawRoundedRect(track, 2.5, 2.5)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(cx, r.top() + 44, 110 * e.confidence, 5), 2.5, 2.5)
        # decision chip
        dc = DECISION_COLORS.get(e.decision, C.TEXT_2)
        chip = QRectF(r.right() - 116, r.top() + (r.height() - 24) / 2, 100, 24)
        p.setPen(QPen(with_alpha(dc, 90), 1))
        p.setBrush(with_alpha(dc, 30))
        p.drawRoundedRect(chip, 12, 12)
        p.setFont(T.caption())
        p.setPen(dc)
        p.drawText(chip, Qt.AlignmentFlag.AlignCenter, e.decision.value.upper())
        p.restore()


class HistoryPage(Page):
    title = "History"
    subtitle = "Every analysed question - stored locally, never uploaded."

    FILTERS = (
        ("all", "All"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("uncertain", "Uncertain"),
        ("low", "Low confidence"),
    )

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search questions and answers…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(320)
        self._debounce = QTimer(self, singleShot=True, interval=220)
        self._debounce.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _t: self._debounce.start())
        self.topic = QComboBox()
        self.topic.addItem("All topics", "")
        for t in TOPICS:
            self.topic.addItem(t, t)
        self.topic.currentIndexChanged.connect(lambda _i: self.refresh())
        self.chips: dict[str, Chip] = {}
        chip_row = hbox(spacing=6)
        for key, text in self.FILTERS:
            c = Chip(text, C.PRIMARY, checkable=True)
            c.setChecked(key == "all")
            c.clicked.connect(lambda _c=False, k=key: self._set_filter(k))
            self.chips[key] = c
            chip_row.addWidget(c)
        chip_row.addStretch(1)
        self.count_lbl = label("", T.small(), C.TEXT_3)
        chip_row.addWidget(self.count_lbl)
        self.body.addLayout(hbox(self.search, self.topic, None))
        self.body.addLayout(chip_row)
        self.filter_key = "all"

        self.model = HistoryModel()
        self.view = QListView()
        self.view.setModel(self.model)
        self.view.setItemDelegate(HistoryDelegate(self.view))
        self.view.setMouseTracking(True)
        self.view.setUniformItemSizes(True)
        self.view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.view.setMinimumHeight(420)
        self.view.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.body.addWidget(self.view, 1)
        self.empty = EmptyState(
            "Your analyzed questions will appear here.",
            "Start 360° online and answer a few questions - each one lands here with the "
            "recommendation, confidence and your decision.",
            "history",
        )
        self.body.addWidget(self.empty)

    def _set_filter(self, key: str) -> None:
        self.filter_key = key
        for k, c in self.chips.items():
            c.setChecked(k == key)
        self.refresh()

    def refresh(self) -> None:
        k = self.filter_key
        f = HistoryFilter(
            search=self.search.text().strip(),
            topic=self.topic.currentData() or "",
            decision=k if k in ("accepted", "rejected") else "",
            uncertain_only=k == "uncertain",
            max_confidence=0.75 if k == "low" else 1.0,
        )
        rows = self.ctx.services.history.query(f)
        self.model.set_rows(rows)
        total = self.ctx.services.history.count()
        self.count_lbl.setText(f"{len(rows)} of {total}")
        filtered_empty = total > 0 and not rows
        self.view.setVisible(bool(rows))
        self.empty.setVisible(not rows)
        if filtered_empty:
            self.empty.findChildren(QWidget)  # keep widget alive
        self.view.setFixedHeight(min(640, max(120, len(rows) * HistoryDelegate.H + 8)))


class InsightsPage(Page):
    title = "Insights"
    subtitle = "Where you are strong, where to practise. Computed locally from your history."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        self.empty = EmptyState(
            "Insights need a little history",
            "After a few analysed questions you will see difficult topics, often rejected "
            "recommendations and OCR problems here.",
            "insights",
        )
        self.body.addWidget(self.empty)
        self.topics_card = self.section("Topics", "Question volume per topic.")
        self.topics_box = vbox(spacing=4)
        self.topics_card.lay.addLayout(self.topics_box)
        g = self.grid()
        self.hard = GlassCard()
        self.hard.lay.addWidget(caption("Difficult topics"))
        self.hard_box = vbox(spacing=4)
        self.hard.lay.addLayout(self.hard_box)
        self.slow = GlassCard()
        self.slow.lay.addWidget(caption("Slowest question types"))
        self.slow_box = vbox(spacing=4)
        self.slow.lay.addLayout(self.slow_box)
        g.addWidget(self.hard, 0, 0)
        g.addWidget(self.slow, 0, 1)
        self.body.addLayout(g)
        self.problems = self.section(
            "My problem questions",
            "Rejected, uncertain or low-confidence - worth reviewing in the learning software.",
        )
        self.problems_box = vbox(spacing=6)
        self.problems.lay.addLayout(self.problems_box)
        self.ocr = self.section(
            "OCR issues", "Questions read with low OCR confidence (consider recalibrating)."
        )
        self.ocr_box = vbox(spacing=6)
        self.ocr.lay.addLayout(self.ocr_box)
        self.body.addStretch(1)

    @staticmethod
    def _clear(box) -> None:  # type: ignore[no-untyped-def]
        clear_layout(box)

    def refresh(self) -> None:
        h = self.ctx.services.history
        topics = h.topics()
        has = bool(topics)
        self.empty.setVisible(not has)
        for w in (self.topics_card, self.hard, self.slow, self.problems, self.ocr):
            w.setVisible(has)
        if not has:
            return
        for b in (self.topics_box, self.hard_box, self.slow_box, self.problems_box, self.ocr_box):
            self._clear(b)
        mx = max(t.count for t in topics)
        for t in topics:
            self.topics_box.addWidget(
                HBar(t.topic, t.count / mx, f"{t.count}  ·  Ø {t.avg_confidence * 100:.0f} %")
            )
        for t in sorted(topics, key=lambda t: t.difficulty, reverse=True)[:5]:
            col = C.ERROR if t.difficulty > 0.5 else (C.WARNING if t.difficulty > 0.25 else C.SUCCESS)
            self.hard_box.addWidget(
                HBar(t.topic, t.difficulty, f"{t.rejected} rejected · {t.uncertain} unsure", col)
            )
        slow_max = max(t.avg_ms for t in topics) or 1
        for t in sorted(topics, key=lambda t: t.avg_ms, reverse=True)[:5]:
            self.slow_box.addWidget(
                HBar(t.topic, t.avg_ms / slow_max, f"{t.avg_ms / 1000:.1f} s", C.SECONDARY)
            )
        probs = h.problem_questions(8)
        for e in probs:
            self.problems_box.addWidget(_problem_row(e))
        if not probs:
            self.problems_box.addWidget(label("No problem questions - nice.", T.body(), C.TEXT_2))
        lows = h.low_ocr(5)
        for e in lows:
            self.ocr_box.addWidget(_problem_row(e, ocr=True))
        if not lows:
            self.ocr_box.addWidget(label("No OCR problems detected.", T.body(), C.TEXT_2))


def _problem_row(e: HistoryEntry, ocr: bool = False) -> QWidget:
    w = QWidget()
    dc = DECISION_COLORS.get(e.decision, C.TEXT_2)
    t = label((e.question_text or "(text not stored)")[:140], T.body(), C.TEXT, wrap=True)
    right = label(
        f"OCR {e.ocr_confidence * 100:.0f} %" if ocr else f"{e.confidence * 100:.0f} %",
        T.telemetry(13),
        confidence_color(e.ocr_confidence if ocr else e.confidence),
    )
    chip = Chip(e.topic or "—", C.SECONDARY)
    dec = Chip(e.decision.value.upper(), dc)
    w.setLayout(hbox(chip, t, None, dec, right, spacing=S.MD, margins=(0, 2, 0, 2)))
    return w


__all__ = ["ALIGN_RIGHT", "HistoryPage", "InsightsPage", "QPointF", "draw_icon"]
