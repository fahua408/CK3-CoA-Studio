"""Main Studio window for CK3 CoA Studio."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from src import APP_TITLE, __version__
from src.core.config import AppConfig, discover_converter
from src.core.converter import COLOR_MODES, ConvertParams, ConverterRunner
from src.core.image_ops import save_square_image
from src.core.txt_renderer import render_coa_txt_file
from src.core.workspace import (
    IMAGE_EXTENSIONS,
    CoaEntry,
    move_to_recycle_bin,
    read_txt_full,
    rename_entry,
    scan_workspace,
)
from src.ui.coa_card import CoaCardWidget
from src.ui.composer_dialog import HeraldicComposerDialog
from src.ui.historical_library_dialog import HistoricalLibraryDialog
from src.ui.image_editor import SquareImageEditorDialog
from src.ui.preview_widget import CoaPreviewWidget
from src.ui.screenshot_overlay import ScreenshotOverlay
from src.ui.settings_dialog import SettingsDialog
from src.ui.theme import pil_to_qpixmap
from src.ui.tutorial_dialog import TutorialDialog
from src.ui.txt_to_image_dialog import TxtToImageDialog


def qimage_to_pil(qimg: QImage) -> Image.Image:
    """Convert QImage cleanly into a PIL RGBA Image."""
    rgba = qimg.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = rgba.constBits()
    return Image.frombuffer(
        "RGBA",
        (rgba.width(), rgba.height()),
        bytes(ptr),
        "raw",
        "RGBA",
        0,
        1,
    ).copy()


class GalleryScrollArea(QScrollArea):
    """ScrollArea that notifies parent when width changes so card columns reflow."""

    def __init__(self, on_resize_cb, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._on_resize_cb = on_resize_cb
        self._last_cols = 0

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        avail = max(220, self.viewport().width() - 16)
        cols = max(1, avail // (CoaCardWidget.CARD_WIDTH + 12))
        if cols != self._last_cols:
            self._last_cols = cols
            self._on_resize_cb()


class MainWindow(QMainWindow):
    """Primary desktop window integrating asset gallery, 1:1 editor, screenshot, and converter."""

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self._config = config
        self._entries: list[CoaEntry] = []
        self._filtered_entries: list[CoaEntry] = []
        self._cards: dict[str, CoaCardWidget] = {}
        self._thumb_cache: dict[str, QPixmap] = {}
        self._selected_id: str = ""
        self._active_filter: str = "all"

        self._runner = ConverterRunner(self)
        self._runner.started_job.connect(self._on_convert_started)
        self._runner.finished_job.connect(self._on_convert_finished)
        self._batch_queue: list[CoaEntry] = []

        self._overlay = ScreenshotOverlay()
        self._overlay.captured.connect(self._on_screenshot_captured)
        self._overlay.cancelled.connect(self._on_screenshot_cancelled)

        self.setWindowTitle(f"{APP_TITLE} v{__version__}")
        self.resize(1340, 840)
        self.setMinimumSize(1040, 680)
        self.setAcceptDrops(True)

        self._build_ui()
        self._bind_shortcuts()
        self.reload_workspace()

    # ------------------------------------------------------------------ UI Build
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        main_vbox = QVBoxLayout(central)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # Top Bar
        topbar = QFrame(self)
        topbar.setObjectName("TopBar")
        tb_l = QHBoxLayout(topbar)
        tb_l.setContentsMargins(12, 9, 12, 9)
        tb_l.setSpacing(7)

        brand = QLabel(f"🛡 {APP_TITLE}")
        brand.setStyleSheet("font-size: 15px; font-weight: 800; color: #E6C775;")
        brand.setMinimumWidth(198)
        tb_l.addWidget(brand)

        self._ws_label = QLabel()
        self._ws_label.setMaximumWidth(155)
        self._ws_label.setStyleSheet(
            "background: #101318; border: 1px solid #282E3A; border-radius: 7px; "
            "padding: 5px 8px; color: #B6BFC9;"
        )
        tb_l.addWidget(self._ws_label)

        switch_ws_btn = QPushButton("📂 切换目录")
        switch_ws_btn.clicked.connect(self._choose_workspace)
        tb_l.addWidget(switch_ws_btn)

        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self.reload_workspace)
        tb_l.addWidget(refresh_btn)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍 搜索...")
        self._search_edit.setMinimumWidth(110)
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter_and_render)
        tb_l.addWidget(self._search_edit, 1)

        shot_btn = QPushButton("📷 正方形截图")
        shot_btn.setObjectName("PrimaryGoldBtn")
        shot_btn.setToolTip("截取屏幕任意区域并强制锁定 1:1 正方形 (Ctrl+Shift+A)")
        shot_btn.clicked.connect(self.start_screenshot)
        tb_l.addWidget(shot_btn)

        compose_btn = QPushButton("🧩 多纹章拼接")
        compose_btn.setToolTip("将多个纹章拼接为西班牙六合一、汉诺威三分、帝国九区、四分+中央小盾等复合纹章")
        compose_btn.setStyleSheet(
            "QPushButton { background: #19322A; border: 1px solid #2D6A54; color: #A7F3D0; font-weight: 700; }"
            "QPushButton:hover { background: #214539; border-color: #3E8E72; }"
        )
        compose_btn.clicked.connect(self.open_composer)
        tb_l.addWidget(compose_btn)

        hist_btn = QPushButton("👑 欧洲名章库")
        hist_btn.setToolTip("内置 14 款欧洲著名历史王朝/帝国纹章（拜占庭、神罗、英格兰金雀花、法兰西波旁、西班牙六合一、耶路撒冷等）")
        hist_btn.setStyleSheet(
            "QPushButton { background: #2A1D24; border: 1px solid #7C3AED; color: #E9D5FF; font-weight: 700; }"
            "QPushButton:hover { background: #372530; border-color: #9333EA; }"
        )
        hist_btn.clicked.connect(self.open_historical_library)
        tb_l.addWidget(hist_btn)

        import_btn = QPushButton("🖼 导入图片")
        import_btn.clicked.connect(self._import_images)
        tb_l.addWidget(import_btn)

        self._batch_btn = QPushButton("⚡ 批量转换")
        self._batch_btn.setToolTip("一键批量将所有尚未生成 TXT 的图片转换为纹章代码")
        self._batch_btn.clicked.connect(self._start_batch_convert)
        tb_l.addWidget(self._batch_btn)

        tutorial_btn = QPushButton("📖 新手教程")
        tutorial_btn.setToolTip("3 步把图片（如卡皮巴拉）放进 CK3 变成纹章的实机图文教程")
        tutorial_btn.setStyleSheet(
            "QPushButton { background: #262117; border: 1px solid #8A6D24; color: #F3DA91; font-weight: 700; }"
            "QPushButton:hover { background: #332C1D; border-color: #D9B45A; }"
        )
        tutorial_btn.clicked.connect(self.open_tutorial)
        tb_l.addWidget(tutorial_btn)

        settings_btn = QPushButton("⚙ 设置")
        settings_btn.clicked.connect(self._open_settings)
        tb_l.addWidget(settings_btn)

        main_vbox.addWidget(topbar)

        # Splitter: Left Gallery + Right Detail Studio
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(2)
        splitter.setStyleSheet("QSplitter::handle { background: #20242E; }")

        # Left Panel
        left_widget = QWidget(splitter)
        left_l = QVBoxLayout(left_widget)
        left_l.setContentsMargins(12, 12, 8, 12)
        left_l.setSpacing(10)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)
        self._filter_btns: dict[str, QPushButton] = {}
        for key, label in (
            ("all", "全部"),
            ("paired", "✓ 已关联TXT"),
            ("pending", "○ 待生成"),
            ("txt_only", "📄 仅TXT"),
            ("non_square", "⚠ 非1:1"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("filterChip", True)
            btn.setChecked(key == "all")
            btn.clicked.connect(lambda _chk, k=key: self._set_filter(k))
            self._filter_btns[key] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch()
        left_l.addLayout(filter_row)

        self._gallery_scroll = GalleryScrollArea(self._reflow_cards, left_widget)
        self._gallery_scroll.setWidgetResizable(True)
        self._gallery_container = QWidget()
        self._gallery_grid = QGridLayout(self._gallery_container)
        self._gallery_grid.setContentsMargins(2, 2, 6, 8)
        self._gallery_grid.setSpacing(10)
        self._gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._gallery_scroll.setWidget(self._gallery_container)
        left_l.addWidget(self._gallery_scroll, 1)

        # Right Panel (scrollable for smaller screens)
        right_scroll = QScrollArea(splitter)
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setMinimumWidth(480)
        right_widget = QWidget()
        right_l = QVBoxLayout(right_widget)
        right_l.setContentsMargins(10, 12, 14, 12)
        right_l.setSpacing(10)

        # Dual-anchor pairing banner
        pair_banner = QFrame(right_widget)
        pair_banner.setObjectName("PairBanner")
        pb_l = QHBoxLayout(pair_banner)
        pb_l.setContentsMargins(12, 10, 12, 10)
        pb_l.setSpacing(8)

        self._pair_img_lbl = QLabel("🖼 原图: —")
        self._pair_img_lbl.setWordWrap(True)
        self._pair_img_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._pair_img_lbl.setStyleSheet("font-weight: 600; color: #F1EFEA; background: transparent;")
        self._pair_link_lbl = QLabel("━━ 🔗 ━━")
        self._pair_link_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pair_link_lbl.setFixedWidth(68)
        self._pair_link_lbl.setStyleSheet("color: #D9B45A; font-weight: 700; background: transparent;")
        self._pair_txt_lbl = QLabel("📜 纹章文本: —")
        self._pair_txt_lbl.setWordWrap(True)
        self._pair_txt_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._pair_txt_lbl.setStyleSheet("font-weight: 600; color: #6EE7B7; background: transparent;")

        pb_l.addWidget(self._pair_img_lbl, 1)
        pb_l.addWidget(self._pair_link_lbl)
        pb_l.addWidget(self._pair_txt_lbl, 1)
        right_l.addWidget(pair_banner)

        # Preview card
        preview_card = QFrame(right_widget)
        preview_card.setObjectName("PanelCard")
        pv_l = QVBoxLayout(preview_card)
        pv_l.setContentsMargins(12, 12, 12, 12)
        pv_l.setSpacing(8)

        pv_head = QHBoxLayout()
        pv_title = QLabel("原图预览与 1:1 校验")
        pv_title.setObjectName("GoldTitle")
        pv_head.addWidget(pv_title)
        pv_head.addStretch()
        pv_head.addWidget(QLabel("参考线:"))
        self._guide_combo = QComboBox()
        self._guide_combo.addItem("无参考线", "none")
        self._guide_combo.addItem("1:1 九宫格", "grid")
        self._guide_combo.addItem("圆形印章", "circle")
        self._guide_combo.addItem("传统盾徽轮廓", "shield")
        self._guide_combo.currentIndexChanged.connect(
            lambda: self._preview.set_guide_mode(str(self._guide_combo.currentData()))
        )
        pv_head.addWidget(self._guide_combo)
        pv_l.addLayout(pv_head)

        self._preview = CoaPreviewWidget(preview_card)
        self._preview.setFixedHeight(216)
        pv_l.addWidget(self._preview)

        self._img_meta_lbl = QLabel("—")
        self._img_meta_lbl.setObjectName("MutedLabel")
        self._img_meta_lbl.setWordWrap(True)
        self._img_meta_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        pv_l.addWidget(self._img_meta_lbl)

        pv_btns = QHBoxLayout()
        pv_btns.setSpacing(6)
        self._edit_img_btn = QPushButton("✂ 1:1 编辑")
        self._edit_img_btn.clicked.connect(self._open_editor_for_selected)
        self._locate_btn = QPushButton("📂 定位")
        self._locate_btn.clicked.connect(self._locate_selected)
        self._rename_btn = QPushButton("✏ 重命名")
        self._rename_btn.clicked.connect(self._rename_selected)
        self._delete_btn = QPushButton("🗑 删除")
        self._delete_btn.setObjectName("DangerBtn")
        self._delete_btn.clicked.connect(self._delete_selected)
        for b in (self._edit_img_btn, self._locate_btn, self._rename_btn, self._delete_btn):
            pv_btns.addWidget(b)
        pv_l.addLayout(pv_btns)
        right_l.addWidget(preview_card)

        # Converter parameters card
        conv_card = QFrame(right_widget)
        conv_card.setObjectName("PanelCard")
        cv_l = QVBoxLayout(conv_card)
        cv_l.setContentsMargins(12, 12, 12, 12)
        cv_l.setSpacing(8)

        cv_title = QLabel("纹章生成参数 (coaConverter_windows.exe)")
        cv_title.setObjectName("GoldTitle")
        cv_l.addWidget(cv_title)

        # -r Resolution row
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("清晰度 (-r):"))
        self._res_slider = QSlider(Qt.Orientation.Horizontal)
        self._res_slider.setRange(20, 300)
        self._res_slider.setValue(self._config.default_resolution)
        self._res_spin = QSpinBox()
        self._res_spin.setRange(20, 400)
        self._res_spin.setValue(self._config.default_resolution)
        self._res_slider.valueChanged.connect(self._res_spin.setValue)
        self._res_spin.valueChanged.connect(lambda v: self._sync_res_slider(v))
        res_row.addWidget(self._res_slider, 1)
        res_row.addWidget(self._res_spin)

        for preset in (100, 150, 200):
            pbtn = QPushButton(str(preset))
            pbtn.setFixedWidth(40)
            pbtn.setStyleSheet("padding: 4px 0;")
            pbtn.clicked.connect(lambda _c, v=preset: self._res_spin.setValue(v))
            res_row.addWidget(pbtn)
        cv_l.addLayout(res_row)

        # -c Color mode, -k limit, -t landed title
        opt_row = QHBoxLayout()
        opt_row.setSpacing(6)
        opt_row.addWidget(QLabel("模式 (-c):"))
        self._mode_combo = QComboBox()
        for m in COLOR_MODES:
            self._mode_combo.addItem(m, m)
        idx = self._mode_combo.findData(self._config.default_color_mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._mode_combo.currentIndexChanged.connect(self._on_conv_param_changed)
        opt_row.addWidget(self._mode_combo)

        opt_row.addWidget(QLabel("色数 (-k):"))
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(2, 256)
        self._limit_spin.setValue(self._config.default_color_limit)
        self._limit_spin.valueChanged.connect(self._update_cli_preview)
        opt_row.addWidget(self._limit_spin)

        self._title_chk = QCheckBox("领地旗帜 (-t)")
        self._title_chk.setToolTip("改家族/宗族纹章请勿勾选；改伯爵领/公国/王国/帝国旗帜必须勾选后重新生成！")
        self._title_chk.setChecked(self._config.default_landed_title)
        self._title_chk.toggled.connect(self._update_cli_preview)
        opt_row.addWidget(self._title_chk)
        opt_row.addStretch()
        cv_l.addLayout(opt_row)

        self._cli_preview_lbl = QLabel()
        self._cli_preview_lbl.setWordWrap(True)
        self._cli_preview_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._cli_preview_lbl.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; color: #8E96A4; "
            "background: #101318; border: 1px solid #232833; border-radius: 6px; padding: 6px 8px;"
        )
        cv_l.addWidget(self._cli_preview_lbl)

        self._convert_btn = QPushButton("⚡ 生成 / 重新生成对应 TXT")
        self._convert_btn.setObjectName("PrimaryGoldBtn")
        self._convert_btn.clicked.connect(self._convert_selected)
        cv_l.addWidget(self._convert_btn)
        right_l.addWidget(conv_card)

        # CoA TXT Manager Card
        txt_card = QFrame(right_widget)
        txt_card.setObjectName("PanelCard")
        tx_l = QVBoxLayout(txt_card)
        tx_l.setContentsMargins(12, 12, 12, 12)
        tx_l.setSpacing(8)

        tx_head = QHBoxLayout()
        tx_title = QLabel("对应 CK3 纹章文本管理")
        tx_title.setObjectName("GoldTitle")
        tx_head.addWidget(tx_title)
        tx_head.addStretch()
        self._txt_to_img_btn = QPushButton("🔮 TXT反推生成图片")
        self._txt_to_img_btn.setToolTip("将当前纹章 .txt 或剪贴板中的纹章代码反向还原并保存为 1:1 图片")
        self._txt_to_img_btn.setStyleSheet(
            "QPushButton { background: #231D36; border: 1px solid #5B4694; color: #DDD6FE; font-weight: 700; }"
            "QPushButton:hover { background: #2E2647; border-color: #7C62C4; }"
        )
        self._txt_to_img_btn.clicked.connect(self.open_txt_to_image)
        tx_head.addWidget(self._txt_to_img_btn)

        self._open_txt_btn = QPushButton("📄 外部打开")
        self._open_txt_btn.clicked.connect(self._open_txt_external)
        tx_head.addWidget(self._open_txt_btn)
        tx_l.addLayout(tx_head)

        self._copy_txt_btn = QPushButton("📋 一键复制完整纹章代码（直接粘贴进 CK3）")
        self._copy_txt_btn.setObjectName("CopyBtn")
        self._copy_txt_btn.clicked.connect(self._copy_selected_txt)
        tx_l.addWidget(self._copy_txt_btn)

        tip_row = QHBoxLayout()
        tip_row.setSpacing(6)
        tip_lbl = QLabel("👉 复制后：进 CK3 纹章界面右下角点「从剪贴板粘贴」(等1~3秒即成)")
        tip_lbl.setStyleSheet("color: #6EE7B7; font-size: 11.5px; font-weight: 600;")
        tip_btn = QPushButton("📖 看红箭头图解")
        tip_btn.setStyleSheet(
            "QPushButton { padding: 2px 8px; font-size: 11px; color: #F3DA91; "
            "background: #262117; border: 1px solid #6E5826; border-radius: 5px; }"
            "QPushButton:hover { background: #332C1D; border-color: #D9B45A; }"
        )
        tip_btn.clicked.connect(self.open_tutorial)
        tip_row.addWidget(tip_lbl, 1)
        tip_row.addWidget(tip_btn)
        tx_l.addLayout(tip_row)

        self._txt_meta_lbl = QLabel("—")
        self._txt_meta_lbl.setObjectName("MutedLabel")
        self._txt_meta_lbl.setWordWrap(True)
        self._txt_meta_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        tx_l.addWidget(self._txt_meta_lbl)

        self._txt_preview = QPlainTextEdit()
        self._txt_preview.setReadOnly(True)
        self._txt_preview.setMinimumHeight(110)
        self._txt_preview.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11.5px; color: #C8D0DC;"
        )
        tx_l.addWidget(self._txt_preview)

        right_l.addWidget(txt_card)
        right_l.addStretch()

        right_scroll.setWidget(right_widget)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_scroll)
        splitter.setSizes([740, 560])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_vbox.addWidget(splitter, 1)

        # Status Bar
        self._status = QStatusBar(self)
        self.setStatusBar(self._status)
        self._on_conv_param_changed()

    def _bind_shortcuts(self) -> None:
        shot_act = QAction("正方形截图", self)
        shot_act.setShortcut(QKeySequence("Ctrl+Shift+A"))
        shot_act.triggered.connect(self.start_screenshot)
        self.addAction(shot_act)

        paste_act = QAction("粘贴图片", self)
        paste_act.setShortcut(QKeySequence.StandardKey.Paste)
        paste_act.triggered.connect(self._paste_from_clipboard)
        self.addAction(paste_act)

        refresh_act = QAction("刷新工作区", self)
        refresh_act.setShortcut(QKeySequence("F5"))
        refresh_act.triggered.connect(self.reload_workspace)
        self.addAction(refresh_act)

    # ------------------------------------------------------------------ Workspace & Gallery
    def reload_workspace(self, preserve_id: Optional[str] = None) -> None:
        ws = Path(self._config.workspace_dir)
        self._ws_label.setText(str(ws))
        self._ws_label.setToolTip(str(ws))
        if not self._config.converter_path or not Path(self._config.converter_path).is_file():
            self._config.converter_path = discover_converter(str(ws))

        self._thumb_cache.clear()
        self._entries = scan_workspace(ws)
        self._update_filter_counts()

        target_id = preserve_id or self._selected_id
        self._apply_filter_and_render(target_id)

        conv_ok = bool(self._config.converter_path and Path(self._config.converter_path).is_file())
        if not conv_ok:
            self._status.showMessage("⚠ 未检测到 coaConverter_windows.exe，请在右上角「设置」中指定路径。")
        else:
            paired = sum(1 for e in self._entries if e.is_paired)
            self._status.showMessage(
                f"已加载 {len(self._entries)} 个条目（其中 {paired} 组已完成 原图↔TXT 配对） · 按 Ctrl+V 可直接粘贴图片"
            )

    def _update_filter_counts(self) -> None:
        counts = {
            "all": len(self._entries),
            "paired": sum(1 for e in self._entries if e.is_paired),
            "pending": sum(1 for e in self._entries if e.has_image and not e.has_txt),
            "txt_only": sum(1 for e in self._entries if not e.has_image and e.has_txt),
            "non_square": sum(
                1 for e in self._entries if e.has_image and e.image_width > 0 and not e.is_square
            ),
        }
        labels = {
            "all": "全部",
            "paired": "✓ 已关联TXT",
            "pending": "○ 待生成",
            "txt_only": "📄 仅TXT",
            "non_square": "⚠ 非1:1",
        }
        for key, btn in self._filter_btns.items():
            btn.setText(f"{labels[key]} ({counts[key]})")

        self._batch_btn.setEnabled(counts["pending"] > 0 and not self._runner.is_running)

    def _set_filter(self, key: str) -> None:
        self._active_filter = key
        for k, btn in self._filter_btns.items():
            btn.setChecked(k == key)
        self._apply_filter_and_render()

    def _apply_filter_and_render(self, target_id: Optional[str] = None) -> None:
        query = self._search_edit.text().strip().lower()
        filtered: list[CoaEntry] = []
        for e in self._entries:
            if self._active_filter == "paired" and not e.is_paired:
                continue
            if self._active_filter == "pending" and not (e.has_image and not e.has_txt):
                continue
            if self._active_filter == "txt_only" and not (not e.has_image and e.has_txt):
                continue
            if self._active_filter == "non_square" and not (
                e.has_image and e.image_width > 0 and not e.is_square
            ):
                continue

            if query:
                hay = e.stem.lower()
                if e.image_path:
                    hay += " " + e.image_path.name.lower()
                if e.txt_path:
                    hay += " " + e.txt_path.name.lower()
                if query not in hay:
                    continue
            filtered.append(e)

        self._filtered_entries = filtered
        self._rebuild_cards()

        want_id = target_id or self._selected_id
        if want_id and any(e.entry_id == want_id for e in self._filtered_entries):
            self._select_entry(want_id)
        elif self._filtered_entries:
            self._select_entry(self._filtered_entries[0].entry_id)
        else:
            self._selected_id = ""
            self._render_detail(None)

    def _get_thumbnail(self, entry: CoaEntry) -> Optional[QPixmap]:
        if entry.has_image and entry.image_path:
            key = str(entry.image_path)
            if key not in self._thumb_cache:
                pm = QPixmap(key)
                if not pm.isNull():
                    self._thumb_cache[key] = pm.scaled(
                        182,
                        158,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                else:
                    self._thumb_cache[key] = QPixmap()
            return self._thumb_cache[key]

        # For TXT-only valid CoA files (e.g. 明月.txt), automatically reverse-render a thumbnail!
        if entry.has_txt and entry.txt_path and entry.txt_meta and entry.txt_meta.is_valid_coa:
            key = f"txt_rev::{entry.txt_path}"
            if key not in self._thumb_cache:
                try:
                    res = render_coa_txt_file(entry.txt_path, output_size=182, smooth_upscale=True)
                    self._thumb_cache[key] = pil_to_qpixmap(res.image)
                except Exception:
                    self._thumb_cache[key] = QPixmap()
            pm = self._thumb_cache[key]
            return pm if not pm.isNull() else None

        return None

    def _rebuild_cards(self) -> None:
        while self._gallery_grid.count():
            item = self._gallery_grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._cards.clear()

        if not self._filtered_entries:
            empty = QLabel("当前筛选条件下暂无条目。\n可点击顶部「📷 正方形截图」或「🖼 导入图片」开始制作。")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #7D8596; padding: 48px;")
            self._gallery_grid.addWidget(empty, 0, 0)
            return

        avail = max(220, self._gallery_scroll.viewport().width() - 16)
        cols = max(1, avail // (CoaCardWidget.CARD_WIDTH + 12))

        for idx, entry in enumerate(self._filtered_entries):
            card = CoaCardWidget(
                entry=entry,
                thumbnail=self._get_thumbnail(entry),
                selected=(entry.entry_id == self._selected_id),
                parent=self._gallery_container,
            )
            card.clicked.connect(self._select_entry)
            card.quick_copy.connect(self._copy_entry_by_id)
            card.quick_convert.connect(self._convert_entry_by_id)
            self._cards[entry.entry_id] = card
            self._gallery_grid.addWidget(card, idx // cols, idx % cols)

    def _reflow_cards(self) -> None:
        if not self._cards:
            return
        avail = max(220, self._gallery_scroll.viewport().width() - 16)
        cols = max(1, avail // (CoaCardWidget.CARD_WIDTH + 12))
        for idx, entry in enumerate(self._filtered_entries):
            card = self._cards.get(entry.entry_id)
            if card is not None:
                self._gallery_grid.addWidget(card, idx // cols, idx % cols)

    def _find_entry(self, entry_id: str) -> Optional[CoaEntry]:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def _select_entry(self, entry_id: str) -> None:
        self._selected_id = entry_id
        for cid, card in self._cards.items():
            card.set_selected(cid == entry_id)
        self._render_detail(self._find_entry(entry_id))

    # ------------------------------------------------------------------ Detail Rendering
    def _render_detail(self, entry: Optional[CoaEntry]) -> None:
        if entry is None:
            self._pair_img_lbl.setText("🖼 原图: 未选中")
            self._pair_link_lbl.setText("━━ — ━━")
            self._pair_txt_lbl.setText("📜 纹章文本: 未选中")
            self._preview.set_image_path(None)
            self._img_meta_lbl.setText("—")
            self._txt_meta_lbl.setText("—")
            self._txt_preview.clear()
            for b in (
                self._edit_img_btn,
                self._locate_btn,
                self._rename_btn,
                self._delete_btn,
                self._convert_btn,
                self._copy_txt_btn,
                self._open_txt_btn,
            ):
                b.setEnabled(False)
            self._update_cli_preview()
            return

        # Pairing Banner
        if entry.has_image and entry.image_path:
            dim = f"{entry.image_width}×{entry.image_height}"
            sq = "1:1 正方形" if entry.is_square else "⚠ 非正方形"
            self._pair_img_lbl.setText(f"🖼 原图: {entry.image_path.name}\n({dim} · {sq})")
        else:
            self._pair_img_lbl.setText("🖼 原图: 无对应原图")

        if entry.is_paired:
            self._pair_link_lbl.setText("━━ 🔗 ━━\n一一对应")
            self._pair_link_lbl.setStyleSheet("color: #D9B45A; font-weight: 700; background: transparent;")
        elif entry.has_image:
            self._pair_link_lbl.setText("━━ ○ ━━\n待生成")
            self._pair_link_lbl.setStyleSheet("color: #8E96A4; font-weight: 600; background: transparent;")
        else:
            self._pair_link_lbl.setText("━━ 📄 ━━\n仅文本")
            self._pair_link_lbl.setStyleSheet("color: #60A5FA; font-weight: 600; background: transparent;")

        if entry.has_txt and entry.txt_path and entry.txt_meta:
            self._pair_txt_lbl.setText(
                f"📜 纹章文本: {entry.txt_path.name}\n"
                f"({entry.txt_meta.coa_kind_label} · {entry.txt_meta.size_str})"
            )
            self._pair_txt_lbl.setStyleSheet("font-weight: 600; color: #6EE7B7; background: transparent;")
        else:
            expected_name = f"{entry.stem}.txt"
            self._pair_txt_lbl.setText(f"📜 纹章文本: 尚未生成\n(生成后将保存为 {expected_name})")
            self._pair_txt_lbl.setStyleSheet("font-weight: 600; color: #636B7A; background: transparent;")

        # Image preview & metadata
        if entry.has_image and entry.image_path:
            self._preview.set_image_path(entry.image_path)
            sq_tip = "✓ 1:1 比例标准" if entry.is_square else "⚠ 非 1:1 正方形，建议先点下方「1:1 编辑 / 裁切」"
            dup_tip = (
                f" · 同名还有 {entry.duplicate_stem_count - 1} 张其他格式图片"
                if entry.duplicate_stem_count > 1
                else ""
            )
            self._img_meta_lbl.setText(
                f"文件: {entry.image_path.name} · 尺寸: {entry.image_width}×{entry.image_height} px · "
                f"体积: {entry.image_size_str} · {sq_tip}{dup_tip}"
            )
        elif entry.has_txt and entry.txt_path and entry.txt_meta and entry.txt_meta.is_valid_coa:
            try:
                res = render_coa_txt_file(entry.txt_path, output_size=512, smooth_upscale=True)
                self._preview.set_pixmap(pil_to_qpixmap(res.image))
                self._img_meta_lbl.setText(
                    f"🔮 已从 {entry.txt_path.name} 实时反推还原画面（原始网格 {res.native_grid_size}×{res.native_grid_size} · "
                    f"{res.color_groups} 色） · 点击下方「🔮 TXT反推生成图片」即可保存为 PNG 原图！"
                )
            except Exception:
                self._preview.set_image_path(None)
                self._img_meta_lbl.setText("当前为纯文本条目，无关联源图片。")
        else:
            self._preview.set_image_path(None)
            self._img_meta_lbl.setText("当前为纯文本条目，无关联源图片。")

        # Button enable states
        self._edit_img_btn.setEnabled(entry.has_image)
        self._locate_btn.setEnabled(True)
        self._rename_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
        self._convert_btn.setEnabled(entry.has_image and not self._runner.is_running)

        # TXT section
        if entry.has_txt and entry.txt_path and entry.txt_meta:
            m = entry.txt_meta
            self._copy_txt_btn.setEnabled(True)
            self._open_txt_btn.setEnabled(True)
            self._copy_txt_btn.setText(f"📋 一键复制完整纹章代码 ({entry.txt_path.name})")
            self._txt_meta_lbl.setText(
                f"类型: {m.coa_kind_label} · 总行数: {m.line_count:,} 行 · "
                f"体积: {m.size_str} · 更新时间: {m.modified_str}  "
                f"（下方仅展示前 {len(m.preview_lines)} 行以保持流畅）"
            )
            self._txt_preview.setPlainText("\n".join(m.preview_lines))
        else:
            self._copy_txt_btn.setEnabled(False)
            self._open_txt_btn.setEnabled(False)
            self._copy_txt_btn.setText("📋 尚未生成对应 TXT")
            self._txt_meta_lbl.setText("点击上方「⚡ 生成 / 重新生成对应 TXT」即可生成可直接粘贴到 CK3 的纹章代码。")
            self._txt_preview.clear()

        self._update_cli_preview()

    # ------------------------------------------------------------------ Converter Controls
    def _sync_res_slider(self, value: int) -> None:
        clipped = max(self._res_slider.minimum(), min(value, self._res_slider.maximum()))
        self._res_slider.blockSignals(True)
        self._res_slider.setValue(clipped)
        self._res_slider.blockSignals(False)
        self._update_cli_preview()

    def _on_conv_param_changed(self) -> None:
        mode = str(self._mode_combo.currentData())
        self._limit_spin.setEnabled(mode == "Reduced")
        self._update_cli_preview()

    def _build_params_for(self, entry: CoaEntry) -> Optional[ConvertParams]:
        if not entry.has_image or not entry.image_path:
            return None
        return ConvertParams(
            source_path=entry.image_path,
            destination_path=entry.image_path.with_suffix(".txt"),
            resolution=self._res_spin.value(),
            color_mode=str(self._mode_combo.currentData()),
            color_limit=self._limit_spin.value(),
            landed_title=self._title_chk.isChecked(),
        )

    def _update_cli_preview(self) -> None:
        entry = self._find_entry(self._selected_id)
        exe = self._config.converter_path or "coaConverter_windows.exe"
        if entry and entry.has_image:
            params = self._build_params_for(entry)
            if params:
                self._cli_preview_lbl.setText(params.format_command(exe))
                return
        self._cli_preview_lbl.setText(f'"{exe}" -s <源图片> -r {self._res_spin.value()}')

    def _convert_selected(self) -> None:
        if self._runner.is_running:
            self._batch_queue.clear()
            self._runner.cancel()
            return
        entry = self._find_entry(self._selected_id)
        if entry:
            self._run_convert_entry(entry)

    def _convert_entry_by_id(self, entry_id: str) -> None:
        if self._runner.is_running:
            QMessageBox.information(self, "请稍候", "当前已有转换任务正在进行。")
            return
        entry = self._find_entry(entry_id)
        if entry:
            self._select_entry(entry_id)
            self._run_convert_entry(entry)

    def _run_convert_entry(self, entry: CoaEntry) -> None:
        exe = self._config.converter_path
        if not exe or not Path(exe).is_file():
            QMessageBox.warning(
                self,
                "未找到转换器",
                "请先在右上角「⚙ 设置」中指定 coaConverter_windows.exe 的路径。",
            )
            return
        params = self._build_params_for(entry)
        if not params:
            return
        try:
            self._runner.start(exe, params)
        except Exception as exc:
            QMessageBox.critical(self, "转换启动失败", str(exc))

    def _start_batch_convert(self) -> None:
        if self._runner.is_running:
            return
        exe = self._config.converter_path
        if not exe or not Path(exe).is_file():
            QMessageBox.warning(
                self,
                "未找到转换器",
                "请先在右上角「⚙ 设置」中指定 coaConverter_windows.exe 的路径。",
            )
            return

        pending = [e for e in self._entries if e.has_image and not e.has_txt]
        if not pending:
            QMessageBox.information(self, "提示", "所有图片都已经生成对应的 TXT 文件了！")
            return

        ans = QMessageBox.question(
            self,
            "批量转换确认",
            f"检测到 {len(pending)} 张图片尚未生成 TXT，是否使用当前参数（-r {self._res_spin.value()}）批量转换？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        self._batch_queue = pending[1:]
        self._run_convert_entry(pending[0])

    def _on_convert_started(self, source_path: str, _cmd: str) -> None:
        name = Path(source_path).name
        self._convert_btn.setText("⏹ 正在转换中...（点击取消）")
        self._batch_btn.setEnabled(False)
        rem = f"（队列剩余 {len(self._batch_queue)} 项）" if self._batch_queue else ""
        self._status.showMessage(f"⏳ 正在将 {name} 转换为 CK3 纹章 TXT... {rem}")

    def _on_convert_finished(
        self, ok: bool, source_path: str, dest_path: str, elapsed: float
    ) -> None:
        self._convert_btn.setText("⚡ 生成 / 重新生成对应 TXT")
        src_name = Path(source_path).name
        dst_name = Path(dest_path).name

        if self._batch_queue:
            next_entry = self._batch_queue.pop(0)
            self._status.showMessage(
                f"{'✓' if ok else '✕'} {src_name} {'完成' if ok else '失败'} ({elapsed:.1f}s)，继续下一项..."
            )
            self._run_convert_entry(next_entry)
            return

        self.reload_workspace(preserve_id=source_path)
        if ok:
            self._status.showMessage(
                f"✓ 转换完成: {src_name} → {dst_name}（耗时 {elapsed:.2f}s），可直接点击复制！"
            )
        else:
            QMessageBox.warning(
                self,
                "转换未成功",
                f"{src_name} 转换失败或被取消，请检查源图片格式及转换器设置。",
            )

    # ------------------------------------------------------------------ TXT Copy & Actions
    def _copy_entry_by_id(self, entry_id: str) -> None:
        entry = self._find_entry(entry_id)
        if not entry or not entry.has_txt or not entry.txt_path:
            return
        self._select_entry(entry_id)
        self._copy_txt_to_clipboard(entry.txt_path, entry.txt_meta.line_count if entry.txt_meta else 0)

    def _copy_selected_txt(self) -> None:
        entry = self._find_entry(self._selected_id)
        if not entry or not entry.has_txt or not entry.txt_path:
            return
        self._copy_txt_to_clipboard(entry.txt_path, entry.txt_meta.line_count if entry.txt_meta else 0)

    def _copy_txt_to_clipboard(self, txt_path: Path, line_count: int) -> None:
        try:
            content = read_txt_full(txt_path)
            QGuiApplication.clipboard().setText(content)
            self._copy_txt_btn.setText(f"✓ 已复制 {txt_path.name}！现在去 CK3 右下角点「从剪贴板粘贴」")
            self._status.showMessage(
                f"✓ 已复制 {txt_path.name}（{line_count:,} 行）！请进入 CK3 纹章界面右下角点击「从剪贴板粘贴」（等待 1~3 秒加载）。",
                8000,
            )
            QTimer.singleShot(
                2200,
                lambda: self._restore_copy_btn_label(txt_path.name),
            )
        except Exception as exc:
            QMessageBox.critical(self, "复制失败", str(exc))

    def _restore_copy_btn_label(self, txt_name: str) -> None:
        entry = self._find_entry(self._selected_id)
        if entry and entry.has_txt and entry.txt_path and entry.txt_path.name == txt_name:
            self._copy_txt_btn.setText(f"📋 一键复制完整纹章代码 ({txt_name})")

    def _open_txt_external(self) -> None:
        entry = self._find_entry(self._selected_id)
        if entry and entry.has_txt and entry.txt_path:
            os.startfile(str(entry.txt_path))  # type: ignore[attr-defined]

    def _locate_selected(self) -> None:
        entry = self._find_entry(self._selected_id)
        if not entry:
            return
        target = entry.image_path if entry.has_image else entry.txt_path
        if target and target.exists():
            import subprocess

            subprocess.Popen(["explorer", "/select,", str(target.resolve())])

    def _rename_selected(self) -> None:
        entry = self._find_entry(self._selected_id)
        if not entry:
            return
        msg = "请输入新的统一名称（将同步重命名"
        parts = []
        if entry.has_image and entry.image_path:
            parts.append(entry.image_path.name)
        if entry.has_txt and entry.txt_path:
            parts.append(entry.txt_path.name)
        msg += " 与 ".join(parts) + "）："

        new_stem, ok = QInputDialog.getText(self, "同步重命名", msg, text=entry.stem)
        if not ok:
            return
        try:
            new_img, new_txt = rename_entry(entry, new_stem)
            next_id = str(new_img or new_txt or "")
            self.reload_workspace(preserve_id=next_id)
            self._status.showMessage(f"✓ 已同步重命名为: {new_stem.strip()}")
        except Exception as exc:
            QMessageBox.warning(self, "重命名失败", str(exc))

    def _delete_selected(self) -> None:
        entry = self._find_entry(self._selected_id)
        if not entry:
            return
        targets: list[Path] = []
        if entry.has_image and entry.image_path:
            targets.append(entry.image_path)
        if entry.has_txt and entry.txt_path:
            targets.append(entry.txt_path)
        if not targets:
            return

        names = "\n".join(f"• {p.name}" for p in targets)
        ans = QMessageBox.question(
            self,
            "确认移入回收站",
            f"确定将以下关联文件移入 Windows 回收站吗？\n\n{names}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        move_to_recycle_bin(targets)
        self._selected_id = ""
        self.reload_workspace()
        self._status.showMessage("✓ 已将选中文件移入回收站。")

    # ------------------------------------------------------------------ Screenshot & Editor
    def start_screenshot(self) -> None:
        self.hide()
        QApplication.processEvents()
        QTimer.singleShot(260, self._overlay.begin_capture)

    def _on_screenshot_cancelled(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_screenshot_captured(self, qimg: QImage) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

        pil_img = qimage_to_pil(qimg)
        ws = Path(self._config.workspace_dir)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        stem = f"screenshot_{stamp}"

        if self._config.screenshot_open_editor:
            self._launch_editor(
                source_image=pil_img,
                suggested_stem=stem,
            )
        else:
            dest = ws / f"{stem}.png"
            save_square_image(pil_img, dest, "png")
            self.reload_workspace(preserve_id=str(dest))
            self._status.showMessage(f"✓ 已保存 1:1 截图: {dest.name}")
            if self._config.editor_auto_convert:
                entry = self._find_entry(str(dest))
                if entry:
                    self._run_convert_entry(entry)

    def _open_editor_for_selected(self) -> None:
        entry = self._find_entry(self._selected_id)
        if not entry or not entry.has_image or not entry.image_path:
            return
        self._launch_editor(source_path=entry.image_path)

    def _launch_editor(
        self,
        source_path: Optional[Path] = None,
        source_image: Optional[Image.Image] = None,
        suggested_stem: str = "",
    ) -> None:
        dlg = SquareImageEditorDialog(
            workspace_dir=Path(self._config.workspace_dir),
            source_path=source_path,
            source_image=source_image,
            suggested_stem=suggested_stem,
            default_auto_convert=self._config.editor_auto_convert,
            parent=self,
        )
        if dlg.exec() == SquareImageEditorDialog.DialogCode.Accepted and dlg.saved_path:
            saved = dlg.saved_path
            self.reload_workspace(preserve_id=str(saved))
            self._status.showMessage(f"✓ 已保存 1:1 图片: {saved.name}")
            if dlg.should_auto_convert:
                entry = self._find_entry(str(saved))
                if entry:
                    self._run_convert_entry(entry)

    # ------------------------------------------------------------------ Import / Paste / Drop
    def _import_images(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "导入图片到纹章工作区",
            self._config.workspace_dir,
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if files:
            self._handle_imported_paths([Path(f) for f in files])

    def _handle_imported_paths(self, paths: list[Path]) -> None:
        ws = Path(self._config.workspace_dir)
        valid = [p for p in paths if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
        if not valid:
            return

        if len(valid) == 1:
            src = valid[0]
            try:
                with Image.open(src) as im:
                    w, h = im.size
            except Exception as exc:
                QMessageBox.warning(self, "无法读取图片", str(exc))
                return

            if w != h:
                ans = QMessageBox.question(
                    self,
                    "检测到非正方形图片",
                    f"{src.name} 尺寸为 {w}×{h}（非 1:1 正方形）。\n是否立即在「1:1 正方形编辑器」中裁切/填充后保存？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ans == QMessageBox.StandardButton.Yes:
                    self._launch_editor(source_path=src, suggested_stem=src.stem)
                    return

            dest = ws / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            self.reload_workspace(preserve_id=str(dest))
            self._status.showMessage(f"✓ 已导入: {dest.name}")
            return

        # Multiple images
        copied: list[Path] = []
        for src in valid:
            dest = ws / src.name
            if src.resolve() != dest.resolve():
                shutil.copy2(src, dest)
            copied.append(dest)
        self.reload_workspace(preserve_id=str(copied[0]) if copied else None)
        self._status.showMessage(f"✓ 已导入 {len(copied)} 张图片到工作区。")

    def _paste_from_clipboard(self) -> None:
        if self._search_edit.hasFocus():
            return
        cb = QGuiApplication.clipboard()
        mime = cb.mimeData()
        if mime and mime.hasImage():
            qimg = cb.image()
            if not qimg.isNull():
                pil_img = qimage_to_pil(qimg)
                stamp = time.strftime("%Y%m%d_%H%M%S")
                self._launch_editor(source_image=pil_img, suggested_stem=f"paste_{stamp}")
                return
        if mime and mime.hasText():
            text = cb.text()
            if text and "colored_emblem" in text:
                self.open_txt_to_image(initial_code=text)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if Path(url.toLocalFile()).suffix.lower() in IMAGE_EXTENSIONS:
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        self._handle_imported_paths(paths)

    # ------------------------------------------------------------------ Workspace & Settings
    def _choose_workspace(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择纹章图片与 TXT 工作目录",
            self._config.workspace_dir,
        )
        if folder:
            self._config.workspace_dir = folder
            self._config.save()
            self._selected_id = ""
            self.reload_workspace()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._config, self)
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            self._res_spin.setValue(self._config.default_resolution)
            idx = self._mode_combo.findData(self._config.default_color_mode)
            if idx >= 0:
                self._mode_combo.setCurrentIndex(idx)
            self._limit_spin.setValue(self._config.default_color_limit)
            self._title_chk.setChecked(self._config.default_landed_title)
            self.reload_workspace()

    def open_tutorial(self) -> None:
        dlg = TutorialDialog(self._config, self)
        dlg.exec()

    def open_historical_library(self) -> None:
        dlg = HistoricalLibraryDialog(
            workspace_dir=Path(self._config.workspace_dir),
            default_auto_convert=self._config.editor_auto_convert,
            parent=self,
        )
        if dlg.exec() == HistoricalLibraryDialog.DialogCode.Accepted and dlg.saved_paths:
            first_saved = dlg.saved_paths[0]
            self.reload_workspace(preserve_id=str(first_saved))
            if len(dlg.saved_paths) == 1:
                self._status.showMessage(f"✓ 已导入欧洲历史名章: {first_saved.name}")
                if dlg.should_auto_convert_single:
                    entry = self._find_entry(str(first_saved))
                    if entry:
                        self._run_convert_entry(entry)
            else:
                self._status.showMessage(f"✓ 已一键导入全部 {len(dlg.saved_paths)} 款欧洲历史名章到工作区！")

    def open_txt_to_image(self, _checked: bool = False, initial_code: str = "") -> None:
        entry = self._find_entry(self._selected_id)
        init_path = (
            entry.txt_path
            if (not initial_code and entry and entry.has_txt and entry.txt_path)
            else None
        )
        dlg = TxtToImageDialog(
            workspace_dir=Path(self._config.workspace_dir),
            initial_txt_path=init_path,
            initial_code=initial_code,
            parent=self,
        )
        if dlg.exec() == TxtToImageDialog.DialogCode.Accepted and dlg.saved_image_path:
            saved = dlg.saved_image_path
            self.reload_workspace(preserve_id=str(saved))
            self._status.showMessage(f"✓ 已从纹章 TXT 反向还原并保存图片: {saved.name}")

    def open_composer(self) -> None:
        dlg = HeraldicComposerDialog(
            workspace_dir=Path(self._config.workspace_dir),
            entries=self._entries,
            default_auto_convert=self._config.editor_auto_convert,
            parent=self,
        )
        if dlg.exec() == HeraldicComposerDialog.DialogCode.Accepted and dlg.saved_image_path:
            saved = dlg.saved_image_path
            self.reload_workspace(preserve_id=str(saved))
            if dlg.saved_txt_path:
                self._status.showMessage(
                    f"✓ 已完成多纹章拼接与 TXT 坐标直拼: {saved.name} ↔ {dlg.saved_txt_path.name}"
                )
            else:
                self._status.showMessage(f"✓ 已保存联合拼接纹章: {saved.name}")
                if dlg.should_auto_convert:
                    entry = self._find_entry(str(saved))
                    if entry:
                        self._run_convert_entry(entry)

    def open_tutorial_first_launch(self) -> None:
        if self._config.show_tutorial_on_startup:
            self._config.show_tutorial_on_startup = False
            self._config.save()
            dlg = TutorialDialog(self._config, self)
            dlg.exec()
