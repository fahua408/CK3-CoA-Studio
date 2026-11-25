"""Built-in 1:1 square image editor (crop, pad, rotate/flip, enhance, export)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from src.core.image_ops import (
    SquareEditSpec,
    apply_enhancements,
    apply_geometry,
    apply_square_edit,
    default_centered_crop,
    load_oriented_rgba,
    save_square_image,
)
from src.ui.theme import pil_to_qpixmap


class SquareEditorCanvas(QWidget):
    """Interactive canvas supporting 1:1 crop box dragging/resizing and pad preview."""

    crop_changed = Signal(int, int, int)  # x, y, side in image pixels

    HANDLE_SIZE = 10

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(460, 460)
        self.setMouseTracking(True)

        self._pixmap = QPixmap()
        self._img_w = 1
        self._img_h = 1
        self._mode = "crop"  # "crop" | "pad"
        self._show_shield_guide = False

        # Crop box in image coordinates
        self._crop_x = 0
        self._crop_y = 0
        self._crop_side = 1

        # Display geometry cache
        self._disp_rect = QRectF()
        self._scale = 1.0

        # Drag state
        self._drag_mode = ""  # "" | "move" | "nw" | "ne" | "sw" | "se"
        self._drag_start_pos = QPoint()
        self._drag_orig_crop = (0, 0, 1)

    def set_preview(
        self,
        pixmap: QPixmap,
        mode: str,
        crop_x: int,
        crop_y: int,
        crop_side: int,
    ) -> None:
        self._pixmap = pixmap
        self._img_w = max(1, pixmap.width())
        self._img_h = max(1, pixmap.height())
        self._mode = mode
        self._crop_x = crop_x
        self._crop_y = crop_y
        self._crop_side = max(1, crop_side)
        self.update()

    def set_shield_guide(self, enabled: bool) -> None:
        self._show_shield_guide = enabled
        self.update()

    def _compute_display_rect(self) -> tuple[QRectF, float]:
        margin = 18
        avail_w = max(10, self.width() - margin * 2)
        avail_h = max(10, self.height() - margin * 2)
        scale = min(avail_w / self._img_w, avail_h / self._img_h)
        dw = self._img_w * scale
        dh = self._img_h * scale
        dx = (self.width() - dw) / 2.0
        dy = (self.height() - dh) / 2.0
        return QRectF(dx, dy, dw, dh), scale

    def _crop_widget_rect(self) -> QRectF:
        return QRectF(
            self._disp_rect.left() + self._crop_x * self._scale,
            self._disp_rect.top() + self._crop_y * self._scale,
            self._crop_side * self._scale,
            self._crop_side * self._scale,
        )

    def _corner_handles(self, r: QRectF) -> dict[str, QRectF]:
        hs = self.HANDLE_SIZE
        half = hs / 2.0
        return {
            "nw": QRectF(r.left() - half, r.top() - half, hs, hs),
            "ne": QRectF(r.right() - half, r.top() - half, hs, hs),
            "sw": QRectF(r.left() - half, r.bottom() - half, hs, hs),
            "se": QRectF(r.right() - half, r.bottom() - half, hs, hs),
        }

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._mode != "crop" or event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        cr = self._crop_widget_rect()
        for name, hr in self._corner_handles(cr).items():
            if hr.adjusted(-5, -5, 5, 5).contains(pos):
                self._drag_mode = name
                self._drag_start_pos = pos
                self._drag_orig_crop = (self._crop_x, self._crop_y, self._crop_side)
                return

        if cr.contains(pos):
            self._drag_mode = "move"
            self._drag_start_pos = pos
            self._drag_orig_crop = (self._crop_x, self._crop_y, self._crop_side)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._mode != "crop":
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        pos = event.position().toPoint()
        if not self._drag_mode:
            cr = self._crop_widget_rect()
            for name, hr in self._corner_handles(cr).items():
                if hr.adjusted(-5, -5, 5, 5).contains(pos):
                    self.setCursor(
                        Qt.CursorShape.SizeFDiagCursor
                        if name in ("nw", "se")
                        else Qt.CursorShape.SizeBDiagCursor
                    )
                    return
            self.setCursor(
                Qt.CursorShape.SizeAllCursor if cr.contains(pos) else Qt.CursorShape.ArrowCursor
            )
            return

        ox, oy, oside = self._drag_orig_crop
        dx_img = round((pos.x() - self._drag_start_pos.x()) / max(1e-6, self._scale))
        dy_img = round((pos.y() - self._drag_start_pos.y()) / max(1e-6, self._scale))
        min_side = min(24, self._img_w, self._img_h)

        if self._drag_mode == "move":
            nx = max(0, min(ox + dx_img, self._img_w - oside))
            ny = max(0, min(oy + dy_img, self._img_h - oside))
            self._crop_x, self._crop_y = nx, ny
        else:
            # Corner resize anchored at opposite corner, locked 1:1
            if self._drag_mode == "se":
                ax, ay = ox, oy
                new_side = max(oside + dx_img, oside + dy_img)
                max_side = min(self._img_w - ax, self._img_h - ay)
                side = max(min_side, min(new_side, max_side))
                self._crop_x, self._crop_y, self._crop_side = ax, ay, side
            elif self._drag_mode == "nw":
                ax, ay = ox + oside, oy + oside
                new_side = max(oside - dx_img, oside - dy_img)
                max_side = min(ax, ay)
                side = max(min_side, min(new_side, max_side))
                self._crop_x, self._crop_y, self._crop_side = ax - side, ay - side, side
            elif self._drag_mode == "ne":
                ax, ay = ox, oy + oside
                new_side = max(oside + dx_img, oside - dy_img)
                max_side = min(self._img_w - ax, ay)
                side = max(min_side, min(new_side, max_side))
                self._crop_x, self._crop_y, self._crop_side = ax, ay - side, side
            elif self._drag_mode == "sw":
                ax, ay = ox + oside, oy
                new_side = max(oside - dx_img, oside + dy_img)
                max_side = min(ax, self._img_h - ay)
                side = max(min_side, min(new_side, max_side))
                self._crop_x, self._crop_y, self._crop_side = ax - side, ay, side

        self.crop_changed.emit(self._crop_x, self._crop_y, self._crop_side)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_mode = ""

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor("#0D0F13"))
        if self._pixmap.isNull():
            return

        self._disp_rect, self._scale = self._compute_display_rect()

        # Draw checkerboard behind image
        tile = 12
        c1, c2 = QColor("#14171D"), QColor("#1A1E26")
        x0 = int(self._disp_rect.left())
        y0 = int(self._disp_rect.top())
        x1 = int(self._disp_rect.right()) + 1
        y1 = int(self._disp_rect.bottom()) + 1
        painter.save()
        painter.setClipRect(self._disp_rect)
        for iy, yy in enumerate(range(y0, y1, tile)):
            for ix, xx in enumerate(range(x0, x1, tile)):
                painter.fillRect(xx, yy, tile, tile, c1 if (ix + iy) % 2 == 0 else c2)
        painter.restore()

        painter.drawPixmap(
            self._disp_rect,
            self._pixmap,
            QRectF(0, 0, self._pixmap.width(), self._pixmap.height()),
        )

        if self._mode == "crop":
            cr = self._crop_widget_rect()
            outer = QPainterPath()
            outer.addRect(self._disp_rect)
            inner = QPainterPath()
            inner.addRect(cr)
            painter.fillPath(outer.subtracted(inner), QColor(8, 10, 14, 155))

            painter.setPen(QPen(QColor("#D9B45A"), 2))
            painter.drawRect(cr)

            # Handles
            painter.setPen(QPen(QColor("#0F1115"), 1))
            painter.setBrush(QColor("#E6C775"))
            for hr in self._corner_handles(cr).values():
                painter.drawRect(hr)

            guide_rect = cr
        else:
            guide_rect = self._disp_rect
            painter.setPen(QPen(QColor("#D9B45A"), 1.5))
            painter.drawRect(self._disp_rect)

        if self._show_shield_guide and guide_rect.width() > 30:
            self._draw_shield_outline(painter, guide_rect)

    @staticmethod
    def _draw_shield_outline(painter: QPainter, r: QRectF) -> None:
        s = r.width()
        x = r.left()
        y = r.top()
        shield = QPainterPath()
        shield.moveTo(x + s * 0.14, y + s * 0.08)
        shield.lineTo(x + s * 0.86, y + s * 0.08)
        shield.lineTo(x + s * 0.86, y + s * 0.50)
        shield.quadTo(x + s * 0.86, y + s * 0.78, x + s * 0.50, y + s * 0.92)
        shield.quadTo(x + s * 0.14, y + s * 0.78, x + s * 0.14, y + s * 0.50)
        shield.closeSubpath()
        painter.setPen(QPen(QColor(229, 193, 88, 185), 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shield)


class SquareImageEditorDialog(QDialog):
    """Full 1:1 square image editor modal returning saved file path and auto-convert flag."""

    def __init__(
        self,
        workspace_dir: Path,
        source_path: Optional[Path] = None,
        source_image: Optional[Image.Image] = None,
        suggested_stem: str = "",
        default_auto_convert: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("1:1 正方形图片编辑器 — CK3 纹章工坊")
        self.resize(980, 680)

        self._workspace_dir = workspace_dir
        self._source_path = source_path
        if source_image is not None:
            self._raw_rgba = source_image.convert("RGBA")
        elif source_path is not None:
            self._raw_rgba = load_oriented_rgba(source_path)
        else:
            raise ValueError("必须提供 source_path 或 source_image")

        self._spec = SquareEditSpec()
        self.saved_path: Optional[Path] = None
        self.should_auto_convert: bool = False

        self._init_crop_from_geometry()
        self._build_ui(suggested_stem, default_auto_convert)
        self._refresh_canvas()

    def _geo_image(self) -> Image.Image:
        return apply_geometry(
            self._raw_rgba,
            self._spec.rotate_steps,
            self._spec.flip_h,
            self._spec.flip_v,
        )

    def _init_crop_from_geometry(self) -> None:
        geo = self._geo_image()
        x, y, side = default_centered_crop(geo.width, geo.height)
        self._spec.crop_x = x
        self._spec.crop_y = y
        self._spec.crop_side = side

    def _build_ui(self, suggested_stem: str, default_auto_convert: bool) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(14)

        # Left: Canvas + info footer
        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        self._canvas = SquareEditorCanvas(self)
        self._canvas.crop_changed.connect(self._on_canvas_crop_changed)
        left_col.addWidget(self._canvas, 1)

        footer = QHBoxLayout()
        self._dim_label = QLabel()
        self._dim_label.setStyleSheet("color: #E6C775; font-weight: 600;")
        self._guide_chk = QCheckBox("叠加参考轮廓线")
        self._guide_chk.setChecked(False)
        self._guide_chk.toggled.connect(self._canvas.set_shield_guide)
        footer.addWidget(self._dim_label)
        footer.addStretch()
        footer.addWidget(self._guide_chk)
        left_col.addLayout(footer)
        layout.addLayout(left_col, 3)

        # Right: Controls panel
        panel = QFrame(self)
        panel.setObjectName("PanelCard")
        panel.setFixedWidth(340)
        p_layout = QVBoxLayout(panel)
        p_layout.setContentsMargins(14, 14, 14, 14)
        p_layout.setSpacing(10)

        # 1. Square mode
        p_layout.addWidget(self._section_label("1. 正方形构图模式（强制 1:1）"))
        mode_row = QHBoxLayout()
        self._crop_mode_btn = QPushButton("✂ 裁切 1:1")
        self._crop_mode_btn.setCheckable(True)
        self._crop_mode_btn.setProperty("filterChip", True)
        self._crop_mode_btn.setChecked(True)
        self._pad_mode_btn = QPushButton("⬜ 填充适配 1:1")
        self._pad_mode_btn.setCheckable(True)
        self._pad_mode_btn.setProperty("filterChip", True)
        self._crop_mode_btn.clicked.connect(lambda: self._set_mode("crop"))
        self._pad_mode_btn.clicked.connect(lambda: self._set_mode("pad"))
        mode_row.addWidget(self._crop_mode_btn)
        mode_row.addWidget(self._pad_mode_btn)
        p_layout.addLayout(mode_row)

        self._center_crop_btn = QPushButton("⌖ 居中最大正方形")
        self._center_crop_btn.clicked.connect(self._reset_centered_crop)
        p_layout.addWidget(self._center_crop_btn)

        self._pad_wrap = QWidget(panel)
        pad_l = QHBoxLayout(self._pad_wrap)
        pad_l.setContentsMargins(0, 0, 0, 0)
        pad_l.addWidget(QLabel("留白填充:"))
        self._pad_combo = QComboBox()
        self._pad_combo.addItem("自动取边缘主色", "edge")
        self._pad_combo.addItem("透明背景 (PNG)", "transparent")
        self._pad_combo.addItem("纯黑 (#000000)", "black")
        self._pad_combo.addItem("纯白 (#FFFFFF)", "white")
        self._pad_combo.addItem("自定义颜色...", "custom")
        self._pad_combo.currentIndexChanged.connect(self._on_pad_changed)
        pad_l.addWidget(self._pad_combo, 1)
        self._pad_wrap.hide()
        p_layout.addWidget(self._pad_wrap)

        # 2. Geometry
        p_layout.addWidget(self._section_label("2. 旋转与翻转"))
        geo_row = QHBoxLayout()
        geo_row.setSpacing(6)
        rot_l = QPushButton("↺ 左90°")
        rot_r = QPushButton("↻ 右90°")
        flp_h = QPushButton("⇄ 水平")
        flp_v = QPushButton("⇅ 垂直")
        rot_l.clicked.connect(lambda: self._rotate(-1))
        rot_r.clicked.connect(lambda: self._rotate(1))
        flp_h.clicked.connect(self._toggle_flip_h)
        flp_v.clicked.connect(self._toggle_flip_v)
        for b in (rot_l, rot_r, flp_h, flp_v):
            b.setStyleSheet("padding: 6px 6px; font-size: 12px;")
            geo_row.addWidget(b)
        p_layout.addLayout(geo_row)

        # 3. Enhancements
        p_layout.addWidget(self._section_label("3. 画质增强（提升纹章还原度）"))
        self._bri_slider, bri_row = self._make_slider("亮度", 50, 160, 100)
        self._con_slider, con_row = self._make_slider("对比度", 50, 180, 100)
        self._sat_slider, sat_row = self._make_slider("饱和度", 0, 180, 100)
        self._shp_slider, shp_row = self._make_slider("锐化", 0, 250, 100)
        for row in (bri_row, con_row, sat_row, shp_row):
            p_layout.addLayout(row)

        reset_enh_btn = QPushButton("↺ 重置调色参数")
        reset_enh_btn.clicked.connect(self._reset_enhancements)
        p_layout.addWidget(reset_enh_btn)

        # 4. Export
        p_layout.addWidget(self._section_label("4. 导出与保存"))
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("输出分辨率:"))
        self._size_combo = QComboBox()
        self._size_combo.addItem("保持当前边长", 0)
        self._size_combo.addItem("256 × 256", 256)
        self._size_combo.addItem("512 × 512 (推荐)", 512)
        self._size_combo.addItem("1024 × 1024", 1024)
        self._size_combo.currentIndexChanged.connect(self._on_export_size_changed)
        size_row.addWidget(self._size_combo, 1)
        p_layout.addLayout(size_row)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("图片格式:"))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItem("PNG (无损 / 支持透明)", "png")
        self._fmt_combo.addItem("JPG (体积更小)", "jpg")
        fmt_row.addWidget(self._fmt_combo, 1)
        p_layout.addLayout(fmt_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("文件名称:"))
        default_stem = suggested_stem or (
            self._source_path.stem
            if self._source_path
            else f"coa_{time.strftime('%Y%m%d_%H%M%S')}"
        )
        self._name_edit = QLineEdit(default_stem)
        name_row.addWidget(self._name_edit, 1)
        p_layout.addLayout(name_row)

        self._overwrite_chk = QCheckBox("直接覆盖原文件（不另存副本）")
        if self._source_path is None:
            self._overwrite_chk.setChecked(False)
            self._overwrite_chk.setEnabled(False)
        else:
            # Default overwrite if user is fixing a non-square existing image or re-editing
            self._overwrite_chk.setChecked(True)
            self._overwrite_chk.toggled.connect(self._on_overwrite_toggled)
        p_layout.addWidget(self._overwrite_chk)

        self._auto_convert_chk = QCheckBox("保存后立即生成对应的 CK3 纹章 TXT")
        self._auto_convert_chk.setChecked(default_auto_convert)
        p_layout.addWidget(self._auto_convert_chk)

        p_layout.addStretch()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("💾 保存 1:1 图片")
        save_btn.setObjectName("PrimaryGoldBtn")
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn, 1)
        p_layout.addLayout(btn_row)

        layout.addWidget(panel)

    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #E8C766; font-weight: 700; font-size: 12px; margin-top: 2px;")
        return lbl

    def _make_slider(self, name: str, lo: int, hi: int, val: int) -> tuple[QSlider, QHBoxLayout]:
        row = QHBoxLayout()
        lbl = QLabel(f"{name}:")
        lbl.setFixedWidth(54)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setValue(val)
        val_lbl = QLabel(f"{val}%")
        val_lbl.setFixedWidth(42)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def on_changed(v: int) -> None:
            val_lbl.setText(f"{v}%")
            self._sync_enhancements()

        slider.valueChanged.connect(on_changed)
        row.addWidget(lbl)
        row.addWidget(slider, 1)
        row.addWidget(val_lbl)
        return slider, row

    def _set_mode(self, mode: str) -> None:
        self._spec.mode = mode
        self._crop_mode_btn.setChecked(mode == "crop")
        self._pad_mode_btn.setChecked(mode == "pad")
        self._center_crop_btn.setVisible(mode == "crop")
        self._pad_wrap.setVisible(mode == "pad")
        self._refresh_canvas()

    def _on_pad_changed(self) -> None:
        choice = self._pad_combo.currentData()
        if choice == "custom":
            color = QColorDialog.getColor(
                QColor(*self._spec.pad_custom_rgb),
                self,
                "选择正方形留白填充色",
            )
            if color.isValid():
                self._spec.pad_custom_rgb = (color.red(), color.green(), color.blue())
        self._spec.pad_bg = choice
        self._refresh_canvas()

    def _rotate(self, delta: int) -> None:
        self._spec.rotate_steps = (self._spec.rotate_steps + delta) % 4
        self._init_crop_from_geometry()
        self._refresh_canvas()

    def _toggle_flip_h(self) -> None:
        self._spec.flip_h = not self._spec.flip_h
        self._init_crop_from_geometry()
        self._refresh_canvas()

    def _toggle_flip_v(self) -> None:
        self._spec.flip_v = not self._spec.flip_v
        self._init_crop_from_geometry()
        self._refresh_canvas()

    def _reset_centered_crop(self) -> None:
        self._init_crop_from_geometry()
        self._refresh_canvas()

    def _sync_enhancements(self) -> None:
        self._spec.brightness = self._bri_slider.value() / 100.0
        self._spec.contrast = self._con_slider.value() / 100.0
        self._spec.saturation = self._sat_slider.value() / 100.0
        self._spec.sharpness = self._shp_slider.value() / 100.0
        self._refresh_canvas()

    def _reset_enhancements(self) -> None:
        for s in (self._bri_slider, self._con_slider, self._sat_slider, self._shp_slider):
            s.blockSignals(True)
            s.setValue(100)
            s.blockSignals(False)
        self._spec.brightness = 1.0
        self._spec.contrast = 1.0
        self._spec.saturation = 1.0
        self._spec.sharpness = 1.0
        # Trigger label refresh cleanly
        for s in (self._bri_slider, self._con_slider, self._sat_slider, self._shp_slider):
            s.valueChanged.emit(100)

    def _on_export_size_changed(self) -> None:
        self._spec.target_size = int(self._size_combo.currentData())
        self._update_dim_label()

    def _on_overwrite_toggled(self, checked: bool) -> None:
        if self._source_path:
            if checked:
                self._name_edit.setText(self._source_path.stem)
            elif self._name_edit.text().strip() == self._source_path.stem:
                self._name_edit.setText(f"{self._source_path.stem}_sq")

    def _on_canvas_crop_changed(self, x: int, y: int, side: int) -> None:
        self._spec.crop_x = x
        self._spec.crop_y = y
        self._spec.crop_side = side
        self._update_dim_label()

    def _refresh_canvas(self) -> None:
        geo = self._geo_image()
        if self._spec.mode == "pad":
            pad_spec = SquareEditSpec(**{**self._spec.__dict__, "target_size": 0})
            preview_img = apply_square_edit(self._raw_rgba, pad_spec)
        else:
            preview_img = apply_enhancements(geo, self._spec)

        pm = pil_to_qpixmap(preview_img)
        self._canvas.set_preview(
            pm,
            self._spec.mode,
            self._spec.crop_x,
            self._spec.crop_y,
            self._spec.crop_side,
        )
        self._update_dim_label(geo.width, geo.height)

    def _update_dim_label(self, geo_w: Optional[int] = None, geo_h: Optional[int] = None) -> None:
        if geo_w is None or geo_h is None:
            geo = self._geo_image()
            geo_w, geo_h = geo.width, geo.height
        native_side = (
            self._spec.crop_side if self._spec.mode == "crop" else max(geo_w, geo_h)
        )
        out_side = self._spec.target_size if self._spec.target_size > 0 else native_side
        self._dim_label.setText(
            f"原图: {geo_w}×{geo_h}  |  当前 1:1 输出尺寸: {out_side} × {out_side} px"
        )

    def _on_save(self) -> None:
        stem = self._name_edit.text().strip()
        if not stem:
            QMessageBox.warning(self, "提示", "请输入有效的输出文件名。")
            return
        invalid = set('<>:"/\\|?*')
        if any(ch in invalid for ch in stem):
            QMessageBox.warning(self, "提示", '文件名不能包含 <>:"/\\|?* 等特殊字符。')
            return

        fmt = self._fmt_combo.currentData()
        if self._source_path and self._overwrite_chk.isChecked():
            dest = self._source_path.with_stem(stem).with_suffix(f".{fmt}")
            # If format changed while overwriting, remove old image cleanly after saving
            remove_old = dest != self._source_path
        else:
            dest = self._workspace_dir / f"{stem}.{fmt}"
            remove_old = False
            if dest.exists():
                ans = QMessageBox.question(
                    self,
                    "文件已存在",
                    f"{dest.name} 已存在，是否覆盖？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans != QMessageBox.StandardButton.Yes:
                    return

        result = apply_square_edit(self._raw_rgba, self._spec)
        save_square_image(result, dest, fmt)
        if remove_old and self._source_path and self._source_path.exists():
            self._source_path.unlink()

        self.saved_path = dest
        self.should_auto_convert = self._auto_convert_chk.isChecked()
        self.accept()
