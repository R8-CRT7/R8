"""Calibration wizard: select Question / Answers / Image / Action areas on a snapshot of the
learning window, test detection live, save as a layout profile.

Steps: 1 Question area · 2 Answers area · 3 Image & action (optional) · 4 Test detection · 5 Save
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLineEdit, QWidget

from smart360.core.models import NormRect, Rect
from smart360.ui.theme import ALIGN_LEFT, C, S, T, glass_gradient, rim_gradient, with_alpha
from smart360.ui.widgets.controls import GlowButton, caption, hbox, label, set_label_color, vbox
from smart360.vision.extractor import LayoutProfile, QuestionExtractor

STEPS = (
    ("question", "Select the question area", "Drag a box around the question text."),
    ("answers", "Select the answers area", "Include the checkboxes on the left and all answer texts."),
    (
        "extras",
        "Image & action area (optional)",
        "Drag the situation image first, then the 'next' button. Skip if the layout has none.",
    ),
    ("test", "Test detection", "360 SMART reads the snapshot with your regions."),
    ("save", "Save profile", "Name it after your setup - e.g. Laptop, Desktop, Fullscreen."),
)
COLORS = {"question": C.PRIMARY, "answers": C.SUCCESS, "image": C.SECONDARY, "action": C.WARNING}


def pil_to_qimage(img: Image.Image) -> QImage:
    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    q = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888)
    return q.copy()


class CalibrationWizard(QWidget):
    saved = Signal(dict)
    cancelled = Signal()

    def __init__(
        self,
        snapshot: Image.Image,
        frame_rect: Rect,
        extractor: QuestionExtractor,
        existing_names: list[str] | None = None,
    ):
        super().__init__(None)
        self.setWindowTitle("360 SMART · Calibration")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint
        )
        self.snapshot = snapshot
        self.frame_rect = frame_rect
        self.extractor = extractor
        self.existing = set(existing_names or [])
        self.pix = QPixmap.fromImage(pil_to_qimage(snapshot))
        self.regions: dict[str, QRectF] = {}  # in image pixel coordinates
        self.step = 0
        self._drag_start: QPointF | None = None
        self._drag_rect: QRectF | None = None
        self.test_result = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # floating instruction panel
        self.panel = QWidget(self)
        self.panel.setFixedWidth(430)
        self.panel.paintEvent = self._paint_panel  # type: ignore[method-assign]
        self.step_lbl = caption("", C.PRIMARY)
        self.title_lbl = label("", T.heading())
        self.desc_lbl = label("", T.body(), C.TEXT_2, wrap=True)
        self.result_lbl = label("", T.small(), C.TEXT, wrap=True)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Profile name")
        self.btn_back = GlowButton("Back", "ghost", compact=True)
        self.btn_skip = GlowButton("Skip", "subtle", compact=True)
        self.btn_next = GlowButton("Next", "primary", "chevron", compact=True)
        self.btn_cancel = GlowButton("Cancel", "subtle", compact=True)
        self.btn_back.clicked.connect(self.back)
        self.btn_next.clicked.connect(self.next)
        self.btn_skip.clicked.connect(self.skip)
        self.btn_cancel.clicked.connect(self._cancel)
        lay = vbox(
            self.step_lbl,
            self.title_lbl,
            self.desc_lbl,
            self.result_lbl,
            self.name,
            hbox(self.btn_cancel, None, self.btn_back, self.btn_skip, self.btn_next),
            spacing=S.SM,
            margins=(S.XL, S.XL + 4, S.XL, S.LG),
        )
        self.panel.setLayout(lay)
        self._sync()

    # ------------------------------------------------------------------ geometry
    def _image_rect(self) -> QRectF:
        """Where the snapshot is drawn (letterboxed, aspect preserved)."""
        w, h = self.width(), self.height()
        iw, ih = self.pix.width(), self.pix.height()
        s = min(w / iw, h / ih)
        return QRectF((w - iw * s) / 2, (h - ih * s) / 2, iw * s, ih * s)

    def _to_img(self, pt: QPointF) -> QPointF:
        r = self._image_rect()
        s = r.width() / self.pix.width()
        x = min(max(0.0, (pt.x() - r.left()) / s), self.pix.width())
        y = min(max(0.0, (pt.y() - r.top()) / s), self.pix.height())
        return QPointF(x, y)

    def _to_screen(self, rect: QRectF) -> QRectF:
        r = self._image_rect()
        s = r.width() / self.pix.width()
        return QRectF(
            r.left() + rect.left() * s, r.top() + rect.top() * s, rect.width() * s, rect.height() * s
        )

    # ------------------------------------------------------------------ steps
    def _current_key(self) -> str:
        key = STEPS[self.step][0]
        if key == "extras":
            return "image" if "image" not in self.regions else "action"
        return key

    def _sync(self) -> None:
        key, title, desc = STEPS[self.step]
        self.step_lbl.setText(f"STEP {self.step + 1} OF {len(STEPS)}")
        self.title_lbl.setText(title)
        self.desc_lbl.setText(desc)
        self.name.setVisible(key == "save")
        self.btn_skip.setVisible(key == "extras")
        self.btn_back.setEnabled(self.step > 0)
        if key in ("question", "answers"):
            self.btn_next.setEnabled(key in self.regions)
        else:
            self.btn_next.setEnabled(True)
        self.btn_next.setText("Save" if key == "save" else "Next")
        self.result_lbl.setVisible(key == "test")
        if key == "test":
            self._run_test()
        self.panel.adjustSize()
        self._place_panel()
        self.update()

    def next(self) -> None:
        key = STEPS[self.step][0]
        if key == "save":
            self._save()
            return
        self.step = min(len(STEPS) - 1, self.step + 1)
        self._sync()

    def back(self) -> None:
        self.step = max(0, self.step - 1)
        self._sync()

    def skip(self) -> None:
        self.step += 1
        self._sync()

    def _cancel(self) -> None:
        self.cancelled.emit()
        self.close()

    def keyPressEvent(self, e: QKeyEvent) -> None:
        if e.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.btn_next.isEnabled():
            self.next()

    # ------------------------------------------------------------------ profile
    def profile_dict(self, name: str) -> dict:
        iw, ih = self.pix.width(), self.pix.height()

        def norm(k: str) -> list[float] | None:
            r = self.regions.get(k)
            if r is None:
                return None
            n = NormRect(r.left() / iw, r.top() / ih, r.width() / iw, r.height() / ih)
            return [round(n.x, 5), round(n.y, 5), round(n.w, 5), round(n.h, 5)]

        return {
            "name": name,
            "question": norm("question"),
            "answers": norm("answers"),
            "image": norm("image"),
            "action": norm("action"),
            "ref_width": self.frame_rect.w,
            "ref_height": self.frame_rect.h,
        }

    def _run_test(self) -> None:
        try:
            prof = LayoutProfile.from_dict(self.profile_dict("test"))
            res = self.extractor.extract(
                self.snapshot, Rect(0, 0, self.snapshot.width, self.snapshot.height), prof, with_crops=False
            )
        except Exception as e:
            self.result_lbl.setText(f"Test failed: {e}")
            set_label_color(self.result_lbl, C.ERROR)
            return
        q = res.question
        self.test_result = q
        if q is None:
            self.result_lbl.setText(
                f"No question detected ({res.problem}). Adjust the regions or make sure a "
                "question is visible."
            )
            set_label_color(self.result_lbl, C.WARNING)
        else:
            ans = "\n".join(f"{a.index}. {a.text}" for a in q.answers) or "Number input question"
            self.result_lbl.setText(
                f"✓ {q.text}\n\n{ans}\n\nOCR confidence {q.ocr_confidence * 100:.0f} %  ·  "
                f"{len(q.answers)} answers  ·  image: {'yes' if q.has_image else 'no'}"
            )
            set_label_color(self.result_lbl, C.TEXT)
        self.update()

    def _save(self) -> None:
        name = self.name.text().strip() or "Profile"
        base, i = name, 2
        while name in self.existing:
            name = f"{base} {i}"
            i += 1
        self.saved.emit(self.profile_dict(name))
        self.close()

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, e: QMouseEvent) -> None:
        if STEPS[self.step][0] in ("test", "save"):
            return
        if self.panel.geometry().contains(e.position().toPoint()):
            return
        self._drag_start = self._to_img(e.position())
        self._drag_rect = None

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        if self._drag_start is not None:
            cur = self._to_img(e.position())
            self._drag_rect = QRectF(self._drag_start, cur).normalized()
            self.update()

    def mouseReleaseEvent(self, e: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        r = self._drag_rect
        self._drag_start, self._drag_rect = None, None
        if r is None or r.width() < 12 or r.height() < 8:
            self.update()
            return
        key = self._current_key()
        self.regions[key] = r
        if STEPS[self.step][0] == "extras" and key == "action":
            self.step += 1
        elif STEPS[self.step][0] != "extras":
            pass
        self._sync()

    # ------------------------------------------------------------------ paint
    def resizeEvent(self, e):  # type: ignore[no-untyped-def]
        super().resizeEvent(e)
        self._place_panel()

    def _place_panel(self) -> None:
        """Put the instruction panel in the corner that covers the fewest selected regions."""
        pw, ph, m = self.panel.width(), self.panel.height(), 28
        corners = [
            (self.width() - pw - m, m),
            (self.width() - pw - m, self.height() - ph - m),
            (m, self.height() - ph - m),
            (m, m),
        ]
        regions = [self._to_screen(r) for r in self.regions.values()]

        def overlap(pos: tuple[int, int]) -> float:
            pr = QRectF(pos[0], pos[1], pw, ph)
            return sum((pr & r).width() * (pr & r).height() for r in regions if pr.intersects(r))

        best = min(corners, key=overlap)
        self.panel.move(int(best[0]), int(best[1]))

    def _paint_panel(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self.panel)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.panel.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 18, 18)
        p.fillPath(path, glass_gradient(r.top(), r.bottom(), 245))
        p.setPen(QPen(rim_gradient(r.top(), r.bottom(), 50), 1))
        p.drawPath(path)
        # progress bar
        seg = (r.width() - 48) / len(STEPS)
        for i in range(len(STEPS)):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(C.PRIMARY if i <= self.step else QColor(255, 255, 255, 30))
            p.drawRoundedRect(QRectF(r.left() + 24 + i * seg, r.top() + 14, seg - 6, 3), 1.5, 1.5)
        p.end()

    def paintEvent(self, _e):  # type: ignore[no-untyped-def]
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), C.BG)
        ir = self._image_rect()
        p.drawPixmap(ir, self.pix, QRectF(self.pix.rect()))
        p.fillRect(ir, QColor(7, 11, 16, 120))  # dim
        for key, rect in self.regions.items():
            self._draw_region(p, key, self._to_screen(rect))
        if self._drag_rect is not None:
            self._draw_region(p, self._current_key(), self._to_screen(self._drag_rect), live=True)
        if self.test_result is not None and STEPS[self.step][0] == "test":
            for a in self.test_result.answers:
                if a.checkbox:
                    cb = QRectF(a.checkbox.x, a.checkbox.y, a.checkbox.w, a.checkbox.h)
                    p.setPen(QPen(C.SUCCESS, 2))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawRoundedRect(self._to_screen(cb), 3, 3)
        p.end()

    def _draw_region(self, p: QPainter, key: str, r: QRectF, live: bool = False) -> None:
        col = COLORS.get(key, C.PRIMARY)
        # un-dim the selected region so the content is readable
        src = QRectF(r)
        ir = self._image_rect()
        s = self.pix.width() / ir.width()
        p.drawPixmap(
            r,
            self.pix,
            QRectF(
                (src.left() - ir.left()) * s, (src.top() - ir.top()) * s, src.width() * s, src.height() * s
            ),
        )
        p.setPen(QPen(col, 2, Qt.PenStyle.DashLine if live else Qt.PenStyle.SolidLine))
        p.setBrush(with_alpha(col, 22))
        p.drawRoundedRect(r, 6, 6)
        p.setFont(T.caption())
        tag = QRectF(r.left(), r.top() - 22, 110, 18)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(tag, 6, 6)
        p.setPen(C.ON_PRIMARY)
        p.drawText(tag.adjusted(8, 0, 0, 0), ALIGN_LEFT, key.upper())
        _ = QRect
