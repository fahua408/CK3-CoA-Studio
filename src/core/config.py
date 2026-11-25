"""Configuration management and path discovery for CK3 CoA Studio."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional


def get_app_root() -> Path:
    """Return the root directory of the running application or script."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_resource_path(relative_path: str) -> Path:
    """Resolve bundled asset paths for both source and PyInstaller builds."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parents[2]
    return base / relative_path


def get_config_file() -> Path:
    """Return persistent user config file path under AppData (Windows) or home."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        cfg_dir = Path(appdata) / "CK3CoAStudio"
    else:
        cfg_dir = Path.home() / ".ck3_coa_studio"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.json"


def discover_converter(workspace_dir: Optional[str] = None) -> str:
    """Locate coaConverter_windows.exe automatically from common locations."""
    candidates: list[Path] = []
    if workspace_dir:
        candidates.append(Path(workspace_dir) / "coaConverter_windows.exe")

    app_root = get_app_root()
    candidates.extend(
        [
            app_root / "coaConverter_windows.exe",
            app_root.parent / "coaConverter_windows.exe",
            Path(r"E:\wenzhang\coaConverter_windows.exe"),
        ]
    )

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    in_path = shutil.which("coaConverter_windows.exe")
    return in_path or ""


def discover_default_workspace() -> str:
    """Pick a sensible initial workspace folder."""
    app_root = get_app_root()
    if (app_root.parent / "coaConverter_windows.exe").is_file():
        return str(app_root.parent)
    if Path(r"E:\wenzhang").is_dir():
        return r"E:\wenzhang"
    pictures = Path.home() / "Pictures"
    if pictures.is_dir():
        return str(pictures)
    return str(Path.home())


@dataclass
class AppConfig:
    """Persistent application preferences."""

    workspace_dir: str = ""
    converter_path: str = ""
    default_resolution: int = 150
    default_color_mode: str = "Reduced"
    default_color_limit: int = 20
    default_landed_title: bool = False
    screenshot_open_editor: bool = True
    editor_auto_convert: bool = True
    screenshot_hotkey: str = "Ctrl+Shift+A"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load configuration from disk, filling missing paths automatically."""
        cfg_file = get_config_file()
        data: dict = {}
        if cfg_file.is_file():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}

        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        cfg = cls(**filtered)

        if not cfg.workspace_dir or not Path(cfg.workspace_dir).is_dir():
            cfg.workspace_dir = discover_default_workspace()
        if not cfg.converter_path or not Path(cfg.converter_path).is_file():
            cfg.converter_path = discover_converter(cfg.workspace_dir)

        return cfg

    def save(self) -> None:
        """Persist configuration to disk."""
        cfg_file = get_config_file()
        cfg_file.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
