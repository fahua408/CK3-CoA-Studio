"""Theme stylesheet and Qt/Pillow conversion utilities."""

from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

DARK_GOLD_QSS = """
QWidget {
    background-color: #0F1115;
    color: #F1EFEA;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #0F1115;
}

QLabel, QCheckBox {
    background-color: transparent;
}

QFrame#TopBar {
    background-color: #15181E;
    border-bottom: 1px solid #232833;
}

QFrame#PanelCard {
    background-color: #171A21;
    border: 1px solid #252A35;
    border-radius: 12px;
}

QFrame#PairBanner {
    background-color: #181C24;
    border: 1px solid #2E333F;
    border-radius: 12px;
}

QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {
    background-color: #101318;
    border: 1px solid #282E3A;
    border-radius: 7px;
    padding: 6px 10px;
    color: #F1EFEA;
    selection-background-color: #D9B45A;
    selection-color: #111317;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #D9B45A;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #171A21;
    border: 1px solid #2D3340;
    selection-background-color: #2A251A;
    selection-color: #F3DA91;
    outline: none;
}

QPushButton {
    background-color: #20242E;
    border: 1px solid #2E3442;
    border-radius: 8px;
    padding: 6px 14px;
    color: #E6E3DC;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #282D39;
    border-color: #3D4557;
}

QPushButton:pressed {
    background-color: #1A1E26;
}

QPushButton:disabled {
    background-color: #15181E;
    color: #5E6675;
    border-color: #222630;
}

QPushButton#PrimaryGoldBtn {
    background-color: #D9B45A;
    border: 1px solid #E6C775;
    color: #121418;
    font-weight: 700;
    padding: 8px 16px;
}

QPushButton#PrimaryGoldBtn:hover {
    background-color: #E5C36D;
}

QPushButton#PrimaryGoldBtn:pressed {
    background-color: #C49E44;
}

QPushButton#CopyBtn {
    background-color: #1A3A2F;
    border: 1px solid #2B624E;
    color: #D1FAE5;
    font-weight: 700;
    padding: 9px 16px;
}

QPushButton#CopyBtn:hover {
    background-color: #21493B;
    border-color: #397E65;
}

QPushButton#DangerBtn {
    background-color: #2C1B1E;
    border: 1px solid #572D34;
    color: #FCA5A5;
}

QPushButton#DangerBtn:hover {
    background-color: #3B2226;
    border-color: #783B45;
}

QPushButton[filterChip="true"] {
    background-color: #171A21;
    border: 1px solid #262B36;
    border-radius: 14px;
    padding: 5px 13px;
    color: #9BA3B2;
    font-size: 12px;
}

QPushButton[filterChip="true"]:hover {
    border-color: #464B58;
    color: #F1EFEA;
}

QPushButton[filterChip="true"]:checked {
    background-color: #262117;
    border-color: #D9B45A;
    color: #F3DA91;
    font-weight: 600;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #262B36;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #D9B45A;
    border: 2px solid #0F1115;
    width: 15px;
    height: 15px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::sub-page:horizontal {
    background: #C49E44;
    border-radius: 2px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background: #0F1115;
    width: 8px;
    margin: 2px 0;
}

QScrollBar::handle:vertical {
    background: #2C313D;
    min-height: 28px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #40485A;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QCheckBox {
    spacing: 7px;
    color: #E6E3DC;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3D4557;
    background: #101318;
}

QCheckBox::indicator:checked {
    background: #D9B45A;
    border-color: #E6C775;
}

QLabel#MutedLabel {
    color: #8E96A4;
    font-size: 12px;
}

QLabel#GoldTitle {
    color: #E6C775;
    font-weight: 700;
    font-size: 13.5px;
}

QStatusBar {
    background-color: #15181E;
    border-top: 1px solid #232833;
    color: #9BA3B2;
    font-size: 12px;
}
"""


def pil_to_qpixmap(img: Image.Image) -> QPixmap:
    """Convert a PIL Image safely to QPixmap via raw RGBA buffer."""
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(
        data,
        rgba.width,
        rgba.height,
        rgba.width * 4,
        QImage.Format.Format_RGBA8888,
    )
    return QPixmap.fromImage(qimg.copy())
