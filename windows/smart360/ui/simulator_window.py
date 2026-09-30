"""Demo mode: shows the practice simulator as a real window so users can watch 360 SMART
read, recommend and (after confirmation) click."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from smart360.capture.simulator import PracticeSimulator
from smart360.ui.calibration import pil_to_qimage


class SimulatorWindow(QWidget):
    """Mirrors the simulator's internal frame. The simulator itself is the 'screen' that the
    engine captures; this window just displays it and forwards the user's own clicks."""

    def __init__(self, sim: PracticeSimulator):
        super().__init__(None)
        self.sim = sim
        self.setWindowTitle("360 SMART · Practice simulator (demo)")
        self.setFixedSize(sim.width, sim.height)
        self._pix: QPixmap | None = None
        self._last_frame = None
        self._timer = QTimer(self, interval=100)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    def _refresh(self) -> None:
        frame = self.sim.render()
        if frame is not self._last_frame:
            self._last_frame = frame
            self._pix = QPixmap.fromImage(pil_to_qimage(frame))
            self.update()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        if self._pix is None:
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pix)
        p.end()

    def mousePressEvent(self, e):  # type: ignore[no-untyped-def]
        if e.button() == Qt.MouseButton.LeftButton:
            pt = e.position().toPoint()
            o = self.sim.origin
            self.sim.click(o[0] + pt.x(), o[1] + pt.y())

    def keyPressEvent(self, e):  # type: ignore[no-untyped-def]
        if e.key() in (Qt.Key.Key_Right, Qt.Key.Key_N):
            self.sim.next()

    def moveEvent(self, e):  # type: ignore[no-untyped-def]
        _ = QPoint
        super().moveEvent(e)
