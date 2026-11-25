"""Interactive Multi-CoA Heraldic Composite Builder Dialog."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.composer import (
    HERALDIC_TEMPLATES,
    CompositeStyle,
    HeraldicTemplate,
    SlotDefinition,
    SlotImageState,
    get_template_by_id,
    merge_coa_txt_scripts,
    render_heraldic_composite,
    slot_pixel_polygon,
)
from src.core.image_ops import save_square_image
from src.core.workspace import CoaEntry, read_txt_full
from src.ui.screenshot_overlay import ScreenshotOverlay
from src.ui.theme import pil_to_qpixmap


def _point_in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon check."""
    inside = False
    n = len(poly)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
            inside = not inside
        j = i
    return inside


class HeraldicComposerCanvas(QWidget):
    """Interactive 1:1 preview canvas supporting slot click selection, drag pan, and wheel zoom."""

    slot_selected = Signal(str)  # slot_id
    slot_panned = Signal(str, float, float)  # slot_id, delta_norm_x, delta_norm_y
    slot_zoomed = Signal(str, float)  # slot_id, zoom_multiplier
    slot_double_clicked = Signal(str)  # slot_id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(460, 460)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self._template: HeraldicTemplate = HERALDIC_TEMPLATES[0]
        self._style = CompositeStyle()
        self._active_slot_id: str = self._template.slots[0].slot_id
        self._show_slot_guides: bool = True

        self._dragging = False
        self._last_pos = QPoint()

    def update_state(
        self,
        pixmap: QPixmap,
        template: HeraldicTemplate,
        style: CompositeStyle,
        active_slot_id: str,
    ) -> None:
        self._pixmap = pixmap
        self._template = template
        self._style = style
        self._active_slot_id = active_slot_id
        self.update()

    def set_show_guides(self, show: bool) -> None:
        self._show_slot_guides = show
        self.update()

    def _stage_rect(self) -> QRectF:
        margin = 14
        side = max(20, min(self.width() - margin * 2, self.height() - margin * 2))
        x = (self.width() - side) / 2.0
        y = (self.height() - side) / 2.0
        return QRectF(x, y, side, side)

    def _hit_test_slot(self, pos: QPoint) -> Optional[SlotDefinition]:
        sr = self._stage_rect()
        if not sr.contains(pos):
            return None
        local_x = pos.x() - sr.left()
        local_y = pos.y() - sr.top()
        side = sr.width()

        # Check overlay slots in reverse order first (center escutcheon on top, then wedges)
        ordered = [s for s in reversed(self._template.slots) if s.is_overlay] + [
            s for s in self._template.slots if not s.is_overlay
        ]
        for slot in ordered:
            poly = slot_pixel_polygon(slot, self._style, int(side))
            if _point_in_poly(local_x, local_y, poly):
                return slot
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        hit = self._hit_test_slot(pos)
        if hit is not None:
            self._active_slot_id = hit.slot_id
            self.slot_selected.emit(hit.slot_id)
            self._dragging = True
            self._last_pos = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._dragging and self._active_slot_id:
            sr = self._stage_rect()
            slot = next(
                (s for s in self._template.slots if s.slot_id == self._active_slot_id),
                None,
            )
            if slot and sr.width() > 10:
                slot_w = max(20.0, (slot.bbox[2] - slot.bbox[0]) * sr.width())
                slot_h = max(20.0, (slot.bbox[3] - slot.bbox[1]) * sr.height())
                dx = (pos.x() - self._last_pos.x()) / slot_w
                dy = (pos.y() - self._last_pos.y()) / slot_h
                self._last_pos = pos
                self.slot_panned.emit(self._active_slot_id, dx, dy)
            return

        hit = self._hit_test_slot(pos)
        self.setCursor(
            Qt.CursorShape.OpenHandCursor if hit is not None else Qt.CursorShape.ArrowCursor
        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self._hit_test_slot(event.position().toPoint())
            if hit is not None:
                self.slot_double_clicked.emit(hit.slot_id)

    def wheelEvent(self, event: QWheelEvent) -> None:
        hit = self._hit_test_slot(event.position().toPoint())
        target_id = hit.slot_id if hit is not None else self._active_slot_id
        if not target_id:
            return
        if hit is not None and hit.slot_id != self._active_slot_id:
            self._active_slot_id = hit.slot_id
            self.slot_selected.emit(hit.slot_id)
        delta = event.angleDelta().y()
        factor = 1.08 if delta > 0 else (1.0 / 1.08)
        self.slot_zoomed.emit(target_id, factor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.fillRect(self.rect(), QColor("#0D0F13"))
        sr = self._stage_rect()
        if not self._pixmap.isNull():
            painter.drawPixmap(
                sr,
                self._pixmap,
                QRectF(0, 0, self._pixmap.width(), self._pixmap.height()),
            )

        # Highlight active slot outline and slot number badges
        if self._show_slot_guides:
            side = int(sr.width())
            for idx, slot in enumerate(self._template.slots, 1):
                poly = slot_pixel_polygon(slot, self._style, side)
                qpoly = QPolygonF([QPointF(sr.left() + px, sr.top() + py) for px, py in poly])

                if slot.slot_id == self._active_slot_id:
                    painter.setPen(QPen(QColor("#34D399"), 2.5, Qt.PenStyle.DashLine))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPolygon(qpoly)

                # Draw small number badge at slot centroid/bbox center
                cx = sr.left() + ((slot.bbox[0] + slot.bbox[2]) / 2.0) * side
                cy = sr.top() + ((slot.bbox[1] + slot.bbox[3]) / 2.0) * side
                # Offset q3/q4 badge slightly if center escutcheon overlaps
                if slot.slot_id in ("q1", "q2", "q3", "q4"):
                    cx = sr.left() + (0.22 if "1" in slot.slot_id or "3" in slot.slot_id else 0.78) * side
                    cy = sr.top() + (0.22 if "1" in slot.slot_id or "2" in slot.slot_id else 0.78) * side

                badge_r = QRectF(cx - 12, cy - 12, 24, 24)
                is_act = slot.slot_id == self._active_slot_id
                painter.setPen(
                    QPen(QColor("#34D399" if is_act else "#D9B45A"), 1.5)
                )
                painter.setBrush(QColor(15, 17, 21, 215))
                painter.drawEllipse(badge_r)
                painter.setPen(QColor("#6EE7B7" if is_act else "#F3DA91"))
                painter.drawText(badge_r, Qt.AlignmentFlag.AlignCenter, str(idx))

        painter.setPen(QPen(QColor("#2C323F"), 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sr)


class HeraldicComposerDialog(QDialog):
    """Multi-CoA Heraldic Composite Builder Studio."""

    def __init__(
        self,
        workspace_dir: Path,
        entries: list[CoaEntry],
        default_auto_convert: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🧩 多纹章拼接工坊（王室联统 / 四分 / 六合一 / 九区复合）— 十字军之王3纹章生成工坊")
        self.resize(1120, 760)

        self._workspace_dir = workspace_dir
        self._entries = [e for e in entries if e.has_image and e.image_path]
        self._all_entries = entries
        self._template: HeraldicTemplate = HERALDIC_TEMPLATES[0]
        self._style = CompositeStyle()
        self._slot_states: dict[str, SlotImageState] = {}
        self._active_slot_id: str = self._template.slots[0].slot_id

        self.saved_image_path: Optional[Path] = None
        self.saved_txt_path: Optional[Path] = None
        self.should_auto_convert: bool = False

        self._overlay = ScreenshotOverlay(self)
        self._overlay.captured.connect(self._on_slot_screenshot_captured)
        self._overlay.cancelled.connect(self._on_slot_screenshot_cancelled)

        self._init_slots_for_template()
        self._build_ui(default_auto_convert)
        self._refresh_slot_list()
        self._refresh_canvas()

    def _init_slots_for_template(self) -> None:
        for slot in self._template.slots:
            if slot.slot_id not in self._slot_states:
                self._slot_states[slot.slot_id] = SlotImageState(bg_color=slot.default_bg)
            else:
                self._slot_states[slot.slot_id].bg_color = slot.default_bg
        self._active_slot_id = self._template.slots[0].slot_id

    def _build_ui(self, default_auto_convert: bool) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # Left column: Interactive canvas + instructions
        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        tip_banner = QFrame(self)
        tip_banner.setObjectName("PairBanner")
        tbl = QVBoxLayout(tip_banner)
        tbl.setContentsMargins(12, 8, 12, 8)
        tip_lbl = QLabel(
            "💡 <b>傻瓜式拼接</b>：① 选右侧分格模板 → ② 点击画布上的 ①~⑨ 分区（或右侧槽位列表）选图填入 → "
            "③ 在画布上<b>按住鼠标拖动可平移</b>该区图案、<b>滚轮可缩放</b> → ④ 点右下角保存即自动转成 CK3 纹章！"
        )
        tip_lbl.setWordWrap(True)
        tip_lbl.setTextFormat(Qt.TextFormat.RichText)
        tip_lbl.setStyleSheet("color: #EAE6DF; font-size: 12px;")
        tbl.addWidget(tip_lbl)
        left_col.addWidget(tip_banner)

        self._canvas = HeraldicComposerCanvas(self)
        self._canvas.slot_selected.connect(self._on_canvas_slot_selected)
        self._canvas.slot_panned.connect(self._on_canvas_slot_panned)
        self._canvas.slot_zoomed.connect(self._on_canvas_slot_zoomed)
        self._canvas.slot_double_clicked.connect(self._on_canvas_slot_double_clicked)
        left_col.addWidget(self._canvas, 1)

        c_footer = QHBoxLayout()
        self._guide_chk = QCheckBox("在画布上显示槽位序号与选中绿框（导出时不会带入）")
        self._guide_chk.setChecked(True)
        self._guide_chk.toggled.connect(self._canvas.set_show_guides)
        demo_fill_btn = QPushButton("🎲 用图库图片一键自动填满示范")
        demo_fill_btn.clicked.connect(self._auto_fill_from_gallery)
        c_footer.addWidget(self._guide_chk)
        c_footer.addStretch()
        c_footer.addWidget(demo_fill_btn)
        left_col.addLayout(c_footer)

        root.addLayout(left_col, 3)

        # Right column: Controls panel
        panel = QFrame(self)
        panel.setObjectName("PanelCard")
        panel.setFixedWidth(475)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(8)

        # 1. Template selector
        pl.addWidget(self._sec_label("1. 选择历史复合纹章模板"))
        self._tpl_combo = QComboBox()
        for t in HERALDIC_TEMPLATES:
            self._tpl_combo.addItem(t.name, t.template_id)
        self._tpl_combo.currentIndexChanged.connect(self._on_template_changed)
        pl.addWidget(self._tpl_combo)

        self._tpl_sub_lbl = QLabel(self._template.subtitle)
        self._tpl_sub_lbl.setWordWrap(True)
        self._tpl_sub_lbl.setStyleSheet("color: #8E96A4; font-size: 11.5px;")
        pl.addWidget(self._tpl_sub_lbl)

        # 2. Slots list & per-slot image assignment
        pl.addWidget(self._sec_label("2. 点击分区槽位填入纹章图片"))
        self._slot_list = QListWidget()
        self._slot_list.setMinimumHeight(182)
        self._slot_list.setMaximumHeight(196)
        self._slot_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._slot_list.setStyleSheet(
            "QListWidget { background: #101318; border: 1px solid #282E3A; border-radius: 7px; padding: 3px; }"
            "QListWidget::item { padding: 4px 8px; border-radius: 5px; }"
            "QListWidget::item:selected { background: #262117; color: #F3DA91; font-weight: 700; border: 1px solid #D9B45A; }"
        )
        self._slot_list.currentRowChanged.connect(self._on_slot_row_changed)
        pl.addWidget(self._slot_list)

        # Quick pick from workspace gallery
        gal_row = QHBoxLayout()
        gal_row.setSpacing(6)
        gal_row.addWidget(QLabel("从图库选:"))
        self._gallery_combo = QComboBox()
        self._gallery_combo.addItem("— 点击选择工作区已有图片填入当前槽位 —", "")
        for e in self._entries:
            if e.image_path:
                self._gallery_combo.addItem(f"🖼 {e.image_path.name} ({e.image_width}×{e.image_height})", str(e.image_path))
        self._gallery_combo.currentIndexChanged.connect(self._on_gallery_picked)
        gal_row.addWidget(self._gallery_combo, 1)
        pl.addLayout(gal_row)

        slot_btn_row = QHBoxLayout()
        slot_btn_row.setSpacing(6)
        pick_file_btn = QPushButton("📂 导入外部图")
        pick_file_btn.clicked.connect(self._pick_external_for_slot)
        shot_slot_btn = QPushButton("📷 截图填入此格")
        shot_slot_btn.clicked.connect(self._screenshot_for_slot)
        bg_slot_btn = QPushButton("🎨 槽位底色")
        bg_slot_btn.clicked.connect(self._pick_slot_bg)
        clear_slot_btn = QPushButton("✕ 清空此格")
        clear_slot_btn.clicked.connect(self._clear_active_slot)
        for b in (pick_file_btn, shot_slot_btn, bg_slot_btn, clear_slot_btn):
            b.setStyleSheet("padding: 5px 8px; font-size: 11.5px;")
            slot_btn_row.addWidget(b)
        pl.addLayout(slot_btn_row)

        # Per-slot zoom & fit mode
        adj_row = QHBoxLayout()
        adj_row.setSpacing(6)
        adj_row.addWidget(QLabel("当前格缩放:"))
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(35, 260)
        self._zoom_slider.setValue(100)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        adj_row.addWidget(self._zoom_slider, 1)

        self._fit_combo = QComboBox()
        self._fit_combo.addItem("填满裁切", "cover")
        self._fit_combo.addItem("完整居中", "contain")
        self._fit_combo.currentIndexChanged.connect(self._on_fit_mode_changed)
        adj_row.addWidget(self._fit_combo)

        reset_pos_btn = QPushButton("居中重置")
        reset_pos_btn.setStyleSheet("padding: 5px 10px; font-size: 11.5px;")
        reset_pos_btn.clicked.connect(self._reset_active_slot_transform)
        adj_row.addWidget(reset_pos_btn)
        pl.addLayout(adj_row)

        # 3. Heraldic Borders & Center Escutcheon Style
        pl.addWidget(self._sec_label("3. 分界线与中央核心小盾样式"))
        style_row1 = QHBoxLayout()
        style_row1.setSpacing(8)
        style_row1.addWidget(QLabel("分界线粗细:"))
        self._bw_spin = QSpinBox()
        self._bw_spin.setRange(0, 20)
        self._bw_spin.setValue(self._style.border_width)
        self._bw_spin.valueChanged.connect(self._on_style_changed)
        style_row1.addWidget(self._bw_spin)

        border_col_btn = QPushButton("🎨 分界线颜色")
        border_col_btn.setStyleSheet("padding: 5px 10px;")
        border_col_btn.clicked.connect(self._pick_border_color)
        style_row1.addWidget(border_col_btn)
        style_row1.addStretch()
        pl.addLayout(style_row1)

        style_row2 = QHBoxLayout()
        style_row2.setSpacing(8)
        style_row2.addWidget(QLabel("中央小盾形状:"))
        self._esc_combo = QComboBox()
        self._esc_combo.addItem("经典盾形", "shield")
        self._esc_combo.addItem("皇家椭圆", "oval")
        self._esc_combo.addItem("正圆徽章", "circle")
        self._esc_combo.currentIndexChanged.connect(self._on_style_changed)
        style_row2.addWidget(self._esc_combo)

        ring_col_btn = QPushButton("🎨 小盾外环颜色")
        ring_col_btn.setStyleSheet("padding: 5px 10px;")
        ring_col_btn.clicked.connect(self._pick_ring_color)
        style_row2.addWidget(ring_col_btn)
        style_row2.addStretch()
        pl.addLayout(style_row2)

        self._outer_shield_chk = QCheckBox("外层套用古典盾形画布边框（默认不勾以满铺适配 CK3 游戏自带框）")
        self._outer_shield_chk.setChecked(False)
        self._outer_shield_chk.toggled.connect(self._on_style_changed)
        pl.addWidget(self._outer_shield_chk)

        # 4. Export & Native TXT Merge
        pl.addWidget(self._sec_label("4. 导出联合纹章与生成 TXT"))
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        out_row.addWidget(QLabel("文件名:"))
        self._name_edit = QLineEdit(f"united_coa_{time.strftime('%H%M%S')}")
        out_row.addWidget(self._name_edit, 1)

        out_row.addWidget(QLabel("尺寸:"))
        self._size_combo = QComboBox()
        self._size_combo.addItem("512×512 (推荐)", 512)
        self._size_combo.addItem("1024×1024", 1024)
        out_row.addWidget(self._size_combo)
        pl.addLayout(out_row)

        self._auto_conv_chk = QCheckBox("保存拼接图后立即调用转换器生成对应的 CK3 纹章 TXT")
        self._auto_conv_chk.setChecked(default_auto_convert)
        pl.addWidget(self._auto_conv_chk)

        pl.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        txt_merge_btn = QPushButton("📜 纯TXT坐标直拼")
        txt_merge_btn.setToolTip("不重新转图，直接把各槽位关联的已有 .txt 纹章代码按坐标缩放合并为一个 .txt")
        txt_merge_btn.clicked.connect(self._on_direct_txt_merge)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("💾 保存联合纹章")
        save_btn.setObjectName("PrimaryGoldBtn")
        save_btn.clicked.connect(self._on_save_composite)

        btn_row.addWidget(txt_merge_btn)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn, 1)
        pl.addLayout(btn_row)

        root.addWidget(panel)

    @staticmethod
    def _sec_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #E6C775; font-weight: 700; font-size: 12.5px; margin-top: 2px;")
        return lbl

    # ------------------------------------------------------------------ Slot & Template Sync
    def _on_template_changed(self) -> None:
        tpl_id = str(self._tpl_combo.currentData())
        self._template = get_template_by_id(tpl_id)
        self._tpl_sub_lbl.setText(self._template.subtitle)
        self._init_slots_for_template()
        self._refresh_slot_list()
        self._refresh_canvas()

    def _refresh_slot_list(self) -> None:
        self._slot_list.blockSignals(True)
        self._slot_list.clear()
        active_row = 0
        for idx, slot in enumerate(self._template.slots):
            st = self._slot_states.get(slot.slot_id)
            if st and st.image_path:
                status = f"✓ 已填入: {st.image_path.name}"
            elif st and st.pil_image is not None:
                status = "✓ 已填入: 屏幕截图"
            else:
                status = "○ 未填图（点击选择）"
            item = QListWidgetItem(f"{slot.label}   —   {status}")
            item.setData(Qt.ItemDataRole.UserRole, slot.slot_id)
            self._slot_list.addItem(item)
            if slot.slot_id == self._active_slot_id:
                active_row = idx
        self._slot_list.setCurrentRow(active_row)
        self._slot_list.blockSignals(False)
        self._sync_active_slot_controls()

    def _sync_active_slot_controls(self) -> None:
        st = self._slot_states.get(self._active_slot_id)
        if not st:
            return
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(round(st.zoom * 100))
        self._zoom_slider.blockSignals(False)

        self._fit_combo.blockSignals(True)
        idx = self._fit_combo.findData(st.fit_mode)
        if idx >= 0:
            self._fit_combo.setCurrentIndex(idx)
        self._fit_combo.blockSignals(False)

        self._gallery_combo.blockSignals(True)
        if st.image_path:
            gidx = self._gallery_combo.findData(str(st.image_path))
            self._gallery_combo.setCurrentIndex(max(0, gidx))
        else:
            self._gallery_combo.setCurrentIndex(0)
        self._gallery_combo.blockSignals(False)

    def _on_slot_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._template.slots):
            self._active_slot_id = self._template.slots[row].slot_id
            self._sync_active_slot_controls()
            self._refresh_canvas()

    def _on_canvas_slot_selected(self, slot_id: str) -> None:
        self._active_slot_id = slot_id
        for idx, slot in enumerate(self._template.slots):
            if slot.slot_id == slot_id:
                self._slot_list.blockSignals(True)
                self._slot_list.setCurrentRow(idx)
                self._slot_list.blockSignals(False)
                break
        self._sync_active_slot_controls()
        self._refresh_canvas()

    def _on_canvas_slot_panned(self, slot_id: str, dx: float, dy: float) -> None:
        st = self._slot_states.get(slot_id)
        if st:
            st.offset_x = max(-1.2, min(1.2, st.offset_x + dx))
            st.offset_y = max(-1.2, min(1.2, st.offset_y + dy))
            self._refresh_canvas()

    def _on_canvas_slot_zoomed(self, slot_id: str, factor: float) -> None:
        st = self._slot_states.get(slot_id)
        if st:
            st.zoom = max(0.35, min(2.6, st.zoom * factor))
            self._sync_active_slot_controls()
            self._refresh_canvas()

    def _on_canvas_slot_double_clicked(self, slot_id: str) -> None:
        self._on_canvas_slot_selected(slot_id)
        self._pick_external_for_slot()

    def _on_gallery_picked(self) -> None:
        path_str = str(self._gallery_combo.currentData() or "")
        if not path_str:
            return
        st = self._slot_states.setdefault(self._active_slot_id, SlotImageState())
        st.image_path = Path(path_str)
        st.pil_image = None
        st.zoom = 1.0
        st.offset_x = 0.0
        st.offset_y = 0.0
        self._refresh_slot_list()
        self._refresh_canvas()

    def _pick_external_for_slot(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "为当前纹章分区选择图片",
            str(self._workspace_dir),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            st = self._slot_states.setdefault(self._active_slot_id, SlotImageState())
            st.image_path = Path(path)
            st.pil_image = None
            st.zoom = 1.0
            st.offset_x = 0.0
            st.offset_y = 0.0
            self._refresh_slot_list()
            self._refresh_canvas()

    def _screenshot_for_slot(self) -> None:
        parent_win = self.parentWidget()
        if parent_win is not None:
            parent_win.setWindowOpacity(0.0)
        self.setWindowOpacity(0.0)
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()
        QTimer.singleShot(220, self._overlay.begin_capture)

    def _restore_windows_after_shot(self) -> None:
        parent_win = self.parentWidget()
        if parent_win is not None:
            parent_win.setWindowOpacity(1.0)
        self.setWindowOpacity(1.0)
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_slot_screenshot_cancelled(self) -> None:
        self._restore_windows_after_shot()

    def _on_slot_screenshot_captured(self, qimg) -> None:
        self._restore_windows_after_shot()
        from src.ui.main_window import qimage_to_pil

        st = self._slot_states.setdefault(self._active_slot_id, SlotImageState())
        st.pil_image = qimage_to_pil(qimg)
        st.image_path = None
        st.zoom = 1.0
        st.offset_x = 0.0
        st.offset_y = 0.0
        self._refresh_slot_list()
        self._refresh_canvas()

    def done(self, result: int) -> None:  # type: ignore[override]
        parent_win = self.parentWidget()
        if parent_win is not None and parent_win.windowOpacity() < 1.0:
            parent_win.setWindowOpacity(1.0)
        super().done(result)

    def _pick_slot_bg(self) -> None:
        st = self._slot_states.setdefault(self._active_slot_id, SlotImageState())
        col = QColorDialog.getColor(QColor(st.bg_color), self, "选择当前分区底色")
        if col.isValid():
            st.bg_color = col.name()
            self._refresh_canvas()

    def _clear_active_slot(self) -> None:
        slot = next((s for s in self._template.slots if s.slot_id == self._active_slot_id), None)
        self._slot_states[self._active_slot_id] = SlotImageState(
            bg_color=slot.default_bg if slot else "#1B2230"
        )
        self._refresh_slot_list()
        self._refresh_canvas()

    def _on_zoom_slider_changed(self, value: int) -> None:
        st = self._slot_states.get(self._active_slot_id)
        if st:
            st.zoom = value / 100.0
            self._refresh_canvas()

    def _on_fit_mode_changed(self) -> None:
        st = self._slot_states.get(self._active_slot_id)
        if st:
            st.fit_mode = str(self._fit_combo.currentData())
            self._refresh_canvas()

    def _reset_active_slot_transform(self) -> None:
        st = self._slot_states.get(self._active_slot_id)
        if st:
            st.zoom = 1.0
            st.offset_x = 0.0
            st.offset_y = 0.0
            self._sync_active_slot_controls()
            self._refresh_canvas()

    def _auto_fill_from_gallery(self) -> None:
        if not self._entries:
            QMessageBox.information(self, "提示", "当前工作目录暂无图片，请先导入或截图。")
            return
        for idx, slot in enumerate(self._template.slots):
            entry = self._entries[idx % len(self._entries)]
            st = self._slot_states.setdefault(slot.slot_id, SlotImageState(bg_color=slot.default_bg))
            st.image_path = entry.image_path
            st.pil_image = None
            st.zoom = 1.0
            st.offset_x = 0.0
            st.offset_y = 0.0
        self._refresh_slot_list()
        self._refresh_canvas()

    # ------------------------------------------------------------------ Style & Rendering
    def _on_style_changed(self) -> None:
        self._style.border_width = self._bw_spin.value()
        self._style.escutcheon_shape = str(self._esc_combo.currentData())
        self._style.outer_shield_frame = self._outer_shield_chk.isChecked()
        self._refresh_canvas()

    def _pick_border_color(self) -> None:
        col = QColorDialog.getColor(QColor(self._style.border_color), self, "选择分界线颜色")
        if col.isValid():
            self._style.border_color = col.name()
            self._refresh_canvas()

    def _pick_ring_color(self) -> None:
        col = QColorDialog.getColor(
            QColor(self._style.escutcheon_ring_color), self, "选择中央小盾外环颜色"
        )
        if col.isValid():
            self._style.escutcheon_ring_color = col.name()
            self._refresh_canvas()

    def _refresh_canvas(self) -> None:
        preview_pil = render_heraldic_composite(
            self._template,
            self._slot_states,
            self._style,
            output_size=512,
        )
        pm = pil_to_qpixmap(preview_pil)
        self._canvas.update_state(pm, self._template, self._style, self._active_slot_id)

    # ------------------------------------------------------------------ Save & TXT Merge
    def _on_save_composite(self) -> None:
        stem = self._name_edit.text().strip()
        if not stem:
            QMessageBox.warning(self, "提示", "请输入输出文件名。")
            return
        invalid = set('<>:"/\\|?*')
        if any(ch in invalid for ch in stem):
            QMessageBox.warning(self, "提示", '文件名不能包含 <>:"/\\|?* 等特殊字符。')
            return

        dest = self._workspace_dir / f"{stem}.png"
        if dest.exists():
            ans = QMessageBox.question(
                self,
                "文件已存在",
                f"{dest.name} 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        out_size = int(self._size_combo.currentData())
        final_img = render_heraldic_composite(
            self._template,
            self._slot_states,
            self._style,
            output_size=out_size,
        )
        save_square_image(final_img, dest, "png")
        self.saved_image_path = dest
        self.should_auto_convert = self._auto_conv_chk.isChecked()
        self.accept()

    def _on_direct_txt_merge(self) -> None:
        """Directly merge paired .txt CoA codes from assigned slots by coordinate transformation."""
        slot_scripts: list[tuple[str, tuple[float, float, float, float]]] = []
        for slot in self._template.slots:
            st = self._slot_states.get(slot.slot_id)
            if not st or not st.image_path:
                continue
            txt_candidate = st.image_path.with_suffix(".txt")
            if txt_candidate.is_file():
                slot_scripts.append((read_txt_full(txt_candidate), slot.bbox))

        if len(slot_scripts) < 2:
            QMessageBox.information(
                self,
                "提示",
                "「纯 TXT 坐标直拼」需要至少 2 个槽位所选的图片已有对应的 .txt 纹章文件。\n\n"
                "提示：直接点右下角金色的「💾 保存联合纹章」即可支持任意图片（含斜切/圆盾/鎏金边框）并自动转成 TXT！",
            )
            return

        stem = self._name_edit.text().strip() or f"united_coa_{time.strftime('%H%M%S')}"
        dest_img = self._workspace_dir / f"{stem}.png"
        dest_txt = self._workspace_dir / f"{stem}.txt"

        out_size = int(self._size_combo.currentData())
        final_img = render_heraldic_composite(
            self._template,
            self._slot_states,
            self._style,
            output_size=out_size,
        )
        save_square_image(final_img, dest_img, "png")

        merged_code = merge_coa_txt_scripts(slot_scripts, landed_title=False)
        dest_txt.write_text(merged_code, encoding="utf-8")

        self.saved_image_path = dest_img
        self.saved_txt_path = dest_txt
        self.should_auto_convert = False
        self.accept()
