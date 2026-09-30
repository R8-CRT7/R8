"""Main dashboard window: frameless, custom title bar, sidebar navigation, pages, toasts."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from smart360 import __version__
from smart360.platform import win32
from smart360.ui.icons import draw_icon
from smart360.ui.overlay import STATE_TITLES
from smart360.ui.pages.base import Page, UiContext
from smart360.ui.pages.diagnostics import DiagnosticsPage
from smart360.ui.pages.history import HistoryPage, InsightsPage
from smart360.ui.pages.overview import OverviewPage, SessionPage
from smart360.ui.pages.settings import AIPage, AppearancePage, DetectionPage, SettingsPage
from smart360.ui.theme import ALIGN_LEFT, C, S, T, font, paint_canvas, with_alpha
from smart360.ui.widgets.controls import FadeStack, IconButton, caption, hbox, label, set_label_color
from smart360.ui.widgets.pulse import NeuralPulse, state_for_engine

NAV = (
    ("overview", "Overview", OverviewPage),
    ("session", "Session", SessionPage),
    ("history", "History", HistoryPage),
    ("insights", "Insights", InsightsPage),
    ("ai", "AI", AIPage),
    ("detection", "Detection", DetectionPage),
    ("appearance", "Appearance", AppearancePage),
    ("settings", "Settings", SettingsPage),
    ("diagnostics", "Diagnostics", DiagnosticsPage),
)


class NavItem(QAbstractButton):
    def __init__(self, icon: str, text: str):
        super().__init__()
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(40)
        self._hover = 0.0
        self._anim = QVariantAnimation(self, duration=140)
        self._anim.valueChanged.connect(self._set_hover)

    def _set_hover(self, v) -> None:  # type: ignore[no-untyped-def]
        self._hover = float(v)
        self.update()

    def enterEvent(self, e):  # type: ignore[no-untyped-def]
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def leaveEvent(self, e):  # type: ignore[no-untyped-def]
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 2, -8, -2)
        on = self.isChecked()
        if on or self._hover > 0:
            path = QPainterPath()
            path.addRoundedRect(r, 10, 10)
            if on:
                g = QLinearGradient(r.topLeft(), r.topRight())
                g.setColorAt(0, with_alpha(C.PRIMARY, 34))
                g.setColorAt(1, with_alpha(C.PRIMARY, 6))
                p.fillPath(path, g)
            else:
                p.fillPath(path, QColor(255, 255, 255, int(10 * self._hover)))
        col = C.TEXT if on else (C.TEXT if self._hover > 0.5 else C.TEXT_2)
        draw_icon(
            p,
            self.icon_name,
            QRectF(r.left() + 12, r.center().y() - 9, 18, 18),
            C.PRIMARY if on else col,
            1.7,
        )
        p.setFont(T.body_medium())
        p.setPen(col)
        p.drawText(QRectF(r.left() + 42, r.top(), r.width() - 50, r.height()), ALIGN_LEFT, self.text())
        p.end()


class Sidebar(QWidget):
    navigate = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setFixedWidth(228)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, S.LG, 8, S.LG)
        lay.setSpacing(2)
        self.items: list[NavItem] = []
        for i, (key, text, _cls) in enumerate(NAV):
            if key == "ai":
                lay.addSpacing(S.MD)
                c = caption("Configure", C.TEXT_3)
                c.setContentsMargins(20, 0, 0, 6)
                lay.addWidget(c)
            it = NavItem(key, text)
            it.clicked.connect(lambda _c=False, idx=i: self.select(idx, emit=True))
            self.items.append(it)
            lay.addWidget(it)
        lay.addStretch(1)
        # live engine card
        self.card = QWidget()
        self.card.setFixedHeight(64)
        self.pulse = NeuralPulse(40)
        self.state_lbl = label("WATCHING", T.caption(), C.PRIMARY)
        self.status_lbl = label("Starting…", T.small(), C.TEXT_2, wrap=True)
        self.status_lbl.setFixedWidth(150)
        from smart360.ui.widgets.controls import vbox

        self.card.setLayout(
            hbox(self.pulse, vbox(self.state_lbl, self.status_lbl, spacing=2), None, margins=(12, 0, 8, 0))
        )
        lay.addWidget(self.card)
        self._ind_y = 0.0
        self._ind = QVariantAnimation(self, duration=220, easingCurve=QEasingCurve.Type.OutCubic)
        self._ind.valueChanged.connect(self._set_ind)
        self.current = 0

    def _set_ind(self, v) -> None:  # type: ignore[no-untyped-def]
        self._ind_y = float(v)
        self.update()

    def select(self, idx: int, emit: bool = False) -> None:
        for i, it in enumerate(self.items):
            it.setChecked(i == idx)
        target = self.items[idx].geometry().center().y()
        self._ind.stop()
        self._ind.setStartValue(self._ind_y or float(target))
        self._ind.setEndValue(float(target))
        self._ind.start()
        self.current = idx
        if emit:
            self.navigate.emit(idx)

    def resizeEvent(self, e):  # type: ignore[no-untyped-def]
        super().resizeEvent(e)
        QTimer.singleShot(0, lambda: self.select(self.current))

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(255, 255, 255, 5))
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.drawLine(QPointF(self.width() - 0.5, 0), QPointF(self.width() - 0.5, self.height()))
        if self._ind_y:
            y = self._ind_y
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C.PRIMARY)
            p.drawRoundedRect(QRectF(4, y - 9, 3, 18), 1.5, 1.5)
            for i in range(3):
                p.setBrush(with_alpha(C.PRIMARY, 30 - i * 9))
                p.drawRoundedRect(QRectF(3 - i, y - 11 - i, 5 + i * 2, 22 + i * 2), 3, 3)
        p.end()


class TitleBar(QWidget):
    def __init__(self, window: QWidget):
        super().__init__(window)
        self.win = window
        self.setFixedHeight(48)
        self.logo = NeuralPulse(26)
        name = label("360 SMART", font(14, T.title().weight(), 0.8), C.TEXT)
        tag = label(f"AI Driving Theory Assistant  ·  {__version__}", T.small(), C.TEXT_3)
        self.page_lbl = label("", T.small(), C.TEXT_2)
        self.btn_overlay = IconButton("orbit", "Show / hide overlay", 30)
        self.btn_min = IconButton("minimize", "Minimize", 30)
        self.btn_max = IconButton("maximize", "Maximize", 30)
        self.btn_close = IconButton("close", "Close to tray", 30)
        self.btn_min.clicked.connect(window.showMinimized)
        self.btn_max.clicked.connect(self._toggle_max)
        self.btn_close.clicked.connect(window.close)
        lay = hbox(
            self.logo,
            name,
            10,
            tag,
            None,
            self.page_lbl,
            16,
            self.btn_overlay,
            8,
            self.btn_min,
            self.btn_max,
            self.btn_close,
            spacing=6,
            margins=(S.LG, 0, S.MD, 0),
        )
        self.setLayout(lay)
        self._drag: QPoint | None = None

    def _toggle_max(self) -> None:
        if self.win.isMaximized():
            self.win.showNormal()
        else:
            self.win.showMaximized()

    def mousePressEvent(self, e: QMouseEvent) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            handle = self.win.windowHandle()
            if handle is not None and handle.startSystemMove():
                return  # native move: supports Aero snap on Windows
            self._drag = e.globalPosition().toPoint() - self.win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        self._drag = None

    def mouseDoubleClickEvent(self, e: QMouseEvent) -> None:
        self._toggle_max()


class Toast(QWidget):
    COLORS = {"success": C.SUCCESS, "error": C.ERROR, "warning": C.WARNING, "info": C.PRIMARY}

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.hide()
        self.text = QLabel(self)
        self.text.setFont(T.body_medium())
        self.color = C.PRIMARY
        lay = QHBoxLayout(self)
        lay.setContentsMargins(38, 12, 18, 12)
        lay.addWidget(self.text)
        self._eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._eff)
        self._anim = QPropertyAnimation(self._eff, b"opacity", self, duration=220)
        self._timer = QTimer(self, singleShot=True)
        self._timer.timeout.connect(self._fade_out)

    def show_message(self, text: str, kind: str = "info") -> None:
        self.color = self.COLORS.get(kind, C.PRIMARY)
        self.text.setText(text)
        set_label_color(self.text, C.TEXT)
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - 24, par.height() - self.height() - 24)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(3200)

    def _fade_out(self) -> None:
        self._anim.stop()
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 12, 12)
        p.fillPath(path, C.SURFACE_3)
        p.fillPath(path, with_alpha(self.color, 22))
        p.setPen(QPen(with_alpha(self.color, 120), 1))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(QPointF(20, r.center().y()), 4, 4)
        p.end()


class Dashboard(QWidget):
    overlay_toggle = Signal()
    closing = Signal()

    def __init__(self, ctx: UiContext):
        super().__init__(None)
        self.ctx = ctx
        self.setWindowTitle("360 SMART")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(1060, 700)
        self.resize(1240, 800)
        self.titlebar = TitleBar(self)
        self.titlebar.btn_overlay.clicked.connect(self.overlay_toggle.emit)
        self.sidebar = Sidebar()
        self.stack = FadeStack()
        self.pages: list[Page] = []
        for _key, _text, cls in NAV:
            page = cls(ctx)
            self.pages.append(page)
            self.stack.addWidget(page)
        self.sidebar.navigate.connect(self.go)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.titlebar)
        body = QHBoxLayout()
        body.setSpacing(0)
        body.addWidget(self.sidebar)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)
        self.toast = Toast(self)
        self.tick = QTimer(self, interval=1000)
        self.tick.timeout.connect(self._tick)
        self.tick.start()
        ctx.bridge.state.connect(self._on_state)
        ctx.bridge.status.connect(self.sidebar.status_lbl.setText)
        QTimer.singleShot(0, lambda: self.go(0))

    def go(self, idx: int) -> None:
        self.sidebar.select(idx)
        self.stack.fade_to(idx)
        self.titlebar.page_lbl.setText(NAV[idx][1])
        try:
            self.pages[idx].refresh()
        except Exception as e:  # a page bug must not take the app down
            self.ctx.services.health.record_error("UI", f"page refresh failed: {e}")

    def go_to(self, key: str) -> None:
        for i, (k, _t, _c) in enumerate(NAV):
            if k == key:
                self.go(i)

    def _tick(self) -> None:
        if not self.isVisible():
            return
        try:
            self.pages[self.stack.currentIndex()].refresh()
        except Exception as e:
            self.ctx.services.health.record_error("UI", f"page refresh failed: {e}")

    def _on_state(self, state: str, _r: str) -> None:
        eng = self.ctx.services.engine
        p = eng.prediction if eng else None
        pulse = state_for_engine(state, bool(p and p.uncertain))
        self.sidebar.pulse.set_state(pulse)
        self.titlebar.logo.set_state(pulse)
        self.sidebar.state_lbl.setText(STATE_TITLES.get(state, state))
        set_label_color(self.sidebar.state_lbl, {"ERROR": C.ERROR, "PAUSED": C.TEXT_2}.get(state, C.PRIMARY))

    def set_reduce_motion(self, on: bool) -> None:
        self.stack.reduce_motion = on
        self.sidebar.pulse.set_reduce_motion(on)
        self.titlebar.logo.set_reduce_motion(on)

    def resizeEvent(self, e):  # type: ignore[no-untyped-def]
        super().resizeEvent(e)
        self.grip.move(self.width() - 16, self.height() - 16)

    def showEvent(self, e):  # type: ignore[no-untyped-def]
        super().showEvent(e)
        if win32.IS_WINDOWS and self.ctx.services.config.appearance.system_backdrop:
            win32.enable_backdrop(int(self.winId()), 3)

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        paint_canvas(p, self.rect())
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawLine(0, 48, self.width(), 48)
        p.end()

    def closeEvent(self, e):  # type: ignore[no-untyped-def]
        self.closing.emit()
        super().closeEvent(e)

    def sizeHint(self) -> QSize:
        return QSize(1240, 800)
