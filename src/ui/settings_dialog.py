"""Settings dialog for converter executable and default workflow preferences."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.config import AppConfig, discover_converter
from src.core.converter import COLOR_MODES


class SettingsDialog(QDialog):
    """Preferences dialog for CK3 CoA Studio."""

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置 — CK3 纹章工坊")
        self.resize(540, 340)
        self._config = config
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        # Converter path
        conv_row = QHBoxLayout()
        self._conv_edit = QLineEdit(self._config.converter_path)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_converter)
        detect_btn = QPushButton("自动探测")
        detect_btn.clicked.connect(self._auto_detect)
        conv_row.addWidget(self._conv_edit, 1)
        conv_row.addWidget(browse_btn)
        conv_row.addWidget(detect_btn)
        form.addRow("转换器路径 (.exe):", conv_row)

        # Default -r
        self._res_spin = QSpinBox()
        self._res_spin.setRange(20, 400)
        self._res_spin.setValue(self._config.default_resolution)
        form.addRow("默认清晰度 (-r):", self._res_spin)

        # Default -c & -k
        color_row = QHBoxLayout()
        self._mode_combo = QComboBox()
        for m in COLOR_MODES:
            self._mode_combo.addItem(m, m)
        idx = self._mode_combo.findData(self._config.default_color_mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(2, 256)
        self._limit_spin.setValue(self._config.default_color_limit)
        color_row.addWidget(self._mode_combo)
        color_row.addWidget(QLabel("颜色上限 (-k):"))
        color_row.addWidget(self._limit_spin)
        color_row.addStretch()
        form.addRow("默认色彩模式 (-c):", color_row)

        self._title_chk = QCheckBox("默认勾选领地头衔纹章 (-t)")
        self._title_chk.setChecked(self._config.default_landed_title)
        form.addRow("", self._title_chk)

        self._shot_editor_chk = QCheckBox("正方形截图后先打开 1:1 图片编辑器（取消则直接保存）")
        self._shot_editor_chk.setChecked(self._config.screenshot_open_editor)
        form.addRow("截图工作流:", self._shot_editor_chk)

        self._auto_conv_chk = QCheckBox("编辑器保存后默认立即生成 TXT")
        self._auto_conv_chk.setChecked(self._config.editor_auto_convert)
        form.addRow("", self._auto_conv_chk)

        root.addLayout(form)
        root.addStretch()

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        save = QPushButton("保存设置")
        save.setObjectName("PrimaryGoldBtn")
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

    def _browse_converter(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 coaConverter_windows.exe",
            self._conv_edit.text() or self._config.workspace_dir,
            "Executable (*.exe);;All Files (*.*)",
        )
        if path:
            self._conv_edit.setText(path)

    def _auto_detect(self) -> None:
        found = discover_converter(self._config.workspace_dir)
        if found:
            self._conv_edit.setText(found)
            QMessageBox.information(self, "已找到", f"已定位转换器:\n{found}")
        else:
            QMessageBox.warning(self, "未找到", "未能自动探测到 coaConverter_windows.exe，请手动浏览选择。")

    def _on_save(self) -> None:
        conv_text = self._conv_edit.text().strip()
        if conv_text and not Path(conv_text).is_file():
            QMessageBox.warning(self, "路径无效", f"找不到转换器文件:\n{conv_text}")
            return

        self._config.converter_path = conv_text
        self._config.default_resolution = self._res_spin.value()
        self._config.default_color_mode = str(self._mode_combo.currentData())
        self._config.default_color_limit = self._limit_spin.value()
        self._config.default_landed_title = self._title_chk.isChecked()
        self._config.screenshot_open_editor = self._shot_editor_chk.isChecked()
        self._config.editor_auto_convert = self._auto_conv_chk.isChecked()
        self._config.save()
        self.accept()
