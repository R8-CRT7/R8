"""Stroke icons drawn with QPainterPath (24-unit grid, 1.7 px stroke). No icon font/deps."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _path(name: str) -> QPainterPath:
    p = QPainterPath()
    if name == "overview":
        for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
            p.addRoundedRect(QRectF(x, y, 8, 8), 2.2, 2.2)
    elif name == "session":
        p.moveTo(2, 12)
        for x, y in ((6, 12), (8.5, 6), (12, 18), (15, 9), (17, 12), (22, 12)):
            p.lineTo(x, y)
    elif name == "history":
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(12, 7)
        p.lineTo(12, 12)
        p.lineTo(15.5, 14)
    elif name == "insights":
        for x, h in ((4, 8), (10, 14), (16, 10)):
            p.addRoundedRect(QRectF(x, 20 - h, 4, h), 1.2, 1.2)
        p.moveTo(3, 21)
        p.lineTo(21, 21)
    elif name == "ai":

        def star(cx, cy, s):  # type: ignore[no-untyped-def]
            p.moveTo(cx, cy - s)
            p.quadTo(cx, cy, cx + s, cy)
            p.quadTo(cx, cy, cx, cy + s)
            p.quadTo(cx, cy, cx - s, cy)
            p.quadTo(cx, cy, cx, cy - s)

        star(10, 12, 7)
        star(18, 5.5, 3)
    elif name == "detection":
        for x0, y0, dx, dy in ((3, 3, 1, 1), (21, 3, -1, 1), (3, 21, 1, -1), (21, 21, -1, -1)):
            p.moveTo(x0, y0 + 5 * dy)
            p.lineTo(x0, y0)
            p.lineTo(x0 + 5 * dx, y0)
        p.addEllipse(QPointF(12, 12), 3.2, 3.2)
    elif name == "appearance":
        p.moveTo(12, 3)
        p.cubicTo(12, 3, 5, 11, 5, 15)
        p.cubicTo(5, 19, 8.2, 21.5, 12, 21.5)
        p.cubicTo(15.8, 21.5, 19, 19, 19, 15)
        p.cubicTo(19, 11, 12, 3, 12, 3)
    elif name == "settings":
        p.addEllipse(QPointF(12, 12), 3, 3)
        for i in range(8):
            a = math.radians(i * 45)
            p.moveTo(12 + math.cos(a) * 6.2, 12 + math.sin(a) * 6.2)
            p.lineTo(12 + math.cos(a) * 9, 12 + math.sin(a) * 9)
        p.addEllipse(QPointF(12, 12), 6.2, 6.2)
    elif name == "diagnostics":
        p.addRoundedRect(QRectF(3, 4, 18, 16), 3, 3)
        p.moveTo(6, 13)
        for x, y in ((9, 13), (10.5, 9), (13, 16), (14.5, 12), (18, 12)):
            p.lineTo(x, y)
    elif name == "pin":
        p.moveTo(9, 3)
        p.lineTo(15, 3)
        p.moveTo(10, 3)
        p.lineTo(10, 10)
        p.lineTo(6.5, 14)
        p.lineTo(17.5, 14)
        p.lineTo(14, 10)
        p.lineTo(14, 3)
        p.moveTo(12, 14)
        p.lineTo(12, 21)
    elif name == "close":
        p.moveTo(6, 6)
        p.lineTo(18, 18)
        p.moveTo(18, 6)
        p.lineTo(6, 18)
    elif name == "minimize":
        p.moveTo(6, 12)
        p.lineTo(18, 12)
    elif name == "maximize":
        p.addRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
    elif name == "search":
        p.addEllipse(QPointF(10.5, 10.5), 6, 6)
        p.moveTo(15, 15)
        p.lineTo(20, 20)
    elif name == "pause":
        p.addRoundedRect(QRectF(7, 5, 3.2, 14), 1.2, 1.2)
        p.addRoundedRect(QRectF(13.8, 5, 3.2, 14), 1.2, 1.2)
    elif name == "play":
        p.moveTo(8, 5.5)
        p.lineTo(18.5, 12)
        p.lineTo(8, 18.5)
        p.closeSubpath()
    elif name == "refresh":
        p.arcMoveTo(QRectF(5, 5, 14, 14), 60)
        p.arcTo(QRectF(5, 5, 14, 14), 60, 280)
        p.moveTo(17.8, 3.8)
        p.lineTo(18.2, 8.2)
        p.lineTo(13.8, 8.4)
    elif name == "check":
        p.moveTo(5, 12.5)
        p.lineTo(10, 17.5)
        p.lineTo(19.5, 7)
    elif name == "chevron":
        p.moveTo(9, 6)
        p.lineTo(15, 12)
        p.lineTo(9, 18)
    elif name == "chevron-down":
        p.moveTo(6, 9)
        p.lineTo(12, 15)
        p.lineTo(18, 9)
    elif name == "key":
        p.addEllipse(QPointF(8, 12), 4, 4)
        p.moveTo(12, 12)
        p.lineTo(21, 12)
        p.moveTo(18, 12)
        p.lineTo(18, 15.5)
    elif name == "shield":
        p.moveTo(12, 3)
        p.lineTo(19.5, 6)
        p.cubicTo(19.5, 13, 16.5, 18, 12, 21)
        p.cubicTo(7.5, 18, 4.5, 13, 4.5, 6)
        p.closeSubpath()
    elif name == "orbit":
        # planet with a tilted ring: the ring passes behind the planet (gap), so it never reads as an eye
        p.addEllipse(QPointF(12, 12), 4.6, 4.6)
        from PySide6.QtGui import QTransform

        ring = QPainterPath()
        ring.arcMoveTo(QRectF(1.5, 8.6, 21, 6.8), 200)
        ring.arcTo(QRectF(1.5, 8.6, 21, 6.8), 200, 320)
        p.addPath(QTransform().translate(12, 12).rotate(-24).translate(-12, -12).map(ring))
    elif name == "focus":
        p.addRoundedRect(QRectF(3, 7.5, 18, 9), 4.5, 4.5)
    elif name == "expand":
        p.addRoundedRect(QRectF(4, 4, 16, 16), 3, 3)
        p.moveTo(4, 9)
        p.lineTo(20, 9)
    elif name == "download":
        p.moveTo(12, 4)
        p.lineTo(12, 15)
        p.moveTo(7.5, 10.5)
        p.lineTo(12, 15)
        p.lineTo(16.5, 10.5)
        p.moveTo(5, 19.5)
        p.lineTo(19, 19.5)
    elif name == "info":
        p.addEllipse(QPointF(12, 12), 9, 9)
        p.moveTo(12, 11)
        p.lineTo(12, 16.5)
        p.addEllipse(QPointF(12, 7.8), 0.4, 0.4)
    elif name == "warning":
        p.moveTo(12, 3.5)
        p.lineTo(21, 19.5)
        p.lineTo(3, 19.5)
        p.closeSubpath()
        p.moveTo(12, 9.5)
        p.lineTo(12, 13.5)
        p.addEllipse(QPointF(12, 16.4), 0.4, 0.4)
    elif name == "window":
        p.addRoundedRect(QRectF(3, 4.5, 18, 15), 2.5, 2.5)
        p.moveTo(3, 8.5)
        p.lineTo(21, 8.5)
    elif name == "sparkle":
        p.moveTo(12, 2)
        p.quadTo(12, 12, 22, 12)
        p.quadTo(12, 12, 12, 22)
        p.quadTo(12, 12, 2, 12)
        p.quadTo(12, 12, 12, 2)
    elif name == "trash":
        p.moveTo(4, 7)
        p.lineTo(20, 7)
        p.moveTo(9, 7)
        p.lineTo(9.5, 4)
        p.lineTo(14.5, 4)
        p.lineTo(15, 7)
        p.moveTo(6, 7)
        p.lineTo(7, 20)
        p.lineTo(17, 20)
        p.lineTo(18, 7)
    elif name == "plus":
        p.moveTo(12, 5)
        p.lineTo(12, 19)
        p.moveTo(5, 12)
        p.lineTo(19, 12)
    elif name == "bolt":
        p.moveTo(13.5, 2.5)
        p.lineTo(5.5, 13.5)
        p.lineTo(11.5, 13.5)
        p.lineTo(10.5, 21.5)
        p.lineTo(18.5, 10.5)
        p.lineTo(12.5, 10.5)
        p.closeSubpath()
    return p


def draw_icon(
    painter: QPainter, name: str, rect: QRectF, color: QColor, width: float = 1.7, fill: bool = False
) -> None:
    path = _path(name)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = min(rect.width(), rect.height()) / 24.0
    painter.translate(rect.x() + (rect.width() - 24 * s) / 2, rect.y() + (rect.height() - 24 * s) / 2)
    painter.scale(s, s)
    pen = QPen(color, width / s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(color if fill else Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()


def icon(name: str, color: QColor, size: int = 24) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(2)
    p = QPainter(pm)
    draw_icon(p, name, QRectF(0, 0, size, size), color)
    p.end()
    return QIcon(pm)
