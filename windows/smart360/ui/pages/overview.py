"""Overview + Session pages."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from smart360.core.models import Prediction, Question
from smart360.health.monitor import COMPONENTS, Health
from smart360.ui.overlay import STATE_TITLES, answer_text
from smart360.ui.pages.base import Page, UiContext
from smart360.ui.theme import C, S, T, pen_color
from smart360.ui.widgets.controls import (
    Chip,
    ConfidenceMeter,
    Divider,
    EmptyState,
    GlassCard,
    GlowButton,
    HBar,
    StatTile,
    caption,
    clear_layout,
    confidence_color,
    hbox,
    label,
    set_label_color,
    vbox,
)
from smart360.ui.widgets.pulse import NeuralPulse, state_for_engine


def fmt_duration(s: float) -> str:
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


class HealthRow(QWidget):
    def __init__(self, name: str):
        super().__init__()
        self.name = label(name, T.body_medium())
        self.detail = label("", T.small(), C.TEXT_3)
        self.chip = Chip("UNKNOWN", C.TEXT_3, dot=True)
        self.setLayout(hbox(self.name, 8, self.detail, None, self.chip, margins=(0, 4, 0, 4)))

    def set(self, state: str, detail: str) -> None:
        self.chip.set(state, pen_color(state))
        self.detail.setText(detail[:60])


class OverviewPage(Page):
    title = "Overview"
    subtitle = "Your current session at a glance."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        self.conf_hist: deque[float] = deque(maxlen=40)
        self.lat_hist: deque[float] = deque(maxlen=40)

        # --- hero: live status
        hero = GlassCard(accent=C.PRIMARY, elevated=True)
        self.pulse = NeuralPulse(64, wave=True)
        self.state_lbl = caption("WATCHING", C.PRIMARY)
        self.status_lbl = label("Starting…", T.heading())
        self.answer_lbl = label("", T.telemetry(15), C.TEXT_2)
        self.btn_pause = GlowButton("Pause", "ghost", "pause")
        self.btn_pause.clicked.connect(lambda: self._engine("toggle_pause"))
        text = vbox(self.state_lbl, self.status_lbl, self.answer_lbl, spacing=4)
        hero.lay.addLayout(hbox(text, None, self.btn_pause, spacing=S.LG))
        hero.lay.addWidget(self.pulse)
        self.body.addWidget(hero)

        # --- KPIs
        self.tiles = {
            "analyzed": StatTile("Questions analyzed", "0", spark=True),
            "accepted": StatTile("Answers accepted", "0", spark=True, color=C.SUCCESS),
            "rechecks": StatTile("Rechecks", "0", spark=True),
            "uncertain": StatTile("Uncertain", "0", color=C.WARNING, spark=True),
            "avg_conf": StatTile("Avg confidence", "—", spark=True),
            "latency": StatTile("Avg AI latency", "—", spark=True, color=C.SECONDARY),
            "cache": StatTile("Cache hit rate", "—", spark=True),
            "time": StatTile("Session time", "00:00", spark=True),
        }
        g = self.grid()
        for i, t in enumerate(self.tiles.values()):
            g.addWidget(t, i // 4, i % 4)
        for col in range(4):
            g.setColumnStretch(col, 1)
        self.body.addLayout(g)

        # --- health
        hc = GlassCard()
        self.overall = Chip("HEALTHY", C.SUCCESS, dot=True)
        hc.lay.addLayout(
            hbox(
                vbox(
                    caption("System health"),
                    label("Live status of every subsystem.", T.small(), C.TEXT_2),
                    spacing=4,
                ),
                None,
                self.overall,
            )
        )
        self.body.addWidget(hc)
        self.rows = {}
        for n in ("Capture", "AI", "Vision", "Input", "Network"):
            row = HealthRow(n)
            self.rows[n] = row
            hc.lay.addWidget(row)
        self.body.addStretch(1)

        ctx.bridge.state.connect(self._on_state)
        ctx.bridge.status.connect(self.status_lbl.setText)
        ctx.bridge.prediction.connect(self._on_prediction)

    def _engine(self, action: str) -> None:
        eng = self.ctx.services.engine
        if eng:
            getattr(eng, action)()

    def _on_state(self, state: str, _reason: str) -> None:
        eng = self.ctx.services.engine
        p = eng.prediction if eng else None
        self.pulse.set_state(state_for_engine(state, bool(p and p.uncertain)))
        self.state_lbl.setText(STATE_TITLES.get(state, state))
        paused = state == "PAUSED"
        self.btn_pause.setText("Resume" if paused else "Pause")
        self.btn_pause.icon_name = "play" if paused else "pause"
        self.btn_pause.update()

    def _on_prediction(self, p: Prediction | None) -> None:
        if p is None:
            return
        self.answer_lbl.setText(f"Recommended {answer_text(p)}  ·  {p.confidence * 100:.0f} %  ·  {p.topic}")
        self.conf_hist.append(p.confidence * 100)
        if p.latency_ms:
            self.lat_hist.append(p.latency_ms / 1000)

    def refresh(self) -> None:
        eng = self.ctx.services.engine
        if eng is None:
            return
        s = eng.stats
        self.tiles["analyzed"].set(str(s.analyzed), f"{s.ai_calls} AI · {s.cache_hits} cache")
        self.tiles["accepted"].set(str(s.accepted), f"{s.rejected} rejected · {s.failed} failed")
        self.tiles["rechecks"].set(str(s.rechecks), "manual re-analysis")
        self.tiles["uncertain"].set(str(s.uncertain), "below threshold")
        self.tiles["avg_conf"].set(f"{s.avg_confidence * 100:.0f} %" if s.analyzed else "—")
        self.tiles["latency"].set(f"{s.avg_ai_ms / 1000:.1f} s" if s.ai_calls else "—")
        self.tiles["cache"].set(
            f"{s.cache_hit_rate * 100:.0f} %" if s.analyzed else "—",
            f"{len(self.ctx.services.cache)} cached questions",
        )
        import time

        self.tiles["time"].set(fmt_duration(time.time() - s.started_at))
        if self.tiles["avg_conf"].spark:
            self.tiles["avg_conf"].spark.set_values(self.conf_hist)
        if self.tiles["latency"].spark:
            self.tiles["latency"].spark.set_values(self.lat_hist)
        h = self.ctx.services.health
        for n, row in self.rows.items():
            c = h.components[n]
            row.set(c.state.value, c.detail)
        ov = h.overall()
        self.overall.set(ov.value, pen_color(ov.value))


class ConfidenceBreakdown(QWidget):
    NAMES = {
        "model": "Model",
        "ocr": "OCR",
        "layout": "Answer layout",
        "image_clarity": "Image clarity",
        "question_match": "Question match",
        "cache_similarity": "Cache similarity",
    }

    def __init__(self):
        super().__init__()
        self.lay = vbox(spacing=2)
        self.setLayout(self.lay)

    def set(self, items: tuple[tuple[str, float], ...]) -> None:
        clear_layout(self.lay)
        for k, v in items:
            self.lay.addWidget(HBar(self.NAMES.get(k, k), v, f"{v * 100:.0f} %", confidence_color(v)))


class SessionPage(Page):
    title = "Session"
    subtitle = "The live question, the recommendation and why."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        self.question: Question | None = None
        self.prediction: Prediction | None = None

        self.btn_pause = GlowButton("Pause", "ghost", "pause")
        self.btn_recheck = GlowButton("Recheck", "ghost", "refresh")
        self.btn_pause.clicked.connect(lambda: self._engine().toggle_pause() if self._engine() else None)
        self.btn_recheck.clicked.connect(lambda: self._engine().reanalyze() if self._engine() else None)
        self.header_row.addWidget(self.btn_pause)
        self.header_row.addWidget(self.btn_recheck)

        self.empty = EmptyState(
            "No question on screen",
            "Open a question in 360° online. It is detected automatically and analysed "
            "- nothing is ever clicked without your confirmation.",
            "session",
        )
        self.body.addWidget(self.empty)

        self.card = GlassCard(elevated=True)
        self.q_state = caption("QUESTION DETECTED", C.PRIMARY)
        self.q_topic = Chip("", C.SECONDARY)
        self.q_text = label("", T.title(), C.TEXT, wrap=True, selectable=True)
        self.card.lay.addLayout(hbox(self.q_state, None, self.q_topic))
        self.card.lay.addWidget(self.q_text)
        self.card.lay.addWidget(Divider())
        self.answers_box = vbox(spacing=S.SM)
        self.card.lay.addLayout(self.answers_box)
        self.body.addWidget(self.card)

        self.rec = GlassCard()
        self.rec_answer = label("—", T.hero(), C.TEXT)
        self.rec_conf = label("", T.telemetry(18), C.TEXT)
        self.rec_meter = ConfidenceMeter(28, 12)
        self.rec_reason = label("", T.body(), C.TEXT, wrap=True)
        self.rec_meta = label("", T.small(), C.TEXT_3)
        self.btn_confirm = GlowButton("Confirm", "primary", "check")
        self.btn_reject = GlowButton("Reject", "ghost", "close")
        self.btn_confirm.clicked.connect(self._confirm)
        self.btn_reject.clicked.connect(self._reject)
        left = vbox(caption("Recommended"), self.rec_answer, spacing=2)
        right = vbox(caption("Confidence"), self.rec_conf, spacing=2)
        self.rec.lay.addLayout(hbox(left, None, right))
        self.rec.lay.addWidget(self.rec_meter)
        self.rec.lay.addWidget(self.rec_reason)
        self.rec.lay.addLayout(hbox(self.rec_meta, None, self.btn_reject, self.btn_confirm))
        self.body.addWidget(self.rec)

        self.breakdown_card = self.section(
            "Confidence breakdown", "Composite score: the weakest signal caps the result."
        )
        self.breakdown = ConfidenceBreakdown()
        self.breakdown_card.lay.addWidget(self.breakdown)

        self.summary = self.section("Session summary")
        self.summary_lbl = label("", T.telemetry(13), C.TEXT_2, wrap=True)
        self.summary.lay.addWidget(self.summary_lbl)
        self.body.addStretch(1)

        ctx.bridge.question.connect(self._on_question)
        ctx.bridge.prediction.connect(self._on_prediction)
        ctx.bridge.state.connect(self._on_state)
        self._render()

    def _engine(self):  # type: ignore[no-untyped-def]
        return self.ctx.services.engine

    def _confirm(self) -> None:
        eng = self._engine()
        if eng and self.question:
            eng.approve(self.question.question_id)

    def _reject(self) -> None:
        eng = self._engine()
        if eng and self.question:
            eng.reject(self.question.question_id)

    def _on_question(self, q: Question | None) -> None:
        self.question = q
        if q is None or (self.prediction and self.prediction.question_id != q.question_id):
            self.prediction = None
        self._render()

    def _on_prediction(self, p: Prediction | None) -> None:
        self.prediction = p
        self._render()

    def _on_state(self, state: str, _r: str) -> None:
        self.q_state.setText(STATE_TITLES.get(state, state))
        waiting = state == "WAITING_FOR_CONFIRMATION"
        self.btn_confirm.setEnabled(waiting)
        self.btn_reject.setEnabled(waiting)
        self.btn_pause.setText("Resume" if state == "PAUSED" else "Pause")
        self.btn_pause.icon_name = "play" if state == "PAUSED" else "pause"
        self.btn_pause.update()

    def _render(self) -> None:
        q, p = self.question, self.prediction
        self.empty.setVisible(q is None)
        self.card.setVisible(q is not None)
        self.rec.setVisible(q is not None)
        self.breakdown_card.setVisible(p is not None and bool(p.confidence_breakdown))
        if q is None:
            return
        self.q_text.setText(q.text)
        self.q_topic.setVisible(bool(p and p.topic))
        if p:
            self.q_topic.set(p.topic, C.SECONDARY)
        clear_layout(self.answers_box)
        for a in q.answers:
            chosen = bool(p and a.index in p.answers)
            num = label(str(a.index), T.telemetry(15), C.PRIMARY if chosen else C.TEXT_3)
            num.setFixedWidth(22)
            txt = label(
                a.text, T.body_medium() if chosen else T.body(), C.TEXT if chosen else C.TEXT_2, wrap=True
            )
            row = hbox(num, txt, spacing=S.MD)
            row.setStretch(1, 1)
            if chosen:
                row.addWidget(Chip("RECOMMENDED", C.SUCCESS))
            self.answers_box.addLayout(row)
        if not q.answers:
            self.answers_box.addLayout(hbox(label("Number input question", T.body(), C.TEXT_2)))
        if p:
            self.rec_answer.setText(answer_text(p))
            set_label_color(self.rec_answer, confidence_color(p.confidence))
            self.rec_conf.setText(f"{p.confidence * 100:.0f} %")
            self.rec_meter.set_value(p.confidence)
            self.rec_reason.setText(p.reason)
            src = {"ai": "AI", "cache": "Cache", "mock": "Demo"}.get(p.source.value, p.source.value)
            lat = f" · {p.latency_ms / 1000:.1f} s" if p.latency_ms else ""
            self.rec_meta.setText(f"{src} · {p.model}{lat}")
            self.btn_confirm.kind = "warning" if p.uncertain else "primary"
            self.btn_confirm.setText("Confirm anyway" if p.uncertain else "Confirm")
            self.breakdown.set(p.confidence_breakdown)
        else:
            self.rec_answer.setText("…")
            set_label_color(self.rec_answer, C.TEXT_3)
            self.rec_conf.setText("")
            self.rec_meter.set_value(0)
            self.rec_reason.setText("Analyzing…")
            self.rec_meta.setText("")

    def refresh(self) -> None:
        eng = self._engine()
        if eng is None:
            return
        s = eng.stats
        costs = self.ctx.services.solver.costs.snapshot() if self.ctx.services.solver else {}
        saved = ""
        if costs.get("requests") and s.cache_hits:
            per = costs["estimated_usd"] / max(1, costs["requests"])
            saved = f"   ·   Cache savings ≈ ${per * s.cache_hits:.3f}"
        self.summary_lbl.setText(
            f"Questions {s.analyzed}   ·   Avg confidence {s.avg_confidence * 100:.0f} %   ·   "
            f"Uncertain {s.uncertain}   ·   Rejected {s.rejected}   ·   AI time {s.ai_time_ms / 1000:.1f} s"
            f"   ·   Cache hits {s.cache_hits}{saved}"
        )


__all__ = ["COMPONENTS", "Health", "OverviewPage", "Qt", "SessionPage"]
