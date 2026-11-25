"""Gallery card widget displaying Image <-> CoA TXT pairing clearly."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.workspace import CoaEntry


class CoaCardWidget(QFrame):
    """Visual card representing a CoA image and its corresponding .txt file."""

    clicked = Signal(str)  # entry_id
    quick_copy = Signal(str)  # entry_id
    quick_convert = Signal(str)  # entry_id

    CARD_WIDTH = 214

    def __init__(
        self,
        entry: CoaEntry,
        thumbnail: Optional[QPixmap] = None,
        selected: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self._selected = selected
        self.setFixedWidth(self.CARD_WIDTH)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_card_style()

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # Thumbnail container with clean dark surface
        thumb_wrap = QWidget(self)
        thumb_wrap.setFixedSize(192, 166)
        thumb_wrap.setStyleSheet("background: #101318; border-radius: 8px;")

        thumb_label = QLabel(thumb_wrap)
        thumb_label.setGeometry(0, 0, 192, 166)
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumbnail and not thumbnail.isNull():
            scaled = thumbnail.scaled(
                182,
                156,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb_label.setPixmap(scaled)
        else:
            thumb_label.setText("📜\n仅 TXT 代码")
            thumb_label.setStyleSheet("color: #7D8B9E; font-size: 13px; font-weight: 600;")

        # Top-left status pill (subtle dark-tinted pills)
        status_badge = QLabel(thumb_wrap)
        if entry.is_paired:
            status_badge.setText("✓ 已关联")
            status_badge.setStyleSheet(
                "background: rgba(16, 46, 36, 225); color: #86EFAC; "
                "border: 1px solid rgba(52, 211, 153, 140); border-radius: 8px; "
                "padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )
        elif entry.has_image:
            status_badge.setText("○ 待生成")
            status_badge.setStyleSheet(
                "background: rgba(28, 32, 41, 225); color: #A6B0C0; "
                "border: 1px solid rgba(100, 116, 139, 130); border-radius: 8px; "
                "padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )
        else:
            status_badge.setText("📄 仅TXT")
            status_badge.setStyleSheet(
                "background: rgba(24, 38, 58, 225); color: #93C5FD; "
                "border: 1px solid rgba(96, 165, 250, 130); border-radius: 8px; "
                "padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )
        status_badge.adjustSize()
        status_badge.move(7, 7)

        # Top-right non-square badge
        if entry.has_image and entry.image_width > 0 and not entry.is_square:
            sq_badge = QLabel("⚠ 非1:1", thumb_wrap)
            sq_badge.setStyleSheet(
                "background: rgba(68, 42, 12, 225); color: #FCD34D; "
                "border: 1px solid rgba(245, 158, 11, 140); border-radius: 8px; "
                "padding: 2px 7px; font-size: 11px; font-weight: 600;"
            )
            sq_badge.adjustSize()
            sq_badge.move(192 - sq_badge.width() - 7, 7)

        root.addWidget(thumb_wrap)

        # Stem title
        title = QLabel(self._elide(entry.stem, 24))
        title.setToolTip(entry.stem)
        title.setStyleSheet("font-weight: 700; font-size: 13px; color: #F1EFEA; background: transparent;")
        root.addWidget(title)

        # Explicit pairing rows: Image <-> TXT
        img_line = QLabel()
        img_line.setStyleSheet("font-size: 11px; color: #8E96A4; background: transparent;")
        if entry.has_image and entry.image_path:
            dim = f"{entry.image_width}×{entry.image_height}" if entry.image_width else "?"
            img_line.setText(f"🖼 {self._elide(entry.image_path.name, 16)} · {dim}")
            img_line.setToolTip(entry.image_path.name)
        else:
            img_line.setText("🖼 无对应原图")
        root.addWidget(img_line)

        txt_line = QLabel()
        if entry.has_txt and entry.txt_path and entry.txt_meta:
            txt_line.setStyleSheet("font-size: 11px; color: #6EE7B7; background: transparent;")
            txt_line.setText(
                f"📜 {self._elide(entry.txt_path.name, 15)} · {entry.txt_meta.size_str}"
            )
            txt_line.setToolTip(
                f"对应纹章文件: {entry.txt_path.name}\n"
                f"类型: {entry.txt_meta.coa_kind_label}\n"
                f"行数: {entry.txt_meta.line_count:,}"
            )
        else:
            txt_line.setStyleSheet("font-size: 11px; color: #636B7A; background: transparent;")
            txt_line.setText("📜 尚未生成 .txt")
        root.addWidget(txt_line)

        # Quick action button
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        if entry.has_txt:
            quick_btn = QPushButton("📋 复制纹章文本")
            quick_btn.setStyleSheet(
                "QPushButton { background: #173229; border: 1px solid #265444; "
                "color: #C6F6D5; border-radius: 7px; padding: 5px 8px; font-size: 11.5px; font-weight: 600; }"
                "QPushButton:hover { background: #1E4236; border-color: #35755E; }"
            )
            quick_btn.clicked.connect(lambda: self.quick_copy.emit(self.entry.entry_id))
            btn_row.addWidget(quick_btn)
        else:
            quick_btn = QPushButton("⚡ 生成 TXT")
            quick_btn.setStyleSheet(
                "QPushButton { background: #262117; border: 1px solid #6E5826; "
                "color: #F3DA91; border-radius: 7px; padding: 5px 8px; font-size: 11.5px; font-weight: 600; }"
                "QPushButton:hover { background: #332C1D; border-color: #D9B45A; }"
            )
            quick_btn.clicked.connect(lambda: self.quick_convert.emit(self.entry.entry_id))
            btn_row.addWidget(quick_btn)
        root.addLayout(btn_row)

    @staticmethod
    def _elide(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_card_style()

    def _apply_card_style(self) -> None:
        if self._selected:
            self.setStyleSheet(
                "CoaCardWidget { background-color: #1D212B; "
                "border: 1.5px solid #D9B45A; border-radius: 11px; }"
            )
        else:
            self.setStyleSheet(
                "CoaCardWidget { background-color: #161920; "
                "border: 1px solid #232833; border-radius: 11px; }"
                "CoaCardWidget:hover { border-color: #424959; background-color: #1A1E27; }"
            )

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.entry.entry_id)
        super().mousePressEvent(event)
