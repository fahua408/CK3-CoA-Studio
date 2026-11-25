"""Multi-CoA Heraldic Composite Engine (Spanish 6-in-1, Hanover 3-way, Savoy 9-in-1, Quartered, Impaled) and native TXT CoA code merger."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image, ImageColor, ImageDraw

from src.core.image_ops import load_oriented_rgba


@dataclass
class SlotDefinition:
    """Normalized geometry definition for a single heraldic slot in [0.0, 1.0]."""

    slot_id: str
    label: str
    shape: str  # "polygon" | "granada_point" | "escutcheon"
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    polygon: list[tuple[float, float]] = field(default_factory=list)
    is_overlay: bool = False
    default_bg: str = "#1C2230"


@dataclass
class HeraldicTemplate:
    """Defines a multi-emblem heraldic layout template."""

    template_id: str
    name: str
    subtitle: str
    slots: list[SlotDefinition]


@dataclass
class SlotImageState:
    """User image and transform assigned to a template slot."""

    image_path: Optional[Path] = None
    pil_image: Optional[Image.Image] = None
    zoom: float = 1.0  # 0.4 .. 3.0
    offset_x: float = 0.0  # -1.0 .. 1.0 (fraction of slot width)
    offset_y: float = 0.0  # -1.0 .. 1.0 (fraction of slot height)
    fit_mode: str = "cover"  # "cover" | "contain"
    bg_color: str = "#1B2230"


@dataclass
class CompositeStyle:
    """Global styling options for a multi-emblem heraldic composite."""

    border_width: int = 6  # px at 512x512 reference
    border_color: str = "#D9B45A"
    escutcheon_shape: str = "shield"  # "shield" | "oval" | "circle"
    escutcheon_ring_width: int = 10
    escutcheon_ring_color: str = "#A82028"
    outer_shield_frame: bool = False
    canvas_bg_color: str = "#12151C"


HERALDIC_TEMPLATES: list[HeraldicTemplate] = [
    HeraldicTemplate(
        template_id="spanish_6",
        name="西班牙王室六合一（四分 + 底部格拉纳达尖角 + 中央小盾）",
        subtitle="还原图1：卡斯蒂利亚 / 莱昂 / 阿拉贡 / 纳瓦拉 + 底部石榴尖角 + 中央波旁小盾",
        slots=[
            SlotDefinition(
                slot_id="q1",
                label="① 左上主区（如：卡斯蒂利亚）",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 0.5),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
                default_bg="#9E1B24",
            ),
            SlotDefinition(
                slot_id="q2",
                label="② 右上主区（如：莱昂）",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 0.5),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)],
                default_bg="#EAE6DF",
            ),
            SlotDefinition(
                slot_id="q3",
                label="③ 左下主区（如：阿拉贡）",
                shape="polygon",
                bbox=(0.0, 0.5, 0.5, 1.0),
                polygon=[(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)],
                default_bg="#D9A72A",
            ),
            SlotDefinition(
                slot_id="q4",
                label="④ 右下主区（如：纳瓦拉）",
                shape="polygon",
                bbox=(0.5, 0.5, 1.0, 1.0),
                polygon=[(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)],
                default_bg="#8C1820",
            ),
            SlotDefinition(
                slot_id="point",
                label="⑤ 底部镶嵌尖角（如：格拉纳达）",
                shape="granada_point",
                bbox=(0.33, 0.68, 0.67, 1.0),
                is_overlay=True,
                default_bg="#ECE7DC",
            ),
            SlotDefinition(
                slot_id="center",
                label="⑥ 中央核心小盾（如：法兰西波旁）",
                shape="escutcheon",
                bbox=(0.33, 0.31, 0.67, 0.69),
                is_overlay=True,
                default_bg="#183A7A",
            ),
        ],
    ),
    HeraldicTemplate(
        template_id="hanover_4",
        name="汉诺威三分 + 中央小盾（左右双区 + 底部三角区 + 中央小盾）",
        subtitle="还原图2：左区双狮 / 右区蓝狮 / 底部白马三角区 + 正中央皇冠小盾",
        slots=[
            SlotDefinition(
                slot_id="left",
                label="① 左主区（如：英格兰/诺曼底）",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 0.86),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.55), (0.0, 0.86)],
                default_bg="#A62126",
            ),
            SlotDefinition(
                slot_id="right",
                label="② 右主区（如：吕讷堡蓝狮）",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 0.86),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.86), (0.5, 0.55)],
                default_bg="#E5B94C",
            ),
            SlotDefinition(
                slot_id="bottom",
                label="③ 底部三角大区（如：萨克森白马）",
                shape="polygon",
                bbox=(0.0, 0.55, 1.0, 1.0),
                polygon=[(0.0, 0.86), (0.5, 0.55), (1.0, 0.86), (1.0, 1.0), (0.0, 1.0)],
                default_bg="#961C22",
            ),
            SlotDefinition(
                slot_id="center",
                label="④ 中央核心小盾（如：帝国皇冠徽）",
                shape="escutcheon",
                bbox=(0.33, 0.32, 0.67, 0.70),
                is_overlay=True,
                default_bg="#B8232A",
            ),
        ],
    ),
    HeraldicTemplate(
        template_id="savoy_9",
        name="帝国九区大复合（左右六格 + 上下楔形三角 + 中央核心盾）",
        subtitle="还原图3：左右各三格领地 + 顶部神罗鹰三角 + 底部新月三角 + 中央十字盾",
        slots=[
            SlotDefinition(
                slot_id="l1",
                label="① 左上领地格",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 0.34),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.34), (0.0, 0.34)],
                default_bg="#F0ECE1",
            ),
            SlotDefinition(
                slot_id="l2",
                label="② 左中领地格",
                shape="polygon",
                bbox=(0.0, 0.34, 0.5, 0.67),
                polygon=[(0.0, 0.34), (0.5, 0.34), (0.5, 0.67), (0.0, 0.67)],
                default_bg="#1E4B8F",
            ),
            SlotDefinition(
                slot_id="l3",
                label="③ 左下领地格",
                shape="polygon",
                bbox=(0.0, 0.67, 0.5, 1.0),
                polygon=[(0.0, 0.67), (0.5, 0.67), (0.5, 1.0), (0.0, 1.0)],
                default_bg="#BD2028",
            ),
            SlotDefinition(
                slot_id="r1",
                label="④ 右上领地格",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 0.34),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.34), (0.5, 0.34)],
                default_bg="#D9A72A",
            ),
            SlotDefinition(
                slot_id="r2",
                label="⑤ 右中领地格",
                shape="polygon",
                bbox=(0.5, 0.34, 1.0, 0.67),
                polygon=[(0.5, 0.34), (1.0, 0.34), (1.0, 0.67), (0.5, 0.67)],
                default_bg="#A81E24",
            ),
            SlotDefinition(
                slot_id="r3",
                label="⑥ 右下领地格",
                shape="polygon",
                bbox=(0.5, 0.67, 1.0, 1.0),
                polygon=[(0.5, 0.67), (1.0, 0.67), (1.0, 1.0), (0.5, 1.0)],
                default_bg="#E2B23B",
            ),
            SlotDefinition(
                slot_id="top_wedge",
                label="⑦ 顶部皇室三角区",
                shape="polygon",
                bbox=(0.24, 0.0, 0.76, 0.36),
                polygon=[(0.24, 0.0), (0.76, 0.0), (0.50, 0.36)],
                is_overlay=True,
                default_bg="#5D9CE6",
            ),
            SlotDefinition(
                slot_id="bot_wedge",
                label="⑧ 底部镶嵌三角区",
                shape="granada_point",
                bbox=(0.28, 0.64, 0.72, 1.0),
                is_overlay=True,
                default_bg="#F2EFE9",
            ),
            SlotDefinition(
                slot_id="center",
                label="⑨ 中央宗主核心盾",
                shape="escutcheon",
                bbox=(0.34, 0.32, 0.66, 0.68),
                is_overlay=True,
                default_bg="#B82028",
            ),
        ],
    ),
    HeraldicTemplate(
        template_id="quartered_5",
        name="经典四分 + 中央核心小盾（5 槽位：四王国 + 核心家族）",
        subtitle="最常用联合纹章：四个象限放置四个领地/支系纹章，正中放置本家核心纹章",
        slots=[
            SlotDefinition(
                slot_id="q1",
                label="① 左上象限",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 0.5),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
                default_bg="#8E1B22",
            ),
            SlotDefinition(
                slot_id="q2",
                label="② 右上象限",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 0.5),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)],
                default_bg="#1B3664",
            ),
            SlotDefinition(
                slot_id="q3",
                label="③ 左下象限",
                shape="polygon",
                bbox=(0.0, 0.5, 0.5, 1.0),
                polygon=[(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)],
                default_bg="#1B3664",
            ),
            SlotDefinition(
                slot_id="q4",
                label="④ 右下象限",
                shape="polygon",
                bbox=(0.5, 0.5, 1.0, 1.0),
                polygon=[(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)],
                default_bg="#8E1B22",
            ),
            SlotDefinition(
                slot_id="center",
                label="⑤ 中央核心小盾",
                shape="escutcheon",
                bbox=(0.32, 0.30, 0.68, 0.70),
                is_overlay=True,
                default_bg="#D4A638",
            ),
        ],
    ),
    HeraldicTemplate(
        template_id="quartered_4",
        name="纯正四分纹章（4 槽位：2×2 经典四大家族/四王国联统）",
        subtitle="标准 2×2 四等分纹章，适合英法联统、卡斯蒂利亚-莱昂四分等经典布局",
        slots=[
            SlotDefinition(
                slot_id="q1",
                label="① 左上象限",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 0.5),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
                default_bg="#8E1B22",
            ),
            SlotDefinition(
                slot_id="q2",
                label="② 右上象限",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 0.5),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)],
                default_bg="#1B3664",
            ),
            SlotDefinition(
                slot_id="q3",
                label="③ 左下象限",
                shape="polygon",
                bbox=(0.0, 0.5, 0.5, 1.0),
                polygon=[(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)],
                default_bg="#1B3664",
            ),
            SlotDefinition(
                slot_id="q4",
                label="④ 右下象限",
                shape="polygon",
                bbox=(0.5, 0.5, 1.0, 1.0),
                polygon=[(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)],
                default_bg="#8E1B22",
            ),
        ],
    ),
    HeraldicTemplate(
        template_id="impaled_3",
        name="左右对半联姻纹章 + 中央小盾（3 槽位：东西共治/王室联姻）",
        subtitle="左右对半拼接两个家族或王国纹章，并在中央叠加核心小盾",
        slots=[
            SlotDefinition(
                slot_id="left",
                label="① 左半区（主方纹章）",
                shape="polygon",
                bbox=(0.0, 0.0, 0.5, 1.0),
                polygon=[(0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)],
                default_bg="#8E1B22",
            ),
            SlotDefinition(
                slot_id="right",
                label="② 右半区（联姻/共治方纹章）",
                shape="polygon",
                bbox=(0.5, 0.0, 1.0, 1.0),
                polygon=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)],
                default_bg="#1B3664",
            ),
            SlotDefinition(
                slot_id="center",
                label="③ 中央核心小盾（可留空）",
                shape="escutcheon",
                bbox=(0.33, 0.31, 0.67, 0.69),
                is_overlay=True,
                default_bg="#D4A638",
            ),
        ],
    ),
]


def get_template_by_id(template_id: str) -> HeraldicTemplate:
    for t in HERALDIC_TEMPLATES:
        if t.template_id == template_id:
            return t
    return HERALDIC_TEMPLATES[0]


def _parse_rgb(hex_color: str, fallback: tuple[int, int, int] = (28, 34, 48)) -> tuple[int, int, int]:
    try:
        c = ImageColor.getrgb(hex_color)
        return (c[0], c[1], c[2])
    except Exception:
        return fallback


def _build_heater_shield_polygon(
    x0: float, y0: float, x1: float, y1: float, steps: int = 24
) -> list[tuple[float, float]]:
    """Construct a smooth classic heater-shield polygon inside (x0, y0, x1, y1)."""
    w = x1 - x0
    h = y1 - y0
    cx = (x0 + x1) / 2.0
    mid_y = y0 + h * 0.48

    pts: list[tuple[float, float]] = [(x0, y0), (x1, y0), (x1, mid_y)]
    # Right curve from (x1, mid_y) down to tip (cx, y1)
    for i in range(1, steps + 1):
        t = i / steps
        # Quadratic bezier with control point (x1, y0 + h * 0.84)
        px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * x1 + t**2 * cx
        py = (1 - t) ** 2 * mid_y + 2 * (1 - t) * t * (y0 + h * 0.84) + t**2 * y1
        pts.append((px, py))
    # Left curve from tip (cx, y1) up to (x0, mid_y)
    for i in range(1, steps):
        t = i / steps
        px = (1 - t) ** 2 * cx + 2 * (1 - t) * t * x0 + t**2 * x0
        py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * (y0 + h * 0.84) + t**2 * mid_y
        pts.append((px, py))
    pts.append((x0, mid_y))
    return pts


def _build_granada_point_polygon(
    x0: float, y0: float, x1: float, y1: float, steps: int = 20
) -> list[tuple[float, float]]:
    """Construct an authentic concave curved heraldic enté-en-point wedge."""
    cx = (x0 + x1) / 2.0
    pts: list[tuple[float, float]] = []
    # Left concave curve from (x0, y1) up to apex (cx, y0)
    for i in range(steps + 1):
        t = i / steps
        ctrl_x = x0 + (cx - x0) * 0.35
        ctrl_y = y0 + (y1 - y0) * 0.60
        px = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * ctrl_x + t**2 * cx
        py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * ctrl_y + t**2 * y0
        pts.append((px, py))
    # Right concave curve from apex (cx, y0) down to (x1, y1)
    for i in range(1, steps + 1):
        t = i / steps
        ctrl_x = x1 - (x1 - cx) * 0.35
        ctrl_y = y0 + (y1 - y0) * 0.60
        px = (1 - t) ** 2 * cx + 2 * (1 - t) * t * ctrl_x + t**2 * x1
        py = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * ctrl_y + t**2 * y1
        pts.append((px, py))
    return pts


def slot_pixel_polygon(
    slot: SlotDefinition,
    style: CompositeStyle,
    canvas_px: int,
) -> list[tuple[float, float]]:
    """Return the polygon vertices in pixel coordinates for hit-testing and drawing."""
    x0, y0, x1, y1 = (c * canvas_px for c in slot.bbox)
    if slot.shape == "polygon":
        return [(px * canvas_px, py * canvas_px) for px, py in slot.polygon]
    if slot.shape == "granada_point":
        return _build_granada_point_polygon(x0, y0, x1, y1)
    if slot.shape == "escutcheon":
        if style.escutcheon_shape == "shield":
            return _build_heater_shield_polygon(x0, y0, x1, y1)
        # Approximate ellipse/circle as 36-gon
        import math

        cx = (x0 + x1) / 2.0
        cy = (y0 + y1) / 2.0
        rx = (x1 - x0) / 2.0
        ry = rx if style.escutcheon_shape == "circle" else (y1 - y0) / 2.0
        return [
            (cx + rx * math.cos(2 * math.pi * i / 36), cy + ry * math.sin(2 * math.pi * i / 36))
            for i in range(36)
        ]
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _render_slot_image(
    slot: SlotDefinition,
    state: Optional[SlotImageState],
    canvas_px: int,
) -> Image.Image:
    """Render a single slot's image positioned inside its bounding box on a full-size RGBA layer."""
    layer = Image.new("RGBA", (canvas_px, canvas_px), (0, 0, 0, 0))
    x0 = round(slot.bbox[0] * canvas_px)
    y0 = round(slot.bbox[1] * canvas_px)
    x1 = round(slot.bbox[2] * canvas_px)
    y1 = round(slot.bbox[3] * canvas_px)
    bw = max(1, x1 - x0)
    bh = max(1, y1 - y0)

    bg_hex = state.bg_color if (state and state.bg_color) else slot.default_bg
    bg_rgb = _parse_rgb(bg_hex)
    slot_canvas = Image.new("RGBA", (bw, bh), (*bg_rgb, 255))

    src_img: Optional[Image.Image] = None
    if state:
        if state.pil_image is not None:
            src_img = state.pil_image.convert("RGBA")
        elif state.image_path is not None and state.image_path.is_file():
            try:
                src_img = load_oriented_rgba(state.image_path)
            except Exception:
                src_img = None

    if src_img is not None and src_img.width > 0 and src_img.height > 0:
        zoom = max(0.25, min(state.zoom if state else 1.0, 4.0))
        fit_mode = state.fit_mode if state else "cover"
        if fit_mode == "contain":
            base_scale = min(bw / src_img.width, bh / src_img.height)
        else:
            base_scale = max(bw / src_img.width, bh / src_img.height)

        target_w = max(1, round(src_img.width * base_scale * zoom))
        target_h = max(1, round(src_img.height * base_scale * zoom))
        resized = src_img.resize((target_w, target_h), Image.Resampling.LANCZOS)

        off_x = round((state.offset_x if state else 0.0) * bw)
        off_y = round((state.offset_y if state else 0.0) * bh)
        px = (bw - target_w) // 2 + off_x
        py = (bh - target_h) // 2 + off_y
        slot_canvas.alpha_composite(resized, (px, py))

    layer.paste(slot_canvas, (x0, y0))
    return layer


def render_heraldic_composite(
    template: HeraldicTemplate,
    slot_states: dict[str, SlotImageState],
    style: CompositeStyle,
    output_size: int = 512,
) -> Image.Image:
    """Render a multi-slot heraldic composite with 2x supersampled vector masks and borders."""
    ss = 2
    work_px = output_size * ss
    scale_factor = work_px / 512.0

    bg_rgb = _parse_rgb(style.canvas_bg_color, (18, 21, 28))
    canvas = Image.new("RGBA", (work_px, work_px), (*bg_rgb, 255))

    border_rgb = _parse_rgb(style.border_color, (217, 180, 90))
    border_w = max(0, round(style.border_width * scale_factor))
    ring_rgb = _parse_rgb(style.escutcheon_ring_color, (168, 32, 40))
    ring_w = max(0, round(style.escutcheon_ring_width * scale_factor))

    # 1. Base slots (non-overlay)
    base_slots = [s for s in template.slots if not s.is_overlay]
    for slot in base_slots:
        st = slot_states.get(slot.slot_id)
        poly = slot_pixel_polygon(slot, style, work_px)
        mask = Image.new("L", (work_px, work_px), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        slot_layer = _render_slot_image(slot, st, work_px)
        canvas = Image.composite(slot_layer, canvas, mask)

    # 2. Division lines between base slots
    if border_w > 0:
        draw = ImageDraw.Draw(canvas)
        for slot in base_slots:
            poly = slot_pixel_polygon(slot, style, work_px)
            draw.line(poly + [poly[0]], fill=(*border_rgb, 255), width=border_w, joint="curve")

    # 3. Overlay slots (Granada point, top/bottom wedges, Center Escutcheon)
    overlay_slots = [s for s in template.slots if s.is_overlay]
    for slot in overlay_slots:
        st = slot_states.get(slot.slot_id)
        # Skip empty optional center escutcheon in impaled_3 if user cleared it and wants pure 2-split
        if (
            template.template_id == "impaled_3"
            and slot.slot_id == "center"
            and (st is None or (st.image_path is None and st.pil_image is None))
        ):
            continue

        poly = slot_pixel_polygon(slot, style, work_px)
        mask = Image.new("L", (work_px, work_px), 0)
        ImageDraw.Draw(mask).polygon(poly, fill=255)
        slot_layer = _render_slot_image(slot, st, work_px)
        canvas = Image.composite(slot_layer, canvas, mask)

        draw = ImageDraw.Draw(canvas)
        if slot.shape == "escutcheon":
            if ring_w > 0:
                draw.line(poly + [poly[0]], fill=(*ring_rgb, 255), width=ring_w, joint="curve")
            if border_w > 0:
                draw.line(
                    poly + [poly[0]],
                    fill=(*border_rgb, 255),
                    width=max(2, border_w // 2),
                    joint="curve",
                )
        elif border_w > 0:
            draw.line(poly + [poly[0]], fill=(*border_rgb, 255), width=border_w, joint="curve")

    # 4. Optional outer heater-shield framing
    if style.outer_shield_frame:
        margin = work_px * 0.04
        shield_poly = _build_heater_shield_polygon(
            margin, margin, work_px - margin, work_px - margin, steps=32
        )
        outer_mask = Image.new("L", (work_px, work_px), 0)
        ImageDraw.Draw(outer_mask).polygon(shield_poly, fill=255)
        framed = Image.new("RGBA", (work_px, work_px), (*bg_rgb, 255))
        framed = Image.composite(canvas, framed, outer_mask)
        if border_w > 0:
            ImageDraw.Draw(framed).line(
                shield_poly + [shield_poly[0]],
                fill=(*border_rgb, 255),
                width=max(4, round(border_w * 1.3)),
                joint="curve",
            )
        canvas = framed

    return canvas.resize((output_size, output_size), Image.Resampling.LANCZOS)


# ------------------------------------------------------------------ Native CK3 TXT Code Merger
_EMBLEM_RE = re.compile(r"colored_emblem\s*=\s*\{", re.IGNORECASE)
_POS_RE = re.compile(r"(position\s*=\s*\{\s*)([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)(\s*\})")
_SCALE_RE = re.compile(r"(scale\s*=\s*\{\s*)([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)(\s*\})")


def _extract_emblem_blocks(coa_text: str) -> list[str]:
    """Extract all top-level colored_emblem={ ... } blocks from a CK3 CoA script."""
    blocks: list[str] = []
    for match in _EMBLEM_RE.finditer(coa_text):
        start = match.start()
        brace_idx = coa_text.find("{", start)
        if brace_idx < 0:
            continue
        depth = 0
        i = brace_idx
        n = len(coa_text)
        while i < n:
            ch = coa_text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(coa_text[start : i + 1])
                    break
            i += 1
    return blocks


def _transform_emblem_block(block: str, bbox: tuple[float, float, float, float]) -> str:
    """Remap position={x y} and scale={sx sy} inside a colored_emblem block into bbox."""
    x0, y0, x1, y1 = bbox
    bw = x1 - x0
    bh = y1 - y0

    def repl_pos(m: re.Match) -> str:
        ox = float(m.group(2))
        oy = float(m.group(3))
        nx = x0 + ox * bw
        ny = y0 + oy * bh
        return f"{m.group(1)}{nx:.6f} {ny:.6f}{m.group(4)}"

    def repl_scale(m: re.Match) -> str:
        osx = float(m.group(2))
        osy = float(m.group(3))
        nsx = osx * bw
        nsy = osy * bh
        return f"{m.group(1)}{nsx:.6f} {nsy:.6f}{m.group(4)}"

    out = _POS_RE.sub(repl_pos, block)
    out = _SCALE_RE.sub(repl_scale, out)
    return out


def merge_coa_txt_scripts(
    slot_scripts: list[tuple[str, tuple[float, float, float, float]]],
    landed_title: bool = False,
) -> str:
    """Directly merge multiple CK3 CoA .txt scripts by transforming their emblem coordinates."""
    header = "coa_title_0000000000={" if landed_title else "coa_rd_dynasty_0000000000={"
    lines = [
        header,
        '\tpattern="pattern_solid.dds"',
        "\tcolor1={ 24 26 32 }",
    ]
    for script_text, bbox in slot_scripts:
        for block in _extract_emblem_blocks(script_text):
            transformed = _transform_emblem_block(block, bbox)
            lines.append("\t" + transformed)
    lines.append("}")
    return "\n".join(lines) + "\n"
