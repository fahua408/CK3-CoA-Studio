"""Reverse renderer: converts CK3 Coat of Arms .txt scripts back into 1:1 images."""

from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

CK3_NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "white": (242, 238, 230),
    "silver": (210, 208, 204),
    "grey": (128, 128, 128),
    "gray": (128, 128, 128),
    "black": (22, 22, 24),
    "red": (172, 28, 34),
    "red_dark": (112, 16, 20),
    "red_light": (214, 68, 72),
    "blue": (28, 68, 138),
    "blue_dark": (16, 38, 84),
    "blue_light": (78, 136, 210),
    "yellow": (228, 184, 52),
    "yellow_light": (245, 214, 108),
    "gold": (217, 175, 55),
    "green": (34, 118, 62),
    "green_dark": (18, 72, 36),
    "green_light": (82, 168, 104),
    "purple": (116, 38, 132),
    "orange": (216, 108, 32),
    "brown": (118, 72, 38),
}

_RGB_BRACE_RE = re.compile(
    r"color1\s*=\s*(?:rgb\s*)?\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}",
    re.IGNORECASE,
)
_HSV_BRACE_RE = re.compile(
    r"color1\s*=\s*(hsv360|hsv)\s*\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}",
    re.IGNORECASE,
)
_NAMED_COLOR_RE = re.compile(r'color1\s*=\s*"?([A-Za-z_][A-Za-z0-9_]*)"?', re.IGNORECASE)

_INST_FAST_RE = re.compile(
    r"position\s*=\s*\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}\s*"
    r"scale\s*=\s*\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}"
)
_INST_BLOCK_RE = re.compile(r"instance\s*=\s*\{([^}]*)\}")
_POS_SINGLE_RE = re.compile(r"position\s*=\s*\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}")
_SCALE_SINGLE_RE = re.compile(r"scale\s*=\s*\{\s*([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)\s*\}")


@dataclass
class TxtRenderResult:
    """Output of reverse-rendering a CK3 CoA .txt script."""

    image: Image.Image
    native_grid_size: int
    color_groups: int
    total_instances: int


def parse_coa_color(text_chunk: str, fallback: tuple[int, int, int] = (28, 32, 40)) -> tuple[int, int, int]:
    """Parse color1 from a CK3 CoA header or colored_emblem chunk."""
    m_rgb = _RGB_BRACE_RE.search(text_chunk)
    if m_rgb:
        r_s, g_s, b_s = m_rgb.group(1), m_rgb.group(2), m_rgb.group(3)
        r_f, g_f, b_f = float(r_s), float(g_s), float(b_s)
        if ("." in r_s or "." in g_s or "." in b_s) and max(r_f, g_f, b_f) <= 1.0:
            return (
                max(0, min(255, round(r_f * 255))),
                max(0, min(255, round(g_f * 255))),
                max(0, min(255, round(b_f * 255))),
            )
        return (
            max(0, min(255, round(r_f))),
            max(0, min(255, round(g_f))),
            max(0, min(255, round(b_f))),
        )

    m_hsv = _HSV_BRACE_RE.search(text_chunk)
    if m_hsv:
        mode = m_hsv.group(1).lower()
        h, s, v = float(m_hsv.group(2)), float(m_hsv.group(3)), float(m_hsv.group(4))
        if mode == "hsv360" or h > 1.0:
            h = (h % 360.0) / 360.0
        if s > 1.0:
            s /= 100.0
        if v > 1.0:
            v /= 100.0
        r, g, b = colorsys.hsv_to_rgb(max(0.0, min(1.0, h)), max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
        return (round(r * 255), round(g * 255), round(b * 255))

    m_named = _NAMED_COLOR_RE.search(text_chunk)
    if m_named:
        cname = m_named.group(1).lower()
        if cname not in ("rgb", "hsv", "hsv360"):
            return CK3_NAMED_COLORS.get(cname, fallback)

    return fallback


def render_coa_txt_string(
    coa_text: str,
    output_size: int = 512,
    smooth_upscale: bool = True,
) -> TxtRenderResult:
    """Reverse-render a CK3 CoA script string into a 1:1 PIL Image."""
    parts = coa_text.split("colored_emblem")
    if len(parts) < 2:
        raise ValueError("未在文本中检测到有效的 CK3 纹章 colored_emblem 代码块。")

    bg_color = parse_coa_color(parts[0], fallback=(28, 32, 40))

    groups: list[tuple[tuple[int, int, int], list[tuple[float, float, float, float]]]] = []
    min_scale = 1.0
    total_instances = 0

    for chunk in parts[1:]:
        col = parse_coa_color(chunk[:240], fallback=(230, 230, 230))
        fast_matches = _INST_FAST_RE.findall(chunk)
        parsed_insts: list[tuple[float, float, float, float]] = []

        if fast_matches:
            for xs, ys, sxs, sys_ in fast_matches:
                sx = abs(float(sxs))
                sy = abs(float(sys_))
                parsed_insts.append((float(xs), float(ys), sx, sy))
                if 0.0005 < sx < min_scale:
                    min_scale = sx
                if 0.0005 < sy < min_scale:
                    min_scale = sy
        else:
            # Fallback for non-standard instance ordering
            for m_blk in _INST_BLOCK_RE.finditer(chunk):
                body = m_blk.group(1)
                mp = _POS_SINGLE_RE.search(body)
                ms = _SCALE_SINGLE_RE.search(body)
                px = float(mp.group(1)) if mp else 0.0
                py = float(mp.group(2)) if mp else 0.0
                sx = abs(float(ms.group(1))) if ms else 0.01
                sy = abs(float(ms.group(2))) if ms else 0.01
                parsed_insts.append((px, py, sx, sy))
                if 0.0005 < sx < min_scale:
                    min_scale = sx

        if parsed_insts:
            groups.append((col, parsed_insts))
            total_instances += len(parsed_insts)

    if total_instances == 0:
        raise ValueError("未能在纹章代码中解析出任何有效的像素坐标 (instance)。")

    grid_n = max(16, min(1024, round(1.0 / min_scale)))
    canvas = Image.new("RGB", (grid_n, grid_n), bg_color)
    px_access = canvas.load()
    draw = ImageDraw.Draw(canvas)

    for col, insts in groups:
        for xf, yf, sxf, syf in insts:
            x0 = round(xf * grid_n)
            y0 = round(yf * grid_n)
            w = max(1, round(sxf * grid_n))
            h = max(1, round(syf * grid_n))
            if w == 1 and h == 1:
                if 0 <= x0 < grid_n and 0 <= y0 < grid_n:
                    px_access[x0, y0] = col
            else:
                x1 = min(grid_n - 1, max(0, x0 + w - 1))
                y1 = min(grid_n - 1, max(0, y0 + h - 1))
                x0_c = max(0, min(grid_n - 1, x0))
                y0_c = max(0, min(grid_n - 1, y0))
                draw.rectangle((x0_c, y0_c, x1, y1), fill=col)

    out_img = canvas.convert("RGBA")
    if output_size > 0 and output_size != grid_n:
        resample = (
            Image.Resampling.LANCZOS if smooth_upscale else Image.Resampling.NEAREST
        )
        out_img = out_img.resize((output_size, output_size), resample)

    return TxtRenderResult(
        image=out_img,
        native_grid_size=grid_n,
        color_groups=len(groups),
        total_instances=total_instances,
    )


def render_coa_txt_file(
    txt_path: Path,
    output_size: int = 512,
    smooth_upscale: bool = True,
) -> TxtRenderResult:
    """Reverse-render a CK3 CoA .txt file from disk into a 1:1 PIL Image."""
    raw = txt_path.read_text(encoding="utf-8", errors="replace")
    return render_coa_txt_string(raw, output_size=output_size, smooth_upscale=smooth_upscale)
