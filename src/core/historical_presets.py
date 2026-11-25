"""Built-in library of famous European historical Coats of Arms (procedurally rendered at 512x512)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw

from src.core.composer import (
    CompositeStyle,
    SlotImageState,
    get_template_by_id,
    render_heraldic_composite,
)


@dataclass
class HistoricalPreset:
    """Metadata and generator for a famous European historical Coat of Arms."""

    preset_id: str
    name: str
    dynasty_or_realm: str
    description: str
    generator: Callable[[int], Image.Image]


def _draw_fleur_de_lis(
    draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    scale: float,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    """Draw a classic sculpted heraldic fleur-de-lis centered at (cx, cy)."""
    s = scale
    # Center spear petal
    center_petal = [
        (cx, cy - 1.05 * s),
        (cx + 0.24 * s, cy - 0.45 * s),
        (cx + 0.16 * s, cy + 0.18 * s),
        (cx, cy + 0.78 * s),
        (cx - 0.16 * s, cy + 0.18 * s),
        (cx - 0.24 * s, cy - 0.45 * s),
    ]
    # Left curving petal
    left_petal = [
        (cx - 0.12 * s, cy + 0.08 * s),
        (cx - 0.36 * s, cy - 0.52 * s),
        (cx - 0.76 * s, cy - 0.56 * s),
        (cx - 0.92 * s, cy - 0.18 * s),
        (cx - 0.68 * s, cy + 0.08 * s),
        (cx - 0.46 * s, cy - 0.12 * s),
        (cx - 0.32 * s, cy + 0.22 * s),
    ]
    # Right curving petal
    right_petal = [(2 * cx - px, py) for px, py in left_petal]
    # Bottom left & right flared tips below the band
    bot_left = [
        (cx - 0.12 * s, cy + 0.28 * s),
        (cx - 0.52 * s, cy + 0.58 * s),
        (cx - 0.34 * s, cy + 0.74 * s),
        (cx - 0.08 * s, cy + 0.48 * s),
    ]
    bot_right = [(2 * cx - px, py) for px, py in bot_left]

    for poly in (bot_left, bot_right, left_petal, right_petal, center_petal):
        draw.polygon(poly, fill=fill, outline=outline, width=max(2, round(s * 0.04)))

    # Horizontal binding band
    draw.rounded_rectangle(
        (cx - 0.44 * s, cy + 0.12 * s, cx + 0.44 * s, cy + 0.30 * s),
        radius=max(3, round(s * 0.06)),
        fill=fill,
        outline=outline,
        width=max(2, round(s * 0.04)),
    )


def _gen_france_bourbon(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (22, 54, 134, 255))
    draw = ImageDraw.Draw(img)
    gold = (238, 198, 72)
    dark = (96, 68, 14)
    r = w * 0.165
    for cx, cy in ((w * 0.31, w * 0.32), (w * 0.69, w * 0.32), (w * 0.50, w * 0.70)):
        _draw_fleur_de_lis(draw, cx, cy, r, gold, dark)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_byzantium_palaiologos(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (124, 20, 38, 255))
    draw = ImageDraw.Draw(img)
    gold = (232, 188, 64)
    dark = (72, 48, 10)

    # Central golden cross
    cw = round(w * 0.14)
    c0 = (w - cw) // 2
    c1 = c0 + cw
    draw.rectangle((c0, 0, c1, w), fill=gold, outline=dark, width=4)
    draw.rectangle((0, c0, w, c1), fill=gold, outline=dark, width=4)

    # Four golden Beta (B) firesteels in the four quarters (left two mirrored)
    def draw_beta(qx: float, qy: float, mirror: bool) -> None:
        bw = w * 0.15
        bh = w * 0.22
        x0 = qx - bw / 2
        y0 = qy - bh / 2
        stroke = round(w * 0.032)
        if not mirror:
            # Spine on left, two loops on right
            draw.rectangle((x0, y0, x0 + stroke, y0 + bh), fill=gold)
            draw.arc((x0 - stroke, y0, x0 + bw, y0 + bh * 0.54), -90, 90, fill=gold, width=stroke)
            draw.arc((x0 - stroke, y0 + bh * 0.46, x0 + bw, y0 + bh), -90, 90, fill=gold, width=stroke)
        else:
            # Spine on right, two loops on left
            draw.rectangle((x0 + bw - stroke, y0, x0 + bw, y0 + bh), fill=gold)
            draw.arc((x0, y0, x0 + bw + stroke, y0 + bh * 0.54), 90, 270, fill=gold, width=stroke)
            draw.arc((x0, y0 + bh * 0.46, x0 + bw + stroke, y0 + bh), 90, 270, fill=gold, width=stroke)

    draw_beta(w * 0.23, w * 0.23, mirror=True)
    draw_beta(w * 0.77, w * 0.23, mirror=False)
    draw_beta(w * 0.23, w * 0.77, mirror=True)
    draw_beta(w * 0.77, w * 0.77, mirror=False)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_hre_eagle(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    gold = (234, 190, 54)
    black = (20, 22, 26)
    red = (188, 28, 34)
    img = Image.new("RGBA", (w, w), (*gold, 255))
    draw = ImageDraw.Draw(img)

    cx = w * 0.50
    # Halos behind the two heads
    for hx in (w * 0.37, w * 0.63):
        hy = w * 0.21
        hr = w * 0.075
        draw.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=(246, 212, 92), outline=black, width=6)

    # Spread wings with splayed feathers
    for sign in (-1, 1):
        wing_shoulder = (cx + sign * w * 0.08, w * 0.34)
        for i, angle_y in enumerate((0.22, 0.32, 0.43, 0.54, 0.64)):
            tip_x = cx + sign * (w * (0.44 - i * 0.035))
            tip_y = w * angle_y
            feather = [
                wing_shoulder,
                (cx + sign * w * 0.24, w * (0.28 + i * 0.05)),
                (tip_x, tip_y),
                (tip_x - sign * w * 0.04, tip_y + w * 0.045),
                (cx + sign * w * 0.10, w * (0.44 + i * 0.04)),
            ]
            draw.polygon(feather, fill=black)

        # Neck & Head
        neck = [
            (cx + sign * w * 0.03, w * 0.36),
            (cx + sign * w * 0.13, w * 0.22),
            (cx + sign * w * 0.17, w * 0.18),
            (cx + sign * w * 0.08, w * 0.18),
            (cx + sign * w * 0.01, w * 0.32),
        ]
        draw.polygon(neck, fill=black)
        hx = cx + sign * w * 0.13
        hy = w * 0.20
        draw.ellipse((hx - w * 0.045, hy - w * 0.04, hx + w * 0.045, hy + w * 0.04), fill=black)
        # Red beak & tongue
        beak = [
            (hx + sign * w * 0.03, hy - w * 0.015),
            (hx + sign * w * 0.10, hy + w * 0.005),
            (hx + sign * w * 0.03, hy + w * 0.025),
        ]
        draw.polygon(beak, fill=red)

        # Red legs & talons
        leg_x = cx + sign * w * 0.16
        draw.line((cx + sign * w * 0.06, w * 0.62, leg_x, w * 0.74), fill=red, width=round(w * 0.028))
        for tx_off in (-0.04, 0.0, 0.04):
            draw.line(
                (leg_x, w * 0.74, leg_x + sign * w * 0.04 + w * tx_off, w * 0.80),
                fill=red,
                width=round(w * 0.016),
            )

    # Central torso & tail fan
    draw.ellipse((cx - w * 0.13, w * 0.32, cx + w * 0.13, w * 0.68), fill=black)
    tail = [
        (cx, w * 0.62),
        (cx - w * 0.14, w * 0.86),
        (cx - w * 0.05, w * 0.82),
        (cx, w * 0.91),
        (cx + w * 0.05, w * 0.82),
        (cx + w * 0.14, w * 0.86),
    ]
    draw.polygon(tail, fill=black)

    # Imperial crown above the two heads
    crown = [
        (cx - w * 0.11, w * 0.12),
        (cx - w * 0.13, w * 0.05),
        (cx - w * 0.05, w * 0.08),
        (cx, w * 0.03),
        (cx + w * 0.05, w * 0.08),
        (cx + w * 0.13, w * 0.05),
        (cx + w * 0.11, w * 0.12),
    ]
    draw.polygon(crown, fill=(245, 208, 78), outline=black, width=5)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_england_plantagenet(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (168, 24, 32, 255))
    draw = ImageDraw.Draw(img)
    gold = (238, 196, 68)
    dark = (88, 56, 12)
    blue = (38, 92, 178)

    for cy in (w * 0.22, w * 0.50, w * 0.78):
        # Striding lion body
        draw.rounded_rectangle(
            (w * 0.26, cy - w * 0.055, w * 0.72, cy + w * 0.045),
            radius=round(w * 0.04),
            fill=gold,
            outline=dark,
            width=4,
        )
        # Mane & guardant head (facing viewer on left)
        draw.ellipse(
            (w * 0.16, cy - w * 0.095, w * 0.34, cy + w * 0.075),
            fill=gold,
            outline=dark,
            width=5,
        )
        # Eyes & mouth details
        draw.ellipse((w * 0.20, cy - w * 0.04, w * 0.22, cy - w * 0.02), fill=dark)
        draw.ellipse((w * 0.26, cy - w * 0.04, w * 0.28, cy - w * 0.02), fill=dark)
        draw.rectangle((w * 0.22, cy + w * 0.01, w * 0.26, cy + w * 0.03), fill=blue)

        # Raised forepaw + 3 striding legs with blue claws
        legs = [
            [(w * 0.26, cy + w * 0.02), (w * 0.11, cy - w * 0.02)],
            [(w * 0.34, cy + w * 0.03), (w * 0.28, cy + w * 0.11)],
            [(w * 0.58, cy + w * 0.03), (w * 0.52, cy + w * 0.11)],
            [(w * 0.68, cy + w * 0.02), (w * 0.82, cy + w * 0.10)],
        ]
        for p0, p1 in legs:
            draw.line([p0, p1], fill=gold, width=round(w * 0.036))
            draw.ellipse(
                (p1[0] - w * 0.018, p1[1] - w * 0.018, p1[0] + w * 0.018, p1[1] + w * 0.018),
                fill=blue,
            )

        # S-curved heraldic tail over the back
        draw.arc(
            (w * 0.44, cy - w * 0.13, w * 0.84, cy + w * 0.01),
            -20,
            175,
            fill=gold,
            width=round(w * 0.024),
        )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_castile(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (168, 26, 34, 255))
    draw = ImageDraw.Draw(img)
    gold = (234, 192, 68)
    dark = (58, 38, 12)
    blue = (28, 78, 166)

    # Main castle wall
    draw.rectangle((w * 0.20, w * 0.38, w * 0.80, w * 0.84), fill=gold, outline=dark, width=6)
    # Wall crenellations
    for bx in range(round(w * 0.20), round(w * 0.78), round(w * 0.10)):
        draw.rectangle((bx, w * 0.33, bx + w * 0.06, w * 0.39), fill=gold, outline=dark, width=4)

    # Three towers (center tower taller)
    towers = [
        (w * 0.22, w * 0.18, w * 0.36, w * 0.38),
        (w * 0.42, w * 0.12, w * 0.58, w * 0.38),
        (w * 0.64, w * 0.18, w * 0.78, w * 0.38),
    ]
    for tx0, ty0, tx1, ty1 in towers:
        draw.rectangle((tx0, ty0, tx1, ty1), fill=gold, outline=dark, width=6)
        wx0 = (tx0 + tx1) / 2 - w * 0.022
        wy0 = (ty0 + ty1) / 2 - w * 0.035
        draw.rounded_rectangle(
            (wx0, wy0, wx0 + w * 0.044, wy0 + w * 0.075),
            radius=round(w * 0.02),
            fill=blue,
            outline=dark,
            width=3,
        )

    # Arched blue gate
    draw.rounded_rectangle(
        (w * 0.42, w * 0.56, w * 0.58, w * 0.84),
        radius=round(w * 0.07),
        fill=blue,
        outline=dark,
        width=5,
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_leon(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (242, 239, 232, 255))
    draw = ImageDraw.Draw(img)
    crimson = (158, 24, 68)
    dark = (74, 10, 32)
    gold = (236, 194, 66)

    # Rampant lion torso & chest
    torso = [
        (w * 0.38, w * 0.26),
        (w * 0.60, w * 0.30),
        (w * 0.56, w * 0.64),
        (w * 0.40, w * 0.68),
        (w * 0.34, w * 0.44),
    ]
    draw.polygon(torso, fill=crimson, outline=dark, width=5)
    # Head
    draw.ellipse((w * 0.34, w * 0.14, w * 0.56, w * 0.30), fill=crimson, outline=dark, width=5)
    # Golden crown
    crown = [
        (w * 0.36, w * 0.16),
        (w * 0.34, w * 0.08),
        (w * 0.42, w * 0.12),
        (w * 0.46, w * 0.07),
        (w * 0.50, w * 0.12),
        (w * 0.56, w * 0.08),
        (w * 0.54, w * 0.16),
    ]
    draw.polygon(crown, fill=gold, outline=dark, width=4)

    # Limbs (2 raised forepaws, 2 standing hind legs)
    limbs = [
        ((w * 0.38, w * 0.34), (w * 0.18, w * 0.22)),
        ((w * 0.42, w * 0.44), (w * 0.20, w * 0.42)),
        ((w * 0.42, w * 0.64), (w * 0.28, w * 0.88)),
        ((w * 0.54, w * 0.62), (w * 0.66, w * 0.88)),
    ]
    for p0, p1 in limbs:
        draw.line([p0, p1], fill=crimson, width=round(w * 0.055))
        draw.ellipse(
            (p1[0] - w * 0.03, p1[1] - w * 0.03, p1[0] + w * 0.03, p1[1] + w * 0.03),
            fill=gold,
            outline=dark,
            width=3,
        )

    # Rampant curved tail on right
    draw.arc(
        (w * 0.52, w * 0.24, w * 0.84, w * 0.72),
        -75,
        130,
        fill=crimson,
        width=round(w * 0.042),
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_aragon(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (236, 190, 52, 255))
    draw = ImageDraw.Draw(img)
    red = (176, 26, 34)
    # 9 vertical stripes total: 5 gold, 4 red
    stripe_w = size / 9.0
    for i in (1, 3, 5, 7):
        draw.rectangle((round(i * stripe_w), 0, round((i + 1) * stripe_w), size), fill=red)
    return img


def _gen_navarre(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (166, 24, 32, 255))
    draw = ImageDraw.Draw(img)
    gold = (236, 194, 68)
    dark = (82, 54, 12)

    m = round(w * 0.12)
    c = w // 2
    lw = round(w * 0.035)
    # Perimeter, cross, and diagonals
    lines = [
        ((m, m), (w - m, m)),
        ((w - m, m), (w - m, w - m)),
        ((w - m, w - m), (m, w - m)),
        ((m, w - m), (m, m)),
        ((c, m), (c, w - m)),
        ((m, c), (w - m, c)),
        ((m, m), (w - m, w - m)),
        ((w - m, m), (m, w - m)),
    ]
    for p0, p1 in lines:
        draw.line([p0, p1], fill=gold, width=lw)
        # Chain link beads along each segment
        for k in range(1, 7):
            t = k / 7.0
            bx = p0[0] + (p1[0] - p0[0]) * t
            by = p0[1] + (p1[1] - p0[1]) * t
            r = w * 0.026
            draw.ellipse((bx - r, by - r, bx + r, by + r), fill=gold, outline=dark, width=3)

    # Center emerald gem
    er = w * 0.055
    draw.ellipse((c - er, c - er, c + er, c + er), fill=(26, 156, 78), outline=gold, width=6)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_granada(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (240, 236, 228, 255))
    draw = ImageDraw.Draw(img)
    gold = (218, 164, 68)
    dark = (92, 62, 24)
    red = (178, 24, 36)
    green = (38, 132, 64)

    # Stem & two leaves at bottom
    draw.polygon(
        [(w * 0.50, w * 0.72), (w * 0.24, w * 0.80), (w * 0.34, w * 0.88)],
        fill=green,
        outline=dark,
        width=4,
    )
    draw.polygon(
        [(w * 0.50, w * 0.72), (w * 0.76, w * 0.80), (w * 0.66, w * 0.88)],
        fill=green,
        outline=dark,
        width=4,
    )
    # Pomegranate body & top crown calyx
    draw.polygon(
        [(w * 0.42, w * 0.24), (w * 0.45, w * 0.14), (w * 0.50, w * 0.20), (w * 0.55, w * 0.14), (w * 0.58, w * 0.24)],
        fill=gold,
        outline=dark,
        width=4,
    )
    draw.ellipse((w * 0.28, w * 0.22, w * 0.72, w * 0.76), fill=gold, outline=dark, width=6)
    # Split ruby seed core
    draw.ellipse((w * 0.43, w * 0.32, w * 0.57, w * 0.66), fill=red, outline=dark, width=4)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_jerusalem(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (244, 241, 234, 255))
    draw = ImageDraw.Draw(img)
    gold = (232, 188, 54)
    dark = (142, 106, 22)

    cx = w // 2
    arm_w = round(w * 0.085)
    arm_len = round(w * 0.34)
    crutch_w = round(w * 0.22)
    crutch_t = round(w * 0.075)

    # Central Cross Potent
    draw.rectangle((cx - arm_w // 2, cx - arm_len, cx + arm_w // 2, cx + arm_len), fill=gold, outline=dark, width=4)
    draw.rectangle((cx - arm_len, cx - arm_w // 2, cx + arm_len, cx + arm_w // 2), fill=gold, outline=dark, width=4)
    # 4 T-crutches
    draw.rectangle((cx - crutch_w // 2, cx - arm_len - crutch_t // 2, cx + crutch_w // 2, cx - arm_len + crutch_t // 2), fill=gold, outline=dark, width=4)
    draw.rectangle((cx - crutch_w // 2, cx + arm_len - crutch_t // 2, cx + crutch_w // 2, cx + arm_len + crutch_t // 2), fill=gold, outline=dark, width=4)
    draw.rectangle((cx - arm_len - crutch_t // 2, cx - crutch_w // 2, cx - arm_len + crutch_t // 2, cx + crutch_w // 2), fill=gold, outline=dark, width=4)
    draw.rectangle((cx + arm_len - crutch_t // 2, cx - crutch_w // 2, cx + arm_len + crutch_t // 2, cx + crutch_w // 2), fill=gold, outline=dark, width=4)

    # 4 corner crosslets
    sw = round(w * 0.045)
    sl = round(w * 0.095)
    for qx, qy in ((w * 0.22, w * 0.22), (w * 0.78, w * 0.22), (w * 0.22, w * 0.78), (w * 0.78, w * 0.78)):
        draw.rectangle((qx - sw / 2, qy - sl, qx + sw / 2, qy + sl), fill=gold, outline=dark, width=3)
        draw.rectangle((qx - sl, qy - sw / 2, qx + sl, qy + sw / 2), fill=gold, outline=dark, width=3)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_teutonic_order(size: int = 512) -> Image.Image:
    ss = 2
    w = size * ss
    img = Image.new("RGBA", (w, w), (242, 240, 235, 255))
    draw = ImageDraw.Draw(img)
    black = (20, 22, 26)
    gold = (232, 188, 56)

    c = w // 2
    bw = round(w * 0.16)
    draw.rectangle((c - bw // 2, 0, c + bw // 2, w), fill=black)
    draw.rectangle((0, c - bw // 2, w, c + bw // 2), fill=black)

    gw = round(w * 0.045)
    draw.rectangle((c - gw // 2, round(w * 0.08), c + gw // 2, round(w * 0.92)), fill=gold)
    draw.rectangle((round(w * 0.08), c - gw // 2, round(w * 0.92), c + gw // 2), fill=gold)

    # Center golden shield with black imperial eagle
    sr = round(w * 0.14)
    draw.rounded_rectangle((c - sr, c - sr, c + sr, c + sr), radius=round(w * 0.04), fill=gold, outline=black, width=6)
    draw.polygon(
        [(c, c - sr * 0.65), (c + sr * 0.65, c - sr * 0.15), (c + sr * 0.35, c + sr * 0.65), (c - sr * 0.35, c + sr * 0.65), (c - sr * 0.65, c - sr * 0.15)],
        fill=black,
    )
    return img.resize((size, size), Image.Resampling.LANCZOS)


def _gen_savoy(size: int = 512) -> Image.Image:
    img = Image.new("RGBA", (size, size), (174, 26, 34, 255))
    draw = ImageDraw.Draw(img)
    white = (244, 242, 238)
    c = size // 2
    cw = round(size * 0.22)
    draw.rectangle((c - cw // 2, 0, c + cw // 2, size), fill=white)
    draw.rectangle((0, c - cw // 2, size, c + cw // 2), fill=white)
    return img


def _gen_spanish_royal_union(size: int = 512) -> Image.Image:
    tpl = get_template_by_id("spanish_6")
    sub = max(256, size // 2)
    states = {
        "q1": SlotImageState(pil_image=_gen_castile(sub)),
        "q2": SlotImageState(pil_image=_gen_leon(sub)),
        "q3": SlotImageState(pil_image=_gen_aragon(sub)),
        "q4": SlotImageState(pil_image=_gen_navarre(sub)),
        "point": SlotImageState(pil_image=_gen_granada(sub)),
        "center": SlotImageState(pil_image=_gen_france_bourbon(sub)),
    }
    style = CompositeStyle(
        border_width=6,
        border_color="#D9B45A",
        escutcheon_shape="oval",
        escutcheon_ring_width=10,
        escutcheon_ring_color="#A82028",
    )
    return render_heraldic_composite(tpl, states, style, output_size=size)


def _gen_anglo_french_union(size: int = 512) -> Image.Image:
    tpl = get_template_by_id("quartered_4")
    sub = max(256, size // 2)
    fr = _gen_france_bourbon(sub)
    en = _gen_england_plantagenet(sub)
    states = {
        "q1": SlotImageState(pil_image=fr),
        "q2": SlotImageState(pil_image=en),
        "q3": SlotImageState(pil_image=en),
        "q4": SlotImageState(pil_image=fr),
    }
    style = CompositeStyle(border_width=6, border_color="#D9B45A")
    return render_heraldic_composite(tpl, states, style, output_size=size)


HISTORICAL_PRESETS: list[HistoricalPreset] = [
    HistoricalPreset(
        preset_id="hist_spanish_royal_union",
        name="西班牙王室大联合纹章（六合一成品）",
        dynasty_or_realm="西班牙哈布斯堡 / 波旁王室",
        description="卡斯蒂利亚 + 莱昂 + 阿拉贡 + 纳瓦拉 + 底部格拉纳达石榴 + 中央法兰西波旁三百合，一步到位。",
        generator=_gen_spanish_royal_union,
    ),
    HistoricalPreset(
        preset_id="hist_anglo_french_union",
        name="英法百年战争四分联统王室纹章",
        dynasty_or_realm="金雀花王朝 · 爱德华三世 / 亨利五世",
        description="左上右下法兰西三金百合 + 右上左下英格兰金雀花三金狮，最经典的欧洲王室四分联统纹章。",
        generator=_gen_anglo_french_union,
    ),
    HistoricalPreset(
        preset_id="hist_byzantium_palaiologos",
        name="东罗马 / 拜占庭帝国（巴列奥略四B十字）",
        dynasty_or_realm="巴列奥略王朝 (Palaiologos)",
        description="帝国紫红底配黄金正十字与四个希腊字母 Β（万王之王，统御诸王），罗马正统经典徽记。",
        generator=_gen_byzantium_palaiologos,
    ),
    HistoricalPreset(
        preset_id="hist_hre_eagle",
        name="神圣罗马帝国（皇室金底双头黑鹰）",
        dynasty_or_realm="霍亨斯陶芬 / 哈布斯堡皇室",
        description="帝王金底配戴光环与皇冠的红喙红爪双头黑鹰（Reichsadler），神罗皇帝标志性纹章。",
        generator=_gen_hre_eagle,
    ),
    HistoricalPreset(
        preset_id="hist_france_bourbon",
        name="法兰西王国（皇家蓝底三金百合）",
        dynasty_or_realm="卡佩 / 瓦卢瓦 / 波旁王朝",
        description="法兰西王室经典 Azure 皇家深蓝底配三朵鎏金鸢尾百合花（Fleur-de-lis）。",
        generator=_gen_france_bourbon,
    ),
    HistoricalPreset(
        preset_id="hist_england_plantagenet",
        name="英格兰王国（金雀花红底三迈步金狮）",
        dynasty_or_realm="金雀花王朝 (Plantagenet)",
        description="狮心王理查一世确立的英格兰皇家绯红底配三头蓝爪迈步凝视金狮。",
        generator=_gen_england_plantagenet,
    ),
    HistoricalPreset(
        preset_id="hist_jerusalem",
        name="耶路撒冷王国（银底黄金五十字）",
        dynasty_or_realm="耶路撒冷十字军王国",
        description="欧洲纹章学唯一破例「金置于银」的神圣纹章：银白底配中央黄金T字大十字与四角小十字。",
        generator=_gen_jerusalem,
    ),
    HistoricalPreset(
        preset_id="hist_teutonic_order",
        name="条顿骑士团（大团长黑金十字与神罗鹰盾）",
        dynasty_or_realm="条顿骑士团国 (Deutschorden)",
        description="银白底黑铁正十字，内嵌黄金窄十字与神圣罗马帝国赐予的中央金底黑鹰小盾。",
        generator=_gen_teutonic_order,
    ),
    HistoricalPreset(
        preset_id="hist_castile",
        name="卡斯蒂利亚王国（红底三塔黄金城堡）",
        dynasty_or_realm="伊比利亚 · 卡斯蒂利亚王室",
        description="绯红底配蓝门蓝窗三塔黄金城堡，伊比利亚核心王国纹章，适合做联统拼接。",
        generator=_gen_castile,
    ),
    HistoricalPreset(
        preset_id="hist_leon",
        name="莱昂王国（银底金冠紫红直立雄狮）",
        dynasty_or_realm="伊比利亚 · 莱昂王室",
        description="银白底配头戴金冠的紫红色直立咆哮雄狮（Lion Rampant），常与卡斯蒂利亚四分拼接。",
        generator=_gen_leon,
    ),
    HistoricalPreset(
        preset_id="hist_aragon",
        name="阿拉贡王国（金底四道绯红条纹 Senyera）",
        dynasty_or_realm="伊比利亚 · 阿拉贡王冠领",
        description="欧洲最古老的旗帜纹章之一：黄金底配四道垂直绯红条纹。",
        generator=_gen_aragon,
    ),
    HistoricalPreset(
        preset_id="hist_navarre",
        name="纳瓦拉王国（红底黄金锁链与翡翠宝石）",
        dynasty_or_realm="伊比利亚 · 纳瓦拉王室",
        description="纪念拉斯纳瓦斯·德·托洛萨战役的绯红底黄金锁链米字方阵与中央绿宝石。",
        generator=_gen_navarre,
    ),
    HistoricalPreset(
        preset_id="hist_granada",
        name="格拉纳达王国（银底裂口红籽金石榴）",
        dynasty_or_realm="伊比利亚 · 格拉纳达领",
        description="银白底配带绿叶与红籽裂口的黄金石榴，专为复合纹章底部镶嵌尖角区设计。",
        generator=_gen_granada,
    ),
    HistoricalPreset(
        preset_id="hist_savoy",
        name="萨伏依王朝 / 圣乔治十字（红底银白正十字）",
        dynasty_or_realm="萨伏依王朝 / 医院骑士团",
        description="绯红底配贯穿全盾的银白圣十字，适合作为帝国九区复合纹章的中央核心盾。",
        generator=_gen_savoy,
    ),
]


def get_historical_preset(preset_id: str) -> HistoricalPreset:
    for p in HISTORICAL_PRESETS:
        if p.preset_id == preset_id:
            return p
    return HISTORICAL_PRESETS[0]
