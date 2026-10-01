"""Thread-safe bridge: engine events (worker threads) -> Qt signals (UI thread)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from smart360.engine.engine import EngineEvent


class EngineBridge(QObject):
    # Signals emitted from engine threads are delivered to UI slots via queued connections.
    event = Signal(object)
    state = Signal(str, str)  # new state, reason
    question = Signal(object)
    prediction = Signal(object)
    status = Signal(str)
    execution = Signal(dict)
    stats = Signal(dict)
    error = Signal(str, str)
    hotkey = Signal(str)
    health = Signal(str, object)
    estop = Signal()

    def sink(self, ev: EngineEvent) -> None:
        """Called from engine/worker threads. Only emits signals (never touches widgets)."""
        self.event.emit(ev)
        d = ev.data
        if ev.kind == "state":
            self.state.emit(d["new"], d.get("reason", ""))
        elif ev.kind == "question":
            self.question.emit(d.get("question"))
        elif ev.kind == "prediction":
            self.prediction.emit(d.get("prediction"))
        elif ev.kind == "status":
            self.status.emit(d.get("text", ""))
        elif ev.kind == "execution":
            self.execution.emit(dict(d))
        elif ev.kind == "stats":
            self.stats.emit(dict(d))
        elif ev.kind == "error":
            self.error.emit(d.get("message", ""), d.get("kind", ""))
        elif ev.kind == "estop":
            self.estop.emit()
