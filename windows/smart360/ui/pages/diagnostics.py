"""Diagnostics: health, latencies, system, log viewer, self-test and export."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QPlainTextEdit, QWidget

from smart360.health.diagnostics import CheckResult, export_report, run_self_test
from smart360.health.monitor import COMPONENTS
from smart360.ui.pages.base import Page, UiContext
from smart360.ui.theme import C, S, T, pen_color
from smart360.ui.widgets.controls import Chip, GlassCard, GlowButton, caption, clear_layout, hbox, label, vbox

METRICS = (
    ("ai_ms", "AI latency"),
    ("ocr_ms", "OCR latency"),
    ("capture_ms", "Capture latency"),
    ("extract_ms", "Question extraction"),
    ("exec_ms", "Confirmed action"),
    ("ui_lag_ms", "UI event lag"),
)


class DiagnosticsPage(Page):
    title = "Diagnostics"
    subtitle = "Health, performance and an anonymized report for troubleshooting."

    def __init__(self, ctx: UiContext):
        super().__init__(ctx)
        self.last_results: list[CheckResult] = []
        run = GlowButton("Run self-test", "ghost", "refresh")
        export = GlowButton("Export report", "ghost", "download")
        self.btn_diagnosis = GlowButton("Create diagnosis (ZIP)", "primary", "download")
        self.btn_diagnosis.setToolTip(
            "One ZIP on your desktop with logs, traces and system info - no API keys, no passwords."
        )
        run.clicked.connect(self._run)
        export.clicked.connect(self._export)
        self.btn_diagnosis.clicked.connect(self._diagnosis)
        self.header_row.addWidget(run)
        self.header_row.addWidget(export)
        self.header_row.addWidget(self.btn_diagnosis)

        g = self.grid(S.MD)
        self.chips: dict[str, tuple[Chip, object]] = {}
        for i, n in enumerate(COMPONENTS):
            card = GlassCard(padding=S.LG)
            chip = Chip("UNKNOWN", C.TEXT_3, dot=True)
            detail = label("", T.small(), C.TEXT_3)
            card.lay.addLayout(hbox(label(n, T.title()), None, chip))
            card.lay.addWidget(detail)
            self.chips[n] = (chip, detail)
            g.addWidget(card, i // 4, i % 4)
        self.body.addLayout(g)

        two = self.grid()
        perf = GlassCard()
        perf.lay.addWidget(caption("Latency (avg / p95)"))
        self.metric_lbls = {}
        for key, text in METRICS:
            v = label("—", T.telemetry(13), C.TEXT)
            self.metric_lbls[key] = v
            perf.lay.addLayout(hbox(label(text, T.body(), C.TEXT_2), None, v))
        sysc = GlassCard()
        sysc.lay.addWidget(caption("Process"))
        self.sys_lbls = {}
        for key, text in (
            ("cpu_percent", "CPU"),
            ("rss_mb", "Memory"),
            ("rss_growth_mb_per_h", "Memory trend"),
            ("threads", "Threads"),
            ("cache_entries", "Cache entries"),
        ):
            v = label("—", T.telemetry(13), C.TEXT)
            self.sys_lbls[key] = v
            sysc.lay.addLayout(hbox(label(text, T.body(), C.TEXT_2), None, v))
        two.addWidget(perf, 0, 0)
        two.addWidget(sysc, 0, 1)
        self.body.addLayout(two)

        st = self.section("Self-test")
        self.results_box = vbox(spacing=4)
        st.lay.addLayout(self.results_box)
        self.results_box.addWidget(
            label(
                "Run the self-test to check storage, config, AI, capture, OCR, cache, "
                "state machine and hotkeys.",
                T.small(),
                C.TEXT_3,
                wrap=True,
            )
        )

        logs = self.section("Recent errors")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(T.telemetry(11.5))
        self.log.setMinimumHeight(180)
        self.log.setPlaceholderText("No errors recorded. Nice.")
        logs.lay.addWidget(self.log)
        self.body.addStretch(1)

    def _run(self) -> None:
        self.last_results = run_self_test(self.ctx.services)
        clear_layout(self.results_box)
        for r in self.last_results:
            w = QWidget()
            w.setLayout(
                hbox(
                    Chip(r.status.upper(), pen_color(r.status), dot=True),
                    label(r.name, T.body_medium()),
                    label(r.detail, T.small(), C.TEXT_2),
                    None,
                    label(f"{r.ms:.0f} ms", T.telemetry(12), C.TEXT_3),
                )
            )
            self.results_box.addWidget(w)

    def _diagnosis(self) -> None:
        fn = self.ctx.extra.get("create_diagnosis")
        if fn is not None:
            fn()

    def _export(self) -> None:
        default = str(Path.home() / f"360smart-diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.json")
        path, _ = QFileDialog.getSaveFileName(self, "Export diagnostic report", default, "JSON (*.json)")
        if not path:
            return
        results = self.last_results or run_self_test(self.ctx.services)
        export_report(self.ctx.services, Path(path), results)
        self.ctx.toast("Report exported (no keys, no question texts, no screenshots)", "success")

    def refresh(self) -> None:
        h = self.ctx.services.health
        for n, (chip, detail) in self.chips.items():
            c = h.components[n]
            chip.set(c.state.value, pen_color(c.state.value))
            detail.setText(c.detail[:48] or "—")  # type: ignore[attr-defined]
        for key, lbl in self.metric_lbls.items():
            m = h.metrics[key]
            lbl.setText(f"{m.avg:.0f} / {m.p95:.0f} ms" if m.values() else "—")
        sysd = h.system
        fmt = {
            "cpu_percent": "{:.1f} %",
            "rss_mb": "{:.0f} MB",
            "rss_growth_mb_per_h": "{:+.1f} MB/h",
            "threads": "{:.0f}",
            "cache_entries": "{:.0f}",
        }
        for key, lbl in self.sys_lbls.items():
            lbl.setText(fmt[key].format(sysd[key]) if key in sysd else "—")
        lines = [
            f"{time.strftime('%H:%M:%S', time.localtime(e.at))}  {e.component:<8} {e.message}"
            for e in list(h.errors)[-80:]
        ]
        text = "\n".join(reversed(lines))
        if text != self.log.toPlainText():
            self.log.setPlainText(text)
