"""Fullscreen 1:1 locked square screenshot overlay with magnifier and handle resize."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QPushButton, QWidget


class ScreenshotOverlay(QWidget):
    """Fullscreen overlay enforcing strict 1:1 square region capture."""

    captured = Signal(QImage)
    cancelled = Signal()

    HANDLE_SIZE = 8

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._bg_pixmap = QPixmap()
        self._screen_geo = QRect()
        self._dpr = 1.0

        self._selection = QRect()
        self._state = "idle"  # "idle" | "creating" | "moving" | "resizing"
        self._anchor = QPoint()
        self._move_offset = QPoint()
        self._resize_handle = ""
        self._resize_origin_rect = QRect()
        self._cursor_pos = QPoint()

        # Floating confirm/cancel buttons anchored near selection
        self._confirm_btn = QPushButton("✓ 确认 (Enter)", self)
        self._confirm_btn.setStyleSheet(
            "QPushButton { background: #C99E32; color: #121418; border: 1px solid #F0CB69; "
            "border-radius: 6px; padding: 5px 12px; font-weight: 700; font-size: 12px; }"
            "QPushButton:hover { background: #E3BC54; }"
        )
        self._confirm_btn.clicked.connect(self._accept_capture)
        self._confirm_btn.hide()

        self._cancel_btn = QPushButton("✕ 取消 (Esc)", self)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background: #232732; color: #EAE4D7; border: 1px solid #4A5366; "
            "border-radius: 6px; padding: 5px 10px; font-size: 12px; }"
            "QPushButton:hover { background: #323846; }"
        )
        self._cancel_btn.clicked.connect(self._cancel_capture)
        self._cancel_btn.hide()

    def begin_capture(self) -> None:
        """Grab the current screen under cursor and show fullscreen overlay."""
        cursor = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        if screen is None:
            self.cancelled.emit()
            return

        self._screen_geo = screen.geometry()
        self._bg_pixmap = screen.grabWindow(0)
        self._dpr = self._bg_pixmap.devicePixelRatio() or 1.0

        self._selection = QRect()
        self._state = "idle"
        self._confirm_btn.hide()
        self._cancel_btn.hide()

        self.setGeometry(self._screen_geo)
        self.showFullScreen()
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self._cursor_pos = self.mapFromGlobal(QCursor.pos())
        self.update()

    def _square_from_anchor(self, anchor: QPoint, current: QPoint) -> QRect:
        dx = current.x() - anchor.x()
        dy = current.y() - anchor.y()
        side = max(abs(dx), abs(dy))

        max_x = (self.width() - anchor.x()) if dx >= 0 else anchor.x()
        max_y = (self.height() - anchor.y()) if dy >= 0 else anchor.y()
        side = min(side, max_x, max_y)
        if side < 1:
            return QRect()

        x = anchor.x() if dx >= 0 else anchor.x() - side
        y = anchor.y() if dy >= 0 else anchor.y() - side
        return QRect(x, y, side, side)

    def _handle_rects(self, r: QRect) -> dict[str, QRect]:
        hs = self.HANDLE_SIZE
        half = hs // 2
        cx = r.center().x()
        cy = r.center().y()
        return {
            "nw": QRect(r.left() - half, r.top() - half, hs, hs),
            "n": QRect(cx - half, r.top() - half, hs, hs),
            "ne": QRect(r.right() - half, r.top() - half, hs, hs),
            "e": QRect(r.right() - half, cy - half, hs, hs),
            "se": QRect(r.right() - half, r.bottom() - half, hs, hs),
            "s": QRect(cx - half, r.bottom() - half, hs, hs),
            "sw": QRect(r.left() - half, r.bottom() - half, hs, hs),
            "w": QRect(r.left() - half, cy - half, hs, hs),
        }

    def _hit_handle(self, pos: QPoint) -> str:
        if self._selection.isNull():
            return ""
        for name, rect in self._handle_rects(self._selection).items():
            if rect.adjusted(-4, -4, 4, 4).contains(pos):
                return name
        return ""

    def _update_cursor_shape(self, pos: QPoint) -> None:
        handle = self._hit_handle(pos)
        if handle in ("nw", "se"):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif handle in ("ne", "sw"):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif handle in ("n", "s"):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif handle in ("e", "w"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif not self._selection.isNull() and self._selection.contains(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def _position_action_bar(self) -> None:
        if self._selection.isNull() or self._selection.width() < 10:
            self._confirm_btn.hide()
            self._cancel_btn.hide()
            return

        self._confirm_btn.adjustSize()
        self._cancel_btn.adjustSize()
        gap = 8
        total_w = self._confirm_btn.width() + gap + self._cancel_btn.width()
        x = min(max(8, self._selection.right() - total_w + 1), self.width() - total_w - 8)
        y = self._selection.bottom() + 10
        if y + self._confirm_btn.height() + 8 > self.height():
            y = max(8, self._selection.top() - self._confirm_btn.height() - 10)

        self._cancel_btn.move(x, y)
        self._confirm_btn.move(x + self._cancel_btn.width() + gap, y)
        self._cancel_btn.show()
        self._confirm_btn.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        self._cursor_pos = pos
        if event.button() == Qt.MouseButton.RightButton:
            if not self._selection.isNull():
                self._selection = QRect()
                self._state = "idle"
                self._confirm_btn.hide()
                self._cancel_btn.hide()
                self.update()
            else:
                self._cancel_capture()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        handle = self._hit_handle(pos)
        if handle:
            self._state = "resizing"
            self._resize_handle = handle
            self._resize_origin_rect = QRect(self._selection)
            self._anchor = pos
            self._confirm_btn.hide()
            self._cancel_btn.hide()
            return

        if not self._selection.isNull() and self._selection.contains(pos):
            self._state = "moving"
            self._move_offset = pos - self._selection.topLeft()
            self._confirm_btn.hide()
            self._cancel_btn.hide()
            return

        self._state = "creating"
        self._anchor = pos
        self._selection = QRect()
        self._confirm_btn.hide()
        self._cancel_btn.hide()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        pos.setX(max(0, min(pos.x(), self.width())))
        pos.setY(max(0, min(pos.y(), self.height())))
        self._cursor_pos = pos

        if self._state == "creating":
            self._selection = self._square_from_anchor(self._anchor, pos)
            self.update()
            return

        if self._state == "moving":
            side = self._selection.width()
            nx = max(0, min(pos.x() - self._move_offset.x(), self.width() - side))
            ny = max(0, min(pos.y() - self._move_offset.y(), self.height() - side))
            self._selection = QRect(nx, ny, side, side)
            self.update()
            return

        if self._state == "resizing":
            self._selection = self._resize_square(self._resize_origin_rect, self._resize_handle, pos)
            self.update()
            return

        self._update_cursor_shape(pos)
        self.update()

    def _resize_square(self, orig: QRect, handle: str, pos: QPoint) -> QRect:
        """Resize selection while strictly preserving 1:1 square proportions."""
        # Anchor opposite corner/edge depending on handle
        if handle == "nw":
            anchor = QPoint(orig.right() + 1, orig.bottom() + 1)
            return self._square_from_anchor(anchor, pos) or orig
        if handle == "ne":
            anchor = QPoint(orig.left(), orig.bottom() + 1)
            return self._square_from_anchor(anchor, pos) or orig
        if handle == "sw":
            anchor = QPoint(orig.right() + 1, orig.top())
            return self._square_from_anchor(anchor, pos) or orig
        if handle == "se":
            anchor = QPoint(orig.left(), orig.top())
            return self._square_from_anchor(anchor, pos) or orig

        # Edge handles expand/shrink around center or opposite edge
        if handle == "e":
            side = max(12, pos.x() - orig.left())
            side = min(side, self.width() - orig.left(), self.height() - orig.top())
            return QRect(orig.left(), orig.top(), side, side)
        if handle == "s":
            side = max(12, pos.y() - orig.top())
            side = min(side, self.width() - orig.left(), self.height() - orig.top())
            return QRect(orig.left(), orig.top(), side, side)
        if handle == "w":
            right = orig.right() + 1
            side = max(12, right - pos.x())
            side = min(side, right, self.height() - orig.top())
            return QRect(right - side, orig.top(), side, side)
        if handle == "n":
            bottom = orig.bottom() + 1
            side = max(12, bottom - pos.y())
            side = min(side, bottom, self.width() - orig.left())
            return QRect(orig.left(), bottom - side, side, side)
        return orig

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._state != "idle":
            self._state = "idle"
            if not self._selection.isNull() and self._selection.width() < 12:
                self._selection = QRect()
            self._position_action_bar()
            self._update_cursor_shape(event.position().toPoint())
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._selection.isNull()
            and self._selection.contains(event.position().toPoint())
        ):
            self._accept_capture()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._cancel_capture()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._selection.isNull() and self._selection.width() >= 12:
                self._accept_capture()
            return

        if not self._selection.isNull():
            step = 10 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else 1
            dx, dy = 0, 0
            if key == Qt.Key.Key_Left:
                dx = -step
            elif key == Qt.Key.Key_Right:
                dx = step
            elif key == Qt.Key.Key_Up:
                dy = -step
            elif key == Qt.Key.Key_Down:
                dy = step
            if dx or dy:
                side = self._selection.width()
                nx = max(0, min(self._selection.left() + dx, self.width() - side))
                ny = max(0, min(self._selection.top() + dy, self.height() - side))
                self._selection = QRect(nx, ny, side, side)
                self._position_action_bar()
                self.update()

    def _accept_capture(self) -> None:
        if self._selection.isNull() or self._selection.width() < 8:
            return
        scale_x = self._bg_pixmap.width() / max(1, self.width())
        scale_y = self._bg_pixmap.height() / max(1, self.height())
        px_x = max(0, round(self._selection.x() * scale_x))
        px_y = max(0, round(self._selection.y() * scale_y))
        px_side = max(1, round(self._selection.width() * min(scale_x, scale_y)))

        # Clamp strictly inside physical bitmap while guaranteeing 1:1 square
        max_side = min(self._bg_pixmap.width() - px_x, self._bg_pixmap.height() - px_y)
        px_side = min(px_side, max_side)

        cropped = self._bg_pixmap.copy(px_x, px_y, px_side, px_side).toImage()
        cropped.setDevicePixelRatio(1.0)
        self.hide()
        self.captured.emit(cropped)

    def _cancel_capture(self) -> None:
        self.hide()
        self.cancelled.emit()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        if self._bg_pixmap.isNull():
            return
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._bg_pixmap)

        # Dimmed mask outside selection
        outer = QPainterPath()
        outer.addRect(self.rect())
        if not self._selection.isNull():
            inner = QPainterPath()
            inner.addRect(self._selection)
            painter.fillPath(outer.subtracted(inner), QColor(8, 10, 14, 150))
        else:
            painter.fillPath(outer, QColor(8, 10, 14, 130))

        # Top instruction banner
        tip = "📷 1:1 正方形截图 · 拖拽框选（自动锁定正方形） · 方向键微调 · Enter/双击确认 · Esc取消"
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(tip) + 28
        tip_rect = QRect((self.width() - tw) // 2, 16, tw, 32)
        painter.setPen(QPen(QColor("#D4AF37"), 1))
        painter.setBrush(QColor(20, 22, 27, 225))
        painter.drawRoundedRect(tip_rect, 16, 16)
        painter.setPen(QColor("#F3EDE0"))
        painter.drawText(tip_rect, Qt.AlignmentFlag.AlignCenter, tip)

        if not self._selection.isNull():
            r = self._selection
            # Golden square border
            painter.setPen(QPen(QColor("#E8C766"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

            # Subtle rule-of-thirds inside selection
            if r.width() >= 48:
                painter.setPen(QPen(QColor(232, 199, 102, 95), 1, Qt.PenStyle.DashLine))
                for f in (1 / 3, 2 / 3):
                    painter.drawLine(
                        round(r.left() + r.width() * f),
                        r.top(),
                        round(r.left() + r.width() * f),
                        r.bottom(),
                    )
                    painter.drawLine(
                        r.left(),
                        round(r.top() + r.height() * f),
                        r.right(),
                        round(r.top() + r.height() * f),
                    )

            # 8 resize handles
            painter.setPen(QPen(QColor("#14161B"), 1))
            painter.setBrush(QColor("#E8C766"))
            for hrect in self._handle_rects(r).values():
                painter.drawRect(hrect)

            # Dimension badge (physical pixels)
            scale = self._bg_pixmap.width() / max(1, self.width())
            px_side = round(r.width() * scale)
            dim_text = f"1:1 正方形  {px_side} × {px_side} px"
            dw = fm.horizontalAdvance(dim_text) + 18
            dx = r.left()
            dy = r.top() - 28 if r.top() >= 34 else r.top() + 8
            dim_rect = QRect(dx, dy, dw, 22)
            painter.setPen(QPen(QColor("#D4AF37"), 1))
            painter.setBrush(QColor(18, 20, 25, 230))
            painter.drawRoundedRect(dim_rect, 6, 6)
            painter.setPen(QColor("#F6DF93"))
            painter.drawText(dim_rect, Qt.AlignmentFlag.AlignCenter, dim_text)

        # Live 3x Magnifier Loupe while idle or dragging
        if self._state in ("idle", "creating", "resizing") and not self._cursor_pos.isNull():
            self._draw_magnifier(painter, self._cursor_pos)

    def _draw_magnifier(self, painter: QPainter, pos: QPoint) -> None:
        loupe_size = 112
        offset = 20
        lx = pos.x() + offset
        ly = pos.y() + offset
        if lx + loupe_size + 10 > self.width():
            lx = pos.x() - offset - loupe_size
        if ly + loupe_size + 10 > self.height():
            ly = pos.y() - offset - loupe_size

        scale_x = self._bg_pixmap.width() / max(1, self.width())
        scale_y = self._bg_pixmap.height() / max(1, self.height())
        src_half = 18
        cx = round(pos.x() * scale_x)
        cy = round(pos.y() * scale_y)
        src_rect = QRect(
            max(0, cx - src_half),
            max(0, cy - src_half),
            src_half * 2,
            src_half * 2,
        )
        zoomed = self._bg_pixmap.copy(src_rect)
        target = QRect(lx, ly, loupe_size, loupe_size)

        painter.save()
        clip = QPainterPath()
        clip.addRoundedRect(target, 10, 10)
        painter.setClipPath(clip)
        painter.drawPixmap(target, zoomed)
        # Crosshair
        painter.setPen(QPen(QColor(212, 175, 55, 190), 1))
        painter.drawLine(target.center().x(), target.top(), target.center().x(), target.bottom())
        painter.drawLine(target.left(), target.center().y(), target.right(), target.center().y())
        painter.restore()

        painter.setPen(QPen(QColor("#D4AF37"), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(target, 10, 10)
