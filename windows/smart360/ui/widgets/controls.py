"""Neural Glass component library (custom painted, no stock look)."""

from __future__ import annotations

import time
from collections.abc import Sequence

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from smart360.ui.icons import draw_icon
from smart360.ui.theme import ALIGN_CENTER, ALIGN_LEFT, C, S, T, glass_gradient, rim_gradient, with_alpha

# ============================================================================ helpers


def label(
    text: str = "",
    font=None,
    color: QColor = C.TEXT,
    wrap: bool = False,  # type: ignore[no-untyped-def]
    selectable: bool = False,
) -> QLabel:
    lb = QLabel(text)
    lb.setFont(font or T.body())
    lb.setStyleSheet(f"color: {color.name(QColor.NameFormat.HexArgb)}; background: transparent;")
    lb.setWordWrap(wrap)
    if selectable:
        lb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return lb


def set_label_color(lb: QLabel, color: QColor) -> None:
    lb.setStyleSheet(f"color: {color.name(QColor.NameFormat.HexArgb)}; background: transparent;")


def clear_layout(lay) -> None:  # type: ignore[no-untyped-def]
    """Remove and destroy all items now (detach first: deleteLater alone leaves ghosts on screen)."""
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.hide()
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


def caption(text: str, color: QColor = C.TEXT_2) -> QLabel:
    return label(text, T.caption(), color)


def hbox(*widgets, spacing: int = S.SM, margins=(0, 0, 0, 0)) -> QHBoxLayout:  # type: ignore[no-untyped-def]
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, int):
            lay.addSpacing(w)
        elif isinstance(w, QHBoxLayout | QVBoxLayout):
            lay.addLayout(w)
        else:
            lay.addWidget(w)
    return lay


def vbox(*widgets, spacing: int = S.SM, margins=(0, 0, 0, 0)) -> QVBoxLayout:  # type: ignore[no-untyped-def]
    lay = QVBoxLayout()
    lay.setSpacing(spacing)
    lay.setContentsMargins(*margins)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, int):
            lay.addSpacing(w)
        elif isinstance(w, QHBoxLayout | QVBoxLayout):
            lay.addLayout(w)
        else:
            lay.addWidget(w)
    return lay


# ============================================================================ glass card


class GlassCard(QFrame):
    """Rounded glass surface: vertical tint gradient, 1px rim light, optional accent glow."""

    def __init__(
        self,
        parent: QWidget | None = None,
        radius: int = S.RADIUS_LG,
        padding: int = S.XL,
        accent: QColor | None = None,
        elevated: bool = False,
    ):
        super().__init__(parent)
        self.radius = radius
        self.accent = accent
        self.elevated = elevated
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(padding, padding, padding, padding)
        self.lay.setSpacing(S.MD)

    def set_accent(self, c: QColor | None) -> None:
        self.accent = c
        self.update()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, self.radius, self.radius)
        p.fillPath(path, glass_gradient(r.top(), r.bottom(), 235 if self.elevated else 205))
        if self.accent is not None:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, with_alpha(self.accent, 30))
            g.setColorAt(0.6, with_alpha(self.accent, 0))
            p.fillPath(path, g)
        p.setPen(QPen(rim_gradient(r.top(), r.bottom(), 40 if self.elevated else 30), 1))
        p.drawPath(path)
        p.end()


# ============================================================================ buttons


class GlowButton(QAbstractButton):
    """kind: primary | ghost | danger | warning | success | subtle"""

    def __init__(
        self,
        text: str = "",
        kind: str = "primary",
        icon: str | None = None,
        parent: QWidget | None = None,
        compact: bool = False,
    ):
        super().__init__(parent)
        self.setText(text)
        self.kind = kind
        self.icon_name = icon
        self.compact = compact
        self._hover = 0.0
        self._press = 0.0
        self._anim = QVariantAnimation(self, duration=160, easingCurve=QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFont(T.body_medium() if not compact else T.small())
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _set_hover(self, v) -> None:  # type: ignore[no-untyped-def]
        self._hover = float(v)
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        w = fm.horizontalAdvance(self.text()) + (40 if not self.compact else 26)
        if self.icon_name:
            w += 22 if self.text() else 0
        h = 40 if not self.compact else 32
        if not self.text():
            w = h
        return QSize(max(w, h), h)

    def enterEvent(self, e):  # type: ignore[no-untyped-def]
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(1.0)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):  # type: ignore[no-untyped-def]
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.0)
        self._anim.start()
        super().leaveEvent(e)

    def mousePressEvent(self, e):  # type: ignore[no-untyped-def]
        self._press = 1.0
        self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):  # type: ignore[no-untyped-def]
        self._press = 0.0
        self.update()
        super().mouseReleaseEvent(e)

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        base = {"primary": C.PRIMARY, "danger": C.ERROR, "warning": C.WARNING, "success": C.SUCCESS}
        if self.kind in base:
            c = base[self.kind]
            return c, c.lighter(112), C.ON_PRIMARY
        return QColor(255, 255, 255, 0), QColor(255, 255, 255, 0), C.TEXT

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        enabled = self.isEnabled()
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        if self._press:
            r = r.adjusted(0.8, 0.8, -0.8, -0.8)
        radius = min(10.0, r.height() / 2)
        c1, c2, fg = self._colors()
        filled = self.kind in ("primary", "danger", "warning", "success")
        path = QPainterPath()
        path.addRoundedRect(r, radius, radius)
        if filled:
            if enabled and self._hover > 0:
                for i in range(4):  # soft glow
                    gr = r.adjusted(-i * 1.5, -i * 1.5, i * 1.5, i * 1.5)
                    gp = QPainterPath()
                    gp.addRoundedRect(gr, radius + i * 1.5, radius + i * 1.5)
                    p.fillPath(gp, with_alpha(c1, int(22 * self._hover / (i + 1))))
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, c2 if enabled else with_alpha(c1, 60))
            g.setColorAt(1, c1 if enabled else with_alpha(c1, 50))
            p.fillPath(path, g)
            p.setPen(QPen(QColor(255, 255, 255, 70), 1))
            p.drawLine(QPointF(r.left() + radius, r.top() + 1), QPointF(r.right() - radius, r.top() + 1))
        else:
            bg_alpha = 14 + int(16 * self._hover) if self.kind == "ghost" else int(14 * self._hover)
            p.fillPath(path, QColor(255, 255, 255, bg_alpha))
            if self.kind == "ghost":
                p.setPen(QPen(QColor(255, 255, 255, 30 + int(30 * self._hover)), 1))
                p.drawPath(path)
            if self.isChecked():
                p.fillPath(path, with_alpha(C.PRIMARY, 30))
        text_color = fg if enabled else C.TEXT_3
        if not filled and self.kind == "subtle":
            text_color = C.TEXT if self._hover > 0.5 or self.isChecked() else C.TEXT_2
        p.setFont(self.font())
        fm = QFontMetrics(self.font())
        tw = fm.horizontalAdvance(self.text())
        iw = 18 if self.icon_name else 0
        gap = 8 if (self.icon_name and self.text()) else 0
        x = r.center().x() - (tw + iw + gap) / 2
        if self.icon_name:
            draw_icon(p, self.icon_name, QRectF(x, r.center().y() - iw / 2, iw, iw), text_color, 1.8)
        if self.text():
            p.setPen(text_color)
            p.drawText(QRectF(x + iw + gap, r.top(), tw + 2, r.height()), ALIGN_LEFT, self.text())
        p.end()


class IconButton(GlowButton):
    def __init__(
        self,
        icon: str,
        tooltip: str = "",
        size: int = 32,
        parent: QWidget | None = None,
        kind: str = "subtle",
    ):
        super().__init__("", kind, icon, parent, compact=True)
        self.setToolTip(tooltip)
        self.setFixedSize(size, size)


class Toggle(QAbstractButton):
    def __init__(self, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(
            self, b"knob", self, duration=180, easingCurve=QEasingCurve.Type.OutCubic
        )
        self.toggled.connect(self._animate)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(42, 24)

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    knob = Property(float, _get, _set)

    def _animate(self, on: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        off = QColor(255, 255, 255, 26)
        on = C.PRIMARY if self.isEnabled() else with_alpha(C.PRIMARY, 80)
        track = QColor(
            round(off.red() + (on.red() - off.red()) * self._pos),
            round(off.green() + (on.green() - off.green()) * self._pos),
            round(off.blue() + (on.blue() - off.blue()) * self._pos),
            round(off.alpha() + (on.alpha() - off.alpha()) * self._pos),
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * self._pos
        p.setBrush(QColor("#FFFFFF") if self.isEnabled() else C.TEXT_3)
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))
        p.end()


class Chip(QAbstractButton):
    """Status or filter chip. Checkable when used as a filter."""

    def __init__(
        self,
        text: str,
        color: QColor = C.TEXT_2,
        checkable: bool = False,
        dot: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setText(text)
        self.color = color
        self.dot = dot
        self.setCheckable(checkable)
        self.setFont(font_caption_chip())
        if checkable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set(self, text: str, color: QColor) -> None:
        self.setText(text)
        self.color = color
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + (30 if self.dot else 20), 24)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        active = self.isChecked() or not self.isCheckable()
        c = self.color if active else C.TEXT_2
        p.setPen(QPen(with_alpha(c, 90 if active else 40), 1))
        p.setBrush(with_alpha(c, 34 if active else 8))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        x = r.left() + 10
        if self.dot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x + 3, r.center().y()), 3, 3)
            x += 10
        p.setPen(c if active else C.TEXT_2)
        p.setFont(self.font())
        p.drawText(QRectF(x, r.top(), r.width(), r.height()), ALIGN_LEFT, self.text())
        p.end()


def font_caption_chip():  # type: ignore[no-untyped-def]
    from smart360.ui.theme import font

    return font(10.5, T.caption().weight(), 0.8, caps=True)


class KeyCap(QWidget):
    def __init__(self, key: str, text: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.key, self.text = key, text
        self.setFont(T.telemetry(10.5))
        fm = QFontMetrics(self.font())
        kw = max(22, fm.horizontalAdvance(key) + 12)
        self._kw = kw
        self.setFixedSize(kw + (fm.horizontalAdvance(text) + 8 if text else 0), 22)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(0.5, 0.5, self._kw - 1, 20)
        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(r, 5, 5)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawLine(QPointF(r.left() + 4, r.bottom() + 0.2), QPointF(r.right() - 4, r.bottom() + 0.2))
        p.setFont(self.font())
        p.setPen(C.TEXT)
        p.drawText(r, ALIGN_CENTER, self.key)
        if self.text:
            p.setPen(C.TEXT_2)
            p.drawText(QRectF(self._kw + 6, 0, self.width(), 21), ALIGN_LEFT, self.text)
        p.end()


# ============================================================================ data viz


def confidence_color(v: float, threshold: float = 0.75) -> QColor:
    if v >= 0.9:
        return C.SUCCESS
    if v >= threshold:
        return C.PRIMARY
    if v >= threshold - 0.2:
        return C.WARNING
    return C.ERROR


class ConfidenceMeter(QWidget):
    """Segmented, animated confidence bar. The segments light up like a HUD gauge."""

    def __init__(self, segments: int = 24, height: int = 10, parent: QWidget | None = None):
        super().__init__(parent)
        self.segments = segments
        self.threshold = 0.75
        self._value = 0.0
        self._target = 0.0
        self._anim = QPropertyAnimation(
            self, b"value", self, duration=650, easingCurve=QEasingCurve.Type.OutCubic
        )
        self.setFixedHeight(height)
        self.setMinimumWidth(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _get(self) -> float:
        return self._value

    def _set(self, v: float) -> None:
        self._value = v
        self.update()

    value = Property(float, _get, _set)

    def set_value(self, v: float, animate: bool = True) -> None:
        self._target = max(0.0, min(1.0, v))
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._value)
            self._anim.setEndValue(self._target)
            self._anim.start()
        else:
            self._set(self._target)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = self.segments
        gap = 3.0
        w = (self.width() - gap * (n - 1)) / n
        h = self.height()
        lit = self._value * n
        col = confidence_color(self._target, self.threshold)
        for i in range(n):
            x = i * (w + gap)
            r = QRectF(x, 0, w, h)
            frac = max(0.0, min(1.0, lit - i))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 16))
            p.drawRoundedRect(r, 2, 2)
            if frac > 0:
                g = QLinearGradient(0, 0, self.width(), 0)
                g.setColorAt(0, with_alpha(C.SECONDARY, 230))
                g.setColorAt(0.55, with_alpha(col, 240))
                g.setColorAt(1, col)
                p.setBrush(g)
                p.setOpacity(0.35 + 0.65 * frac)
                p.drawRoundedRect(r, 2, 2)
                p.setOpacity(1)
        # threshold tick
        tx = self.threshold * self.width()
        p.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DotLine))
        p.drawLine(QPointF(tx, -2), QPointF(tx, h + 2))
        p.end()


class Sparkline(QWidget):
    def __init__(self, color: QColor = C.PRIMARY, parent: QWidget | None = None):
        super().__init__(parent)
        self.values: list[float] = []
        self.color = color
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, values: Sequence[float]) -> None:
        self.values = list(values)[-40:]
        self.update()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        if len(self.values) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        lo, hi = min(self.values), max(self.values)
        span = (hi - lo) or 1.0
        w, h = self.width(), self.height() - 4
        pts = [
            QPointF(i * w / (len(self.values) - 1), 2 + h - (v - lo) / span * h)
            for i, v in enumerate(self.values)
        ]
        path = QPainterPath(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        fill = QPainterPath(path)
        fill.lineTo(w, h + 2)
        fill.lineTo(0, h + 2)
        fill.closeSubpath()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, with_alpha(self.color, 60))
        g.setColorAt(1, with_alpha(self.color, 0))
        p.fillPath(fill, g)
        p.setPen(QPen(self.color, 1.6))
        p.drawPath(path)
        p.setBrush(self.color)
        p.drawEllipse(pts[-1], 2.5, 2.5)
        p.end()


class StatTile(GlassCard):
    def __init__(
        self,
        title: str,
        value: str = "—",
        hint: str = "",
        color: QColor = C.PRIMARY,
        spark: bool = False,
        parent: QWidget | None = None,
    ):
        super().__init__(parent, padding=S.LG)
        self.lay.setSpacing(6)
        self.title = caption(title)
        self.value = label(value, T.telemetry(26), C.TEXT)
        self.hint = label(hint, T.small(), C.TEXT_3)
        self.lay.addWidget(self.title)
        self.lay.addWidget(self.value)
        self.spark = Sparkline(color) if spark else None
        if self.spark:
            self.lay.addWidget(self.spark)
        self.lay.addWidget(self.hint)
        self.setMinimumHeight(118)

    def set(self, value: str, hint: str | None = None) -> None:
        self.value.setText(value)
        if hint is not None:
            self.hint.setText(hint)


class HBar(QWidget):
    """Single horizontal value bar with label + value text (insights)."""

    def __init__(
        self, text: str, value: float, display: str, color: QColor = C.PRIMARY, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.text, self.v, self.display, self.color = text, max(0.0, min(1.0, value)), display, color
        self.setFixedHeight(34)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        p.setFont(T.body())
        p.setPen(C.TEXT)
        p.drawText(QRectF(0, 0, w * 0.32, 20), ALIGN_LEFT, self.text)
        p.setFont(T.telemetry(12))
        p.setPen(C.TEXT_2)
        p.drawText(
            QRectF(0, 0, w, 20), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.display
        )
        track = QRectF(0, 24, w, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 14))
        p.drawRoundedRect(track, 3, 3)
        g = QLinearGradient(0, 0, w, 0)
        g.setColorAt(0, with_alpha(C.SECONDARY, 220))
        g.setColorAt(1, self.color)
        p.setBrush(g)
        p.drawRoundedRect(QRectF(0, 24, max(6.0, w * self.v), 6), 3, 3)
        p.end()


# ============================================================================ segmented + misc


class SegmentedControl(QWidget):
    changed = Signal(str)

    def __init__(
        self, options: Sequence[tuple[str, str]], value: str | None = None, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.options = list(options)  # (value, label)
        self.value = value or self.options[0][0]
        self._x = float(self._index())
        self._anim = QVariantAnimation(self, duration=200, easingCurve=QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._move)
        self.setFont(T.body_medium())
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        fm = QFontMetrics(self.font())
        self.setMinimumWidth(sum(fm.horizontalAdvance(lab) + 34 for _, lab in self.options))

    def _index(self) -> int:
        return next((i for i, (v, _) in enumerate(self.options) if v == self.value), 0)

    def _move(self, v) -> None:  # type: ignore[no-untyped-def]
        self._x = float(v)
        self.update()

    def set_value(self, value: str, emit: bool = False) -> None:
        if value == self.value:
            return
        start = self._x
        self.value = value
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(float(self._index()))
        self._anim.start()
        if emit:
            self.changed.emit(value)

    def mousePressEvent(self, e):  # type: ignore[no-untyped-def]
        seg = self.width() / len(self.options)
        i = int(e.position().x() // seg)
        i = max(0, min(len(self.options) - 1, i))
        self.set_value(self.options[i][0], emit=True)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(255, 255, 255, 24), 1))
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(r, 11, 11)
        seg = r.width() / len(self.options)
        ind = QRectF(r.left() + 3 + self._x * seg, r.top() + 3, seg - 6, r.height() - 6)
        g = QLinearGradient(ind.topLeft(), ind.bottomLeft())
        g.setColorAt(0, QColor(48, 213, 255, 60))
        g.setColorAt(1, QColor(48, 213, 255, 30))
        p.setBrush(g)
        p.setPen(QPen(with_alpha(C.PRIMARY, 120), 1))
        p.drawRoundedRect(ind, 8, 8)
        p.setFont(self.font())
        for i, (v, lab) in enumerate(self.options):
            p.setPen(C.TEXT if v == self.value else C.TEXT_2)
            p.drawText(QRectF(r.left() + i * seg, r.top(), seg, r.height()), ALIGN_CENTER, lab)
        p.end()


class Skeleton(QWidget):
    """Shimmering placeholder while analysing (loading state)."""

    def __init__(self, height: int = 14, width_frac: float = 1.0, parent: QWidget | None = None):
        super().__init__(parent)
        self.width_frac = width_frac
        self.setFixedHeight(height)
        self._t0 = time.monotonic()
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self.update)

    def showEvent(self, e):  # type: ignore[no-untyped-def]
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):  # type: ignore[no-untyped-def]
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width() * self.width_frac
        r = QRectF(0, 0, w, self.height())
        k = ((time.monotonic() - self._t0) % 1.4) / 1.4
        g = QLinearGradient(-w + 2 * w * k, 0, 2 * w * k, 0)
        g.setColorAt(0, QColor(255, 255, 255, 12))
        g.setColorAt(0.5, QColor(255, 255, 255, 34))
        g.setColorAt(1, QColor(255, 255, 255, 12))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, self.height() / 2, self.height() / 2)
        p.end()


class EmptyState(QWidget):
    def __init__(self, title: str, text: str, icon: str = "sparkle", parent: QWidget | None = None):
        super().__init__(parent)
        self.icon = icon
        lay = vbox(None, spacing=S.SM, margins=(S.XL, S.XXL, S.XL, S.XXL))
        self._glyph = QWidget()
        self._glyph.setFixedSize(84, 84)
        self._glyph.paintEvent = self._paint_glyph  # type: ignore[method-assign]
        lay.addWidget(self._glyph, 0, ALIGN_CENTER)
        lay.addSpacing(S.MD)
        t = label(title, T.title(), C.TEXT)
        t.setAlignment(ALIGN_CENTER)
        d = label(text, T.body(), C.TEXT_2, wrap=True)
        d.setAlignment(ALIGN_CENTER)
        d.setMaximumWidth(380)
        lay.addWidget(t, 0, ALIGN_CENTER)
        lay.addWidget(d, 0, ALIGN_CENTER)
        lay.addStretch(1)
        self.setLayout(lay)

    def _paint_glyph(self, _e):  # type: ignore[no-untyped-def]
        from PySide6.QtGui import QRadialGradient

        p = QPainter(self._glyph)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(42, 42)
        g = QRadialGradient(c, 42)
        g.setColorAt(0, with_alpha(C.PRIMARY, 50))
        g.setColorAt(1, with_alpha(C.SECONDARY, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(c, 42, 42)
        p.setBrush(QColor(255, 255, 255, 10))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawEllipse(c, 26, 26)
        draw_icon(p, self.icon, QRectF(30, 30, 24, 24), C.PRIMARY, 1.8)
        p.end()


class FadeStack(QStackedWidget):
    """Stacked widget with a short cross-fade + rise when switching pages."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._anim: QPropertyAnimation | None = None
        self.reduce_motion = False

    def fade_to(self, index: int) -> None:
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        if self.reduce_motion:
            return
        w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w, duration=220, easingCurve=QEasingCurve.Type.OutCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: w.setGraphicsEffect(None))  # type: ignore[arg-type]
        anim.start()
        self._anim = anim


class Divider(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor(255, 255, 255, 0))
        g.setColorAt(0.2, QColor(255, 255, 255, 22))
        g.setColorAt(0.8, QColor(255, 255, 255, 22))
        g.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), g)
        p.end()


class SettingRow(QWidget):
    """Label + description on the left, a control on the right."""

    def __init__(self, title: str, description: str, control: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        left = vbox(label(title, T.body_medium()), spacing=2)
        if description:
            d = label(description, T.small(), C.TEXT_2, wrap=True)
            left.addWidget(d)
        lay = hbox(left, None, control, spacing=S.LG, margins=(0, 6, 0, 6))
        lay.setStretch(0, 3)
        self.setLayout(lay)
        self.control = control
