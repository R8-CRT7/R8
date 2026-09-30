"""NEURAL GLASS design tokens.

Principles (derived from studying Raycast, Linear, Arc and automotive HUDs - not copied):
* one calm dark canvas, depth through light (gradients, inner highlights), not borders
* one electric accent (cyan) for "the AI speaks", violet only as secondary glow
* numbers are telemetry: tabular figures, generous size, quiet labels
* motion explains state (pulse), never decorates
"""

from __future__ import annotations

import random
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QLinearGradient, QPainter, QPixmap

ASSETS = Path(__file__).resolve().parent.parent / "assets"


class C:
    BG = QColor("#070B10")
    SURFACE = QColor("#0E151D")
    SURFACE_2 = QColor("#121C26")
    SURFACE_3 = QColor("#172431")
    GLASS = QColor(15, 24, 34, int(0.78 * 255))
    LINE = QColor(255, 255, 255, 22)
    LINE_STRONG = QColor(255, 255, 255, 40)
    PRIMARY = QColor("#30D5FF")
    PRIMARY_DIM = QColor(48, 213, 255, 40)
    SECONDARY = QColor("#7C6CFF")
    SUCCESS = QColor("#36E58A")
    WARNING = QColor("#FFB547")
    ERROR = QColor("#FF5C72")
    TEXT = QColor("#F5F8FA")
    TEXT_2 = QColor("#8E9BA8")
    TEXT_3 = QColor("#5B6875")
    ON_PRIMARY = QColor("#031018")


def hexa(c: QColor, alpha: float | None = None) -> str:
    if alpha is None:
        return c.name()
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha:.3f})"


def with_alpha(c: QColor, a: int) -> QColor:
    x = QColor(c)
    x.setAlpha(a)
    return x


class S:
    """Spacing scale (4 pt grid)."""

    XS, SM, MD, LG, XL, XXL = 4, 8, 12, 16, 24, 32
    RADIUS_SM, RADIUS, RADIUS_LG, RADIUS_XL = 8, 12, 16, 22


FAMILY = "Inter"
_loaded = False


def load_fonts() -> str:
    global FAMILY, _loaded
    if _loaded:
        return FAMILY
    fams: set[str] = set()
    for f in (ASSETS / "fonts").glob("Inter-*.ttf"):
        fid = QFontDatabase.addApplicationFont(str(f))
        if fid >= 0:
            fams.update(QFontDatabase.applicationFontFamilies(fid))
    FAMILY = "Inter" if "Inter" in fams else ("Segoe UI Variable Text" if not fams else sorted(fams)[0])
    _loaded = True
    return FAMILY


def font(
    size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
    tracking: float = 0.0,
    tabular: bool = False,
    caps: bool = False,
) -> QFont:
    f = QFont(FAMILY)
    f.setPixelSize(max(1, round(size)))
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if tracking:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    if caps:
        f.setCapitalization(QFont.Capitalization.AllUppercase)
    if tabular:
        try:
            f.setFeature(QFont.Tag("tnum"), 1)
        except (AttributeError, TypeError):
            pass
    return f


class T:
    """Type scale."""

    @staticmethod
    def hero() -> QFont:
        return font(40, QFont.Weight.DemiBold, -1.0, tabular=True)

    @staticmethod
    def display() -> QFont:
        return font(28, QFont.Weight.DemiBold, -0.6)

    @staticmethod
    def heading() -> QFont:
        return font(20, QFont.Weight.DemiBold, -0.3)

    @staticmethod
    def title() -> QFont:
        return font(15, QFont.Weight.DemiBold, -0.1)

    @staticmethod
    def body() -> QFont:
        return font(13.5)

    @staticmethod
    def body_medium() -> QFont:
        return font(13.5, QFont.Weight.Medium)

    @staticmethod
    def small() -> QFont:
        return font(12)

    @staticmethod
    def caption() -> QFont:
        return font(10.5, QFont.Weight.DemiBold, 1.3, caps=True)

    @staticmethod
    def telemetry(size: float = 13) -> QFont:
        return font(size, QFont.Weight.Medium, 0.2, tabular=True)


_noise: QPixmap | None = None


def noise_tile() -> QPixmap:
    """Subtle film grain (generated once, deterministic)."""
    global _noise
    if _noise is None:
        rng = random.Random(360)
        img = QImage(128, 128, QImage.Format.Format_ARGB32_Premultiplied)
        for y in range(128):
            for x in range(128):
                v = rng.randint(0, 255)
                a = rng.randint(0, 10)
                img.setPixelColor(x, y, QColor(v, v, v, a))
        _noise = QPixmap.fromImage(img)
    return _noise


def paint_canvas(p: QPainter, rect, glow: bool = True) -> None:  # type: ignore[no-untyped-def]
    """App background: deep base + two soft light sources + grain."""
    from PySide6.QtGui import QRadialGradient

    p.fillRect(rect, C.BG)
    if glow:
        g1 = QRadialGradient(
            rect.left() + rect.width() * 0.12, rect.top() - rect.height() * 0.05, rect.width() * 0.6
        )
        g1.setColorAt(0, with_alpha(C.PRIMARY, 26))
        g1.setColorAt(1, with_alpha(C.PRIMARY, 0))
        p.fillRect(rect, g1)
        g2 = QRadialGradient(rect.right(), rect.bottom(), rect.width() * 0.55)
        g2.setColorAt(0, with_alpha(C.SECONDARY, 22))
        g2.setColorAt(1, with_alpha(C.SECONDARY, 0))
        p.fillRect(rect, g2)
    p.drawTiledPixmap(rect, noise_tile())


def glass_gradient(top: float, bottom: float, alpha: int = 200) -> QLinearGradient:
    g = QLinearGradient(0, top, 0, bottom)
    g.setColorAt(0, QColor(22, 34, 46, alpha))
    g.setColorAt(1, QColor(12, 19, 27, alpha))
    return g


def rim_gradient(top: float, bottom: float, strength: int = 34) -> QLinearGradient:
    g = QLinearGradient(0, top, 0, bottom)
    g.setColorAt(0, QColor(255, 255, 255, strength))
    g.setColorAt(0.5, QColor(255, 255, 255, strength // 4))
    g.setColorAt(1, QColor(255, 255, 255, strength // 3))
    return g


def stylesheet() -> str:
    """Base QSS for stock widgets we still use (inputs, lists, scrollbars, combos)."""
    return f"""
    * {{ font-family: "{FAMILY}"; color: {C.TEXT.name()}; outline: none; }}
    QToolTip {{ background: {C.SURFACE_3.name()}; color: {C.TEXT.name()}; border: 1px solid {hexa(C.LINE_STRONG, 0.16)};
               padding: 6px 8px; border-radius: 8px; font-size: 12px; }}
    QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.10); border-radius: 3px; min-height: 36px; }}
    QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.20); }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ height: 0; background: none; }}
    QScrollBar:horizontal {{ height: 0; }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
        background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
        padding: 8px 12px; selection-background-color: {hexa(C.PRIMARY, 0.35)}; font-size: 13px; }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover {{ border-color: rgba(255,255,255,0.16); }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus {{
        border-color: {hexa(C.PRIMARY, 0.65)}; background: rgba(48,213,255,0.05); }}
    QLineEdit:disabled {{ color: {C.TEXT_3.name()}; }}
    QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; }}
    QComboBox {{ background: rgba(255,255,255,0.035); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
                padding: 7px 12px; font-size: 13px; min-height: 20px; }}
    QComboBox:hover {{ border-color: rgba(255,255,255,0.16); }}
    QComboBox::drop-down {{ width: 26px; border: none; }}
    QComboBox::down-arrow {{ image: none; width: 0; }}
    QComboBox QAbstractItemView {{ background: {C.SURFACE_2.name()}; border: 1px solid rgba(255,255,255,0.10);
        border-radius: 10px; padding: 4px; selection-background-color: rgba(48,213,255,0.16); }}
    QListView, QTreeView, QTableView {{ background: transparent; border: none; }}
    QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.08); border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C.SECONDARY.name()},
        stop:1 {C.PRIMARY.name()}); border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {C.TEXT.name()}; width: 16px; height: 16px; margin: -6px 0;
        border-radius: 8px; border: 3px solid {C.BG.name()}; }}
    QSlider::handle:horizontal:hover {{ background: {C.PRIMARY.name()}; }}
    QMenu {{ background: {C.SURFACE_2.name()}; border: 1px solid rgba(255,255,255,0.10); border-radius: 12px; padding: 6px; }}
    QMenu::item {{ padding: 8px 18px; border-radius: 8px; font-size: 13px; }}
    QMenu::item:selected {{ background: rgba(48,213,255,0.14); }}
    QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.08); margin: 6px 8px; }}
    QMessageBox {{ background: {C.SURFACE.name()}; }}
    """


def pen_color(state: str) -> QColor:
    return {
        "HEALTHY": C.SUCCESS,
        "DEGRADED": C.WARNING,
        "RECOVERING": C.SECONDARY,
        "FAILED": C.ERROR,
        "UNKNOWN": C.TEXT_3,
        "ok": C.SUCCESS,
        "warn": C.WARNING,
        "fail": C.ERROR,
    }.get(state, C.TEXT_2)


ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
