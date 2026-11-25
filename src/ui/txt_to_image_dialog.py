"""Dialog to reverse-render CK3 CoA .txt files or clipboard code back into 1:1 images."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.image_ops import save_square_image
from src.core.txt_renderer import TxtRenderResult, render_coa_txt_string
from src.ui.preview_widget import CoaPreviewWidget
from src.ui.theme import pil_to_qpixmap


class TxtToImageDialog(QDialog):
    """Reverse converts a CK3 CoA .txt file or pasted clipboard script into a 1:1 PNG image."""

    def __init__(
        self,
        workspace_dir: Path,
        initial_txt_path: Optional[Path] = None,
        initial_code: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🔮 纹章 TXT 反推生成图片 — 十字军之王3纹章生成工坊")
        self.resize(980, 660)

        self._workspace_dir = workspace_dir
        self._source_txt_path = initial_txt_path
        self._current_code = initial_code
        self._render_result: Optional[TxtRenderResult] = None
        self.saved_image_path: Optional[Path] = None

        if not self._current_code and self._source_txt_path and self._source_txt_path.is_file():
            self._current_code = self._source_txt_path.read_text(encoding="utf-8", errors="replace")

        self._build_ui()
        if self._current_code:
            self._parse_and_render()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        # Left column: 1:1 Rendered Image Preview
        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        banner = QFrame(self)
        banner.setObjectName("PairBanner")
        bl = QVBoxLayout(banner)
        bl.setContentsMargins(12, 8, 12, 8)
        tip = QLabel(
            "🔮 <b>纹章代码反向还原为图片</b>：无论是孤立的 <code>.txt</code> 文件，还是网上/游戏里复制来的纹章代码，"
            "都能瞬间解析所有色块坐标并还原为 <code>1:1</code> 高清图片！"
        )
        tip.setWordWrap(True)
        tip.setTextFormat(Qt.TextFormat.RichText)
        tip.setStyleSheet("color: #EAE6DF; font-size: 12px;")
        bl.addWidget(tip)
        left_col.addWidget(banner)

        self._preview = CoaPreviewWidget(self)
        self._preview._empty_text = "请在右侧选择 .txt 文件\n或点击「📋 粘贴剪贴板纹章代码」"
        left_col.addWidget(self._preview, 1)

        self._stats_lbl = QLabel("等待载入纹章 TXT 代码...")
        self._stats_lbl.setStyleSheet("color: #6EE7B7; font-weight: 600; font-size: 12.5px;")
        left_col.addWidget(self._stats_lbl)

        root.addLayout(left_col, 3)

        # Right column: Source selector & export controls
        panel = QFrame(self)
        panel.setObjectName("PanelCard")
        panel.setFixedWidth(410)
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(14, 12, 14, 12)
        pl.setSpacing(10)

        pl.addWidget(self._sec_label("1. 载入纹章 TXT 代码来源"))
        src_btns = QHBoxLayout()
        src_btns.setSpacing(8)
        paste_btn = QPushButton("📋 粘贴剪贴板中的纹章代码")
        paste_btn.setObjectName("CopyBtn")
        paste_btn.clicked.connect(self._paste_from_clipboard)

        open_file_btn = QPushButton("📂 选择 .txt 文件...")
        open_file_btn.clicked.connect(self._choose_txt_file)
        src_btns.addWidget(paste_btn, 1)
        src_btns.addWidget(open_file_btn)
        pl.addLayout(src_btns)

        self._source_lbl = QLabel()
        self._source_lbl.setWordWrap(True)
        self._source_lbl.setStyleSheet("color: #8E96A4; font-size: 11.5px;")
        self._update_source_label()
        pl.addWidget(self._source_lbl)

        self._code_preview = QPlainTextEdit()
        self._code_preview.setReadOnly(True)
        self._code_preview.setPlaceholderText("此处显示已载入的纹章代码前 35 行摘要...")
        self._code_preview.setMaximumHeight(165)
        self._code_preview.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 11px; color: #C8D0DC;"
        )
        pl.addWidget(self._code_preview)

        pl.addWidget(self._sec_label("2. 还原画质与输出尺寸"))
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("放大算法:"))
        self._smooth_combo = QComboBox()
        self._smooth_combo.addItem("平滑抗锯齿还原 (推荐，画面细腻)", True)
        self._smooth_combo.addItem("原始像素块锐利放大 (看清色块颗粒)", False)
        self._smooth_combo.currentIndexChanged.connect(self._parse_and_render)
        mode_row.addWidget(self._smooth_combo, 1)
        pl.addLayout(mode_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("输出分辨率:"))
        self._size_combo = QComboBox()
        self._size_combo.addItem("512 × 512 (推荐标准尺寸)", 512)
        self._size_combo.addItem("256 × 256", 256)
        self._size_combo.addItem("1024 × 1024 (超清)", 1024)
        self._size_combo.addItem("保持 TXT 原始网格分辨率 (如 150×150)", 0)
        self._size_combo.currentIndexChanged.connect(self._parse_and_render)
        size_row.addWidget(self._size_combo, 1)
        pl.addLayout(size_row)

        pl.addWidget(self._sec_label("3. 保存并关联到工作区"))
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("保存名称:"))
        default_stem = (
            self._source_txt_path.stem
            if self._source_txt_path
            else f"from_txt_{time.strftime('%H%M%S')}"
        )
        self._name_edit = QLineEdit(default_stem)
        name_row.addWidget(self._name_edit, 1)
        pl.addLayout(name_row)

        self._save_txt_chk = QCheckBox("同时保存对应的同名 .txt 文件（实现 原图↔TXT 自动配对）")
        self._save_txt_chk.setChecked(True)
        pl.addWidget(self._save_txt_chk)

        pl.addStretch()

        footer = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        self._save_btn = QPushButton("💾 保存反推生成的图片")
        self._save_btn.setObjectName("PrimaryGoldBtn")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)

        footer.addWidget(cancel_btn)
        footer.addWidget(self._save_btn, 1)
        pl.addLayout(footer)

        root.addWidget(panel)

    @staticmethod
    def _sec_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color: #E6C775; font-weight: 700; font-size: 12.5px; margin-top: 2px;")
        return lbl

    def _update_source_label(self) -> None:
        if self._source_txt_path:
            self._source_lbl.setText(f"当前文件: {self._source_txt_path.name}")
        elif self._current_code:
            self._source_lbl.setText(f"当前来源: 剪贴板纹章代码（共 {len(self._current_code):,} 字符）")
        else:
            self._source_lbl.setText("当前来源: 未载入")

    def _paste_from_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text()
        if not text or "colored_emblem" not in text:
            QMessageBox.warning(
                self,
                "剪贴板中无有效纹章代码",
                "未在剪贴板中检测到 CK3 纹章代码（需包含 colored_emblem={ ... }）。\n"
                "请先复制纹章文本，或点击右侧「📂 选择 .txt 文件...」。",
            )
            return
        self._source_txt_path = None
        self._current_code = text
        self._name_edit.setText(f"from_txt_{time.strftime('%H%M%S')}")
        self._update_source_label()
        self._parse_and_render()

    def _choose_txt_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 CK3 纹章 .txt 文件",
            str(self._workspace_dir),
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not path:
            return
        p = Path(path)
        self._source_txt_path = p
        self._current_code = p.read_text(encoding="utf-8", errors="replace")
        self._name_edit.setText(p.stem)
        self._update_source_label()
        self._parse_and_render()

    def _parse_and_render(self) -> None:
        if not self._current_code:
            return
        head_lines = self._current_code.splitlines()[:35]
        self._code_preview.setPlainText("\n".join(head_lines))

        out_size = int(self._size_combo.currentData())
        smooth = bool(self._smooth_combo.currentData())
        try:
            res = render_coa_txt_string(
                self._current_code,
                output_size=out_size,
                smooth_upscale=smooth,
            )
            self._render_result = res
            pm = pil_to_qpixmap(res.image)
            self._preview.set_pixmap(pm)
            final_w = res.image.width
            self._stats_lbl.setText(
                f"✓ 反推成功！原始清晰度网格: {res.native_grid_size}×{res.native_grid_size} · "
                f"色彩层: {res.color_groups} 色 · 色块总数: {res.total_instances:,} · "
                f"导出尺寸: {final_w}×{final_w} px"
            )
            self._save_btn.setEnabled(True)
        except Exception as exc:
            self._render_result = None
            self._preview.set_pixmap(None)
            self._stats_lbl.setText(f"✕ 解析失败: {exc}")
            self._save_btn.setEnabled(False)

    def _on_save(self) -> None:
        if not self._render_result:
            return
        stem = self._name_edit.text().strip()
        if not stem:
            QMessageBox.warning(self, "提示", "请输入有效的保存名称。")
            return
        invalid = set('<>:"/\\|?*')
        if any(ch in invalid for ch in stem):
            QMessageBox.warning(self, "提示", '文件名不能包含 <>:"/\\|?* 等特殊字符。')
            return

        dest_img = self._workspace_dir / f"{stem}.png"
        if dest_img.exists():
            ans = QMessageBox.question(
                self,
                "图片已存在",
                f"{dest_img.name} 已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

        save_square_image(self._render_result.image, dest_img, "png")

        # Also save or copy the .txt file into workspace if requested and not already at <stem>.txt
        dest_txt = self._workspace_dir / f"{stem}.txt"
        if self._save_txt_chk.isChecked() and self._current_code:
            if not dest_txt.exists() or (
                self._source_txt_path is None
                or self._source_txt_path.resolve() != dest_txt.resolve()
            ):
                dest_txt.write_text(self._current_code, encoding="utf-8")

        self.saved_image_path = dest_img
        self.accept()
