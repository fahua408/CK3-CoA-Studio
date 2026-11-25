"""1:1 Image preview canvas with optional CK3 heraldic shield/seal overlay guides."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class CoaPreviewWidget(QWidget):
    """Displays a Coat of Arms source image with optional CK3 framing guides."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._guide_mode: str = "none"  # "none" | "grid" | "shield" | "circle"
        self._empty_text: str = "无源图片\n(当前为仅 TXT 条目)"
        self.setMinimumSize(220, 220)

    def set_image_path(self, path: Optional[Path]) -> None:
        if path and path.is_file():
            pm = QPixmap(str(path))
            self._pixmap = pm if not pm.isNull() else None
        else:
            self._pixmap = None
        self.update()

    def set_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        self._pixmap = pixmap
        self.update()

    def set_guide_mode(self, mode: str) -> None:
        self._guide_mode = mode
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        side = min(w, h) - 8
        if side <= 10:
            return
        square_rect = QRectF((w - side) / 2.0, (h - side) / 2.0, side, side)

        # Subtle checkerboard background inside the 1:1 square stage
        painter.save()
        clip_path = QPainterPath()
        clip_path.addRoundedRect(square_rect, 8, 8)
        painter.setClipPath(clip_path)

        tile = 14
        c1 = QColor("#14171D")
        c2 = QColor("#1A1E26")
        x0 = int(square_rect.left())
        y0 = int(square_rect.top())
        x1 = int(square_rect.right()) + 1
        y1 = int(square_rect.bottom()) + 1
        for iy, yy in enumerate(range(y0, y1, tile)):
            for ix, xx in enumerate(range(x0, x1, tile)):
                painter.fillRect(xx, yy, tile, tile, c1 if (ix + iy) % 2 == 0 else c2)

        if self._pixmap and not self._pixmap.isNull():
            pw = self._pixmap.width()
            ph = self._pixmap.height()
            scale = min(side / max(1, pw), side / max(1, ph))
            dw = pw * scale
            dh = ph * scale
            dx = square_rect.center().x() - dw / 2.0
            dy = square_rect.center().y() - dh / 2.0
            painter.drawPixmap(QRectF(dx, dy, dw, dh), self._pixmap, QRectF(0, 0, pw, ph))
        else:
            painter.setPen(QColor("#7D8596"))
            painter.drawText(square_rect, Qt.AlignmentFlag.AlignCenter, self._empty_text)

        # Draw CK3 guide overlay
        if self._pixmap and self._guide_mode != "none":
            self._draw_guide(painter, square_rect)

        painter.restore()

        # Square border frame
        painter.setPen(QPen(QColor("#2C323F"), 1.2))
        painter.drawRoundedRect(square_rect, 8, 8)

    def _draw_guide(self, painter: QPainter, r: QRectF) -> None:
        s = r.width()
        x = r.left()
        y = r.top()

        if self._guide_mode == "grid":
            pen = QPen(QColor(212, 175, 55, 130), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            for frac in (1 / 3, 2 / 3):
                painter.drawLine(QPointF(x + s * frac, y), QPointF(x + s * frac, y + s))
                painter.drawLine(QPointF(x, y + s * frac), QPointF(x + s, y + s * frac))
            return

        if self._guide_mode == "circle":
            margin = s * 0.08
            circle_rect = r.adjusted(margin, margin, -margin, -margin)
            outer = QPainterPath()
            outer.addRect(r)
            inner = QPainterPath()
            inner.addEllipse(circle_rect)
            painter.fillPath(outer.subtracted(inner), QColor(10, 12, 16, 110))
            painter.setPen(QPen(QColor(229, 193, 88, 200), 1.8, Qt.PenStyle.DashLine))
            painter.drawEllipse(circle_rect)
            return

        if self._guide_mode == "shield":
            # Classic heater shield silhouette approximation for CK3 CoA framing reference
            shield = QPainterPath()
            top_y = y + s * 0.08
            mid_y = y + s * 0.50
            bot_y = y + s * 0.92
            left_x = x + s * 0.14
            right_x = x + s * 0.86
            cx = x + s * 0.50

            shield.moveTo(left_x, top_y)
            shield.lineTo(right_x, top_y)
            shield.lineTo(right_x, mid_y)
            shield.quadTo(right_x, y + s * 0.78, cx, bot_y)
            shield.quadTo(left_x, y + s * 0.78, left_x, mid_y)
            shield.closeSubpath()

            outer = QPainterPath()
            outer.addRect(r)
            painter.fillPath(outer.subtracted(shield), QColor(10, 12, 16, 110))
            painter.setPen(QPen(QColor(229, 193, 88, 200), 1.8, Qt.PenStyle.DashLine))
            painter.drawPath(shield)
