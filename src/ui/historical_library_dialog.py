"""Dialog for browsing and importing the 14 built-in famous European historical Coats of Arms."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.historical_presets import HISTORICAL_PRESETS, HistoricalPreset
from src.core.image_ops import save_square_image
from src.ui.preview_widget import CoaPreviewWidget
from src.ui.theme import pil_to_qpixmap


class HistoricalLibraryDialog(QDialog):
    """Visual gallery of built-in European historical Coats of Arms."""

    def __init__(
        self,
        workspace_dir: Path,
        default_auto_convert: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🏛️ 欧洲历史名门纹章库（内置 14 款经典王室/帝国纹章）— 十字军之王3纹章生成工坊")
        self.resize(980, 660)

        self._workspace_dir = workspace_dir
        self._img_cache: dict[str, Image.Image] = {}
        self._pm_cache: dict[str, QPixmap] = {}
        self.saved_paths: list[Path] = []
        self.should_auto_convert_single: bool = False

        self._build_ui(default_auto_convert)
        self._list.setCurrentRow(0)

    def _get_preset_image(self, preset: HistoricalPreset) -> tuple[Image.Image, QPixmap]:
        if preset.preset_id not in self._img_cache:
            pil_img = preset.generator(512)
            self._img_cache[preset.preset_id] = pil_img
            self._pm_cache[preset.preset_id] = pil_to_qpixmap(pil_img)
        return self._img_cache[preset.preset_id], self._pm_cache[preset.preset_id]

    def _build_ui(self, default_auto_convert: bool) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # Left column: List of 14 historical presets
        left_card = QFrame(self)
        left_card.setObjectName("PanelCard")
        ll = QVBoxLayout(left_card)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)

        head = QLabel("👑 内置欧洲知名历史王朝 / 王国纹章（点击预览）")
        head.setObjectName("GoldTitle")
        ll.addWidget(head)

        sub = QLabel("所有历史纹章均为软件内置矢量高清绘制（512×512），可一键导入工作区或送入多纹章拼接工坊。")
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #8E96A4; font-size: 11.5px;")
        ll.addWidget(sub)

        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setStyleSheet(
            "QListWidget { background: #101318; border: 1px solid #282E3A; border-radius: 8px; padding: 4px; }"
            "QListWidget::item { padding: 8px 10px; border-radius: 6px; margin-bottom: 2px; }"
            "QListWidget::item:selected { background: #262117; color: #F3DA91; font-weight: 700; border: 1px solid #D9B45A; }"
        )
        for idx, p in enumerate(HISTORICAL_PRESETS, 1):
            item = QListWidgetItem(f"{idx:02d}. {p.name}  ·  [{p.dynasty_or_realm}]")
            item.setData(Qt.ItemDataRole.UserRole, p.preset_id)
            self._list.addItem(item)
        self._list.currentRowChanged.connect(self._on_row_changed)
        ll.addWidget(self._list, 1)

        import_all_btn = QPushButton("📦 一键将全部 14 款欧洲历史名章导入我的工作区")
        import_all_btn.setStyleSheet(
            "QPushButton { background: #19322A; border: 1px solid #2D6A54; color: #A7F3D0; font-weight: 700; padding: 8px 12px; }"
            "QPushButton:hover { background: #214539; border-color: #3E8E72; }"
        )
        import_all_btn.clicked.connect(self._import_all_presets)
        ll.addWidget(import_all_btn)

        root.addWidget(left_card, 3)

        # Right column: Large 1:1 preview & details
        right_card = QFrame(self)
        right_card.setObjectName("PanelCard")
        right_card.setFixedWidth(410)
        rl = QVBoxLayout(right_card)
        rl.setContentsMargins(14, 14, 14, 14)
        rl.setSpacing(10)

        self._title_lbl = QLabel()
        self._title_lbl.setWordWrap(True)
        self._title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #E6C775;")
        rl.addWidget(self._title_lbl)

        self._realm_lbl = QLabel()
        self._realm_lbl.setWordWrap(True)
        self._realm_lbl.setStyleSheet("color: #6EE7B7; font-weight: 600; font-size: 12.5px;")
        rl.addWidget(self._realm_lbl)

        self._preview = CoaPreviewWidget(right_card)
        self._preview.setFixedHeight(290)
        rl.addWidget(self._preview)

        self._desc_lbl = QLabel()
        self._desc_lbl.setWordWrap(True)
        self._desc_lbl.setStyleSheet(
            "color: #E6E3DC; font-size: 12.5px; background: #101318; "
            "border: 1px solid #232833; border-radius: 8px; padding: 10px;"
        )
        rl.addWidget(self._desc_lbl)

        self._auto_conv_chk = QCheckBox("导入单个纹章后立即调用转换器生成 CK3 纹章 TXT")
        self._auto_conv_chk.setChecked(default_auto_convert)
        rl.addWidget(self._auto_conv_chk)

        rl.addStretch()

        btn_row = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.reject)

        import_one_btn = QPushButton("⚡ 导入此纹章到工作区")
        import_one_btn.setObjectName("PrimaryGoldBtn")
        import_one_btn.clicked.connect(self._import_selected_preset)

        btn_row.addWidget(close_btn)
        btn_row.addWidget(import_one_btn, 1)
        rl.addLayout(btn_row)

        root.addWidget(right_card)

    def _current_preset(self) -> HistoricalPreset:
        row = max(0, self._list.currentRow())
        return HISTORICAL_PRESETS[row]

    def _on_row_changed(self, row: int) -> None:
        if not (0 <= row < len(HISTORICAL_PRESETS)):
            return
        preset = HISTORICAL_PRESETS[row]
        _, pm = self._get_preset_image(preset)
        self._title_lbl.setText(preset.name)
        self._realm_lbl.setText(f"🏛️ 历史归属：{preset.dynasty_or_realm}  |  规格：512×512 (1:1)")
        self._desc_lbl.setText(preset.description)
        self._preview.set_pixmap(pm)

    def _import_selected_preset(self) -> None:
        preset = self._current_preset()
        pil_img, _ = self._get_preset_image(preset)
        dest = self._workspace_dir / f"{preset.preset_id}.png"
        save_square_image(pil_img, dest, "png")
        self.saved_paths = [dest]
        self.should_auto_convert_single = self._auto_conv_chk.isChecked()
        self.accept()

    def _import_all_presets(self) -> None:
        saved: list[Path] = []
        for preset in HISTORICAL_PRESETS:
            pil_img, _ = self._get_preset_image(preset)
            dest = self._workspace_dir / f"{preset.preset_id}.png"
            save_square_image(pil_img, dest, "png")
            saved.append(dest)
        self.saved_paths = saved
        self.should_auto_convert_single = False
        QMessageBox.information(
            self,
            "已全部导入",
            f"已将全部 {len(saved)} 款欧洲知名历史纹章（512×512 高清 1:1）导入至工作区！\n"
            "您可以在主窗口直接点击生成 TXT，或在「🧩 多纹章拼接」中自由组合它们。",
        )
        self.accept()
