"""Dry run: crosshair markers on the screen exactly where 360 SMART WOULD click.

Small frameless, always-on-top, click-through windows; excluded from screen capture so they never
disturb OCR. Click coordinates are physical screen pixels (the process is per-monitor DPI aware);
Qt places windows in logical coordinates, so they are converted per screen. The trace picture with the
red cross (Create diagnosis) is the exact record; the on-screen marker is the live view.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

SIZE = 72


def physical_to_logical(x: int, y: int) -> QPoint:
    """Physical screen pixel -> Qt logical coordinate (Qt 6 keeps each screen's top-left native)."""
    for scr in QGuiApplication.screens():
        g, dpr = scr.geometry(), scr.devicePixelRatio()
        if g.x() <= x < g.x() + g.width() * dpr and g.y() <= y < g.y() + g.height() * dpr:
            return QPoint(round(g.x() + (x - g.x()) / dpr), round(g.y() + (y - g.y()) / dpr))
    return QPoint(x, y)


class ClickMarker(QWidget):
    def __init__(self, label: str, blocked: bool = False):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(SIZE, SIZE)
        self.label = label
        self.blocked = blocked

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(120, 120, 120) if self.blocked else QColor(230, 30, 30)
        mid = SIZE / 2
        p.setPen(QPen(QColor(255, 255, 255, 200), 6))
        p.drawLine(int(mid - 22), int(mid), int(mid + 22), int(mid))
        p.drawLine(int(mid), int(mid - 22), int(mid), int(mid + 22))
        p.setPen(QPen(c, 3))
        p.drawLine(int(mid - 22), int(mid), int(mid + 22), int(mid))
        p.drawLine(int(mid), int(mid - 22), int(mid), int(mid + 22))
        p.drawEllipse(QRectF(mid - 9, mid - 9, 18, 18))
        p.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        p.drawText(QRectF(mid + 8, 0, SIZE - mid - 8, 18), Qt.AlignmentFlag.AlignLeft, self.label)
        p.end()


class ClickMarkers:
    """Shows one marker per planned click; they vanish after `seconds` or on clear()."""

    def __init__(self) -> None:
        self.markers: list[ClickMarker] = []
        self._timer = QTimer(singleShot=True)
        self._timer.timeout.connect(self.clear)

    def show_points(self, clicks: list[dict], seconds: float = 10.0) -> None:
        self.clear()
        for c in clicks:
            m = ClickMarker(str(c.get("answer", "")), blocked=bool(c.get("blocked")))
            pos = physical_to_logical(int(c["x"]), int(c["y"]))
            m.move(pos.x() - SIZE // 2, pos.y() - SIZE // 2)
            m.show()
            try:
                from smart360.platform import win32

                win32.exclude_from_capture(int(m.winId()))
            except Exception:
                pass
            self.markers.append(m)
        self._timer.start(int(seconds * 1000))

    def clear(self) -> None:
        for m in self.markers:
            m.close()
            m.deleteLater()
        self.markers = []
