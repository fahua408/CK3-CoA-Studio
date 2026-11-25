"""Application entry point for CK3 CoA Studio."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

# Ensure project root is importable when launched via `python src/main.py`
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src import APP_NAME, __version__
from src.core.config import AppConfig, get_resource_path
from src.ui.main_window import MainWindow
from src.ui.theme import DARK_GOLD_QSS


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_GOLD_QSS)

    icon_path = get_resource_path("assets/app_icon.ico")
    if not icon_path.is_file():
        icon_path = get_resource_path("assets/app_icon.png")
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = AppConfig.load()
    window = MainWindow(config)
    window.show()
    if config.show_tutorial_on_startup:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(300, window.open_tutorial_first_launch)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
