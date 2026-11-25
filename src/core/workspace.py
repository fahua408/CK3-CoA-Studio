"""Workspace scanning, image<->txt pairing, and CK3 CoA metadata parsing."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class TxtMetadata:
    """Lightweight summary of a CK3 CoA text file."""

    path: Path
    size_bytes: int
    line_count: int
    modified_ts: float
    coa_kind: str  # "dynasty" | "title" | "coa" | "other"
    coa_kind_label: str
    preview_lines: list[str]

    @property
    def modified_str(self) -> str:
        return datetime.fromtimestamp(self.modified_ts).strftime("%Y-%m-%d %H:%M")

    @property
    def size_str(self) -> str:
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        if self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        return f"{self.size_bytes / (1024 * 1024):.2f} MB"

    @property
    def is_valid_coa(self) -> bool:
        return self.coa_kind in {"dynasty", "title", "coa"}


@dataclass
class CoaEntry:
    """Represents a paired (Image <-> CoA TXT) item or a standalone item."""

    stem: str
    image_path: Optional[Path] = None
    image_width: int = 0
    image_height: int = 0
    image_size_bytes: int = 0
    txt_path: Optional[Path] = None
    txt_meta: Optional[TxtMetadata] = None
    duplicate_stem_count: int = 1

    @property
    def entry_id(self) -> str:
        if self.image_path:
            return str(self.image_path)
        return str(self.txt_path)

    @property
    def has_image(self) -> bool:
        return self.image_path is not None and self.image_path.is_file()

    @property
    def has_txt(self) -> bool:
        return self.txt_path is not None and self.txt_path.is_file()

    @property
    def is_paired(self) -> bool:
        return self.has_image and self.has_txt

    @property
    def is_square(self) -> bool:
        return self.image_width > 0 and self.image_width == self.image_height

    @property
    def image_size_str(self) -> str:
        if self.image_size_bytes < 1024:
            return f"{self.image_size_bytes} B"
        if self.image_size_bytes < 1024 * 1024:
            return f"{self.image_size_bytes / 1024:.1f} KB"
        return f"{self.image_size_bytes / (1024 * 1024):.2f} MB"

    @property
    def expected_txt_path(self) -> Optional[Path]:
        if self.txt_path:
            return self.txt_path
        if self.image_path:
            return self.image_path.with_suffix(".txt")
        return None


def inspect_txt_file(txt_path: Path, max_preview_lines: int = 40) -> TxtMetadata:
    """Read lightweight metadata and first lines of a CoA txt without choking on 70k+ lines."""
    stat = txt_path.stat()
    preview_lines: list[str] = []
    line_count = 0

    with txt_path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 256)
            if not chunk:
                break
            line_count += chunk.count(b"\n")

    # Handle trailing line without newline
    if stat.st_size > 0:
        with txt_path.open("rb") as f:
            f.seek(-1, 2)
            if f.read(1) != b"\n":
                line_count += 1

    with txt_path.open("r", encoding="utf-8", errors="replace") as f:
        for _ in range(max_preview_lines):
            line = f.readline()
            if not line:
                break
            preview_lines.append(line.rstrip("\r\n"))

    first_non_empty = next((ln.strip() for ln in preview_lines if ln.strip()), "")
    if first_non_empty.startswith("coa_rd_dynasty"):
        coa_kind = "dynasty"
        coa_kind_label = "家族/宗族纹章"
    elif first_non_empty.startswith("coa_title"):
        coa_kind = "title"
        coa_kind_label = "领地头衔纹章"
    elif first_non_empty.startswith("coa_") or (
        len(preview_lines) > 2 and "colored_emblem" in "\n".join(preview_lines[:15])
    ):
        coa_kind = "coa"
        coa_kind_label = "CK3 纹章代码"
    else:
        coa_kind = "other"
        coa_kind_label = "普通文本"

    return TxtMetadata(
        path=txt_path,
        size_bytes=stat.st_size,
        line_count=line_count,
        modified_ts=stat.st_mtime,
        coa_kind=coa_kind,
        coa_kind_label=coa_kind_label,
        preview_lines=preview_lines,
    )


def scan_workspace(workspace_dir: Path) -> list[CoaEntry]:
    """Scan workspace directory and pair images with matching <stem>.txt files."""
    if not workspace_dir.is_dir():
        return []

    images_by_stem: dict[str, list[Path]] = {}
    txts_by_stem: dict[str, Path] = {}

    for item in workspace_dir.iterdir():
        if not item.is_file():
            continue
        suffix = item.suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            images_by_stem.setdefault(item.stem, []).append(item)
        elif suffix == ".txt":
            txts_by_stem[item.stem] = item

    txt_meta_cache: dict[Path, TxtMetadata] = {}

    def get_txt_meta(path: Path) -> TxtMetadata:
        if path not in txt_meta_cache:
            txt_meta_cache[path] = inspect_txt_file(path)
        return txt_meta_cache[path]

    entries: list[CoaEntry] = []

    for stem, img_paths in images_by_stem.items():
        paired_txt = txts_by_stem.get(stem)
        txt_meta = get_txt_meta(paired_txt) if paired_txt else None
        for img_path in sorted(img_paths, key=lambda p: p.name.lower()):
            width, height = 0, 0
            try:
                with Image.open(img_path) as im:
                    width, height = im.size
            except Exception:
                width, height = 0, 0

            entries.append(
                CoaEntry(
                    stem=stem,
                    image_path=img_path,
                    image_width=width,
                    image_height=height,
                    image_size_bytes=img_path.stat().st_size,
                    txt_path=paired_txt,
                    txt_meta=txt_meta,
                    duplicate_stem_count=len(img_paths),
                )
            )

    # Orphan TXT files (no image with matching stem)
    for stem, txt_path in txts_by_stem.items():
        if stem not in images_by_stem:
            entries.append(
                CoaEntry(
                    stem=stem,
                    txt_path=txt_path,
                    txt_meta=get_txt_meta(txt_path),
                )
            )

    # Sort: paired first, then pending images, then orphan TXTs; within each, by latest mtime desc
    def sort_key(e: CoaEntry) -> tuple[int, float, str]:
        if e.is_paired:
            group = 0
        elif e.has_image:
            group = 1
        else:
            group = 2
        mtime = 0.0
        if e.txt_path and e.txt_path.exists():
            mtime = max(mtime, e.txt_path.stat().st_mtime)
        if e.image_path and e.image_path.exists():
            mtime = max(mtime, e.image_path.stat().st_mtime)
        return (group, -mtime, e.stem.lower())

    entries.sort(key=sort_key)
    return entries


def read_txt_full(txt_path: Path) -> str:
    """Read full text content for clipboard copy."""
    return txt_path.read_text(encoding="utf-8", errors="replace")


def rename_entry(entry: CoaEntry, new_stem: str) -> tuple[Optional[Path], Optional[Path]]:
    """Rename image and/or paired txt cleanly to new_stem, checking for collisions."""
    clean_stem = new_stem.strip()
    if not clean_stem:
        raise ValueError("名称不能为空")
    invalid_chars = set('<>:"/\\|?*')
    if any(ch in invalid_chars for ch in clean_stem):
        raise ValueError('文件名不能包含 <>:"/\\|?* 等特殊字符')

    new_img: Optional[Path] = None
    new_txt: Optional[Path] = None

    if entry.has_image and entry.image_path:
        target_img = entry.image_path.with_stem(clean_stem)
        if target_img != entry.image_path and target_img.exists():
            raise FileExistsError(f"目标图片已存在: {target_img.name}")
        new_img = target_img

    if entry.has_txt and entry.txt_path:
        target_txt = entry.txt_path.with_stem(clean_stem)
        if target_txt != entry.txt_path and target_txt.exists():
            raise FileExistsError(f"目标文本已存在: {target_txt.name}")
        new_txt = target_txt

    if new_img and entry.image_path and new_img != entry.image_path:
        entry.image_path.rename(new_img)
    if new_txt and entry.txt_path and new_txt != entry.txt_path:
        entry.txt_path.rename(new_txt)

    return new_img, new_txt


def move_to_recycle_bin(paths: list[Path]) -> None:
    """Send files to Windows Recycle Bin when available; fallback to unlink."""
    existing = [str(p.resolve()) for p in paths if p.exists()]
    if not existing:
        return

    if hasattr(ctypes, "windll"):
        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 3
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        p_from = "\0".join(existing) + "\0\0"
        op = SHFILEOPSTRUCTW(
            hwnd=None,
            wFunc=FO_DELETE,
            pFrom=p_from,
            pTo=None,
            fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT,
            fAnyOperationsAborted=False,
            hNameMappings=None,
            lpszProgressTitle=None,
        )
        res = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        if res == 0:
            return

    for p in paths:
        if p.exists():
            p.unlink()
