"""Pillow-based 1:1 square image editing, color enhancement, and icon generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageOps


@dataclass
class SquareEditSpec:
    """Non-destructive edit parameters producing a guaranteed 1:1 square image."""

    mode: str = "crop"  # "crop" | "pad"
    crop_x: int = 0
    crop_y: int = 0
    crop_side: int = 0  # 0 means auto max centered square
    pad_bg: str = "edge"  # "transparent" | "black" | "white" | "edge" | "custom"
    pad_custom_rgb: tuple[int, int, int] = (20, 22, 26)
    rotate_steps: int = 0  # clockwise 90 deg increments (0..3)
    flip_h: bool = False
    flip_v: bool = False
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    target_size: int = 0  # 0 = keep natural square size


def load_oriented_rgba(path: Path) -> Image.Image:
    """Open an image respecting EXIF orientation and convert to RGBA."""
    with Image.open(path) as im:
        oriented = ImageOps.exif_transpose(im)
        return oriented.convert("RGBA")


def apply_geometry(img: Image.Image, rotate_steps: int, flip_h: bool, flip_v: bool) -> Image.Image:
    """Apply lossless 90-degree rotations and flips."""
    out = img
    steps = rotate_steps % 4
    if steps == 1:
        out = out.transpose(Image.Transpose.ROTATE_270)
    elif steps == 2:
        out = out.transpose(Image.Transpose.ROTATE_180)
    elif steps == 3:
        out = out.transpose(Image.Transpose.ROTATE_90)

    if flip_h:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        out = out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return out


def sample_edge_color(img: Image.Image) -> tuple[int, int, int]:
    """Compute average opaque border color for smart padding."""
    rgb = img.convert("RGBA")
    w, h = rgb.size
    if w == 0 or h == 0:
        return (20, 22, 26)

    samples: list[tuple[int, int, int]] = []
    step_x = max(1, w // 24)
    step_y = max(1, h // 24)
    px = rgb.load()

    for x in range(0, w, step_x):
        for y in (0, h - 1):
            r, g, b, a = px[x, y]
            if a > 32:
                samples.append((r, g, b))
    for y in range(0, h, step_y):
        for x in (0, w - 1):
            r, g, b, a = px[x, y]
            if a > 32:
                samples.append((r, g, b))

    if not samples:
        return (20, 22, 26)
    n = len(samples)
    return (
        sum(c[0] for c in samples) // n,
        sum(c[1] for c in samples) // n,
        sum(c[2] for c in samples) // n,
    )


def apply_enhancements(img: Image.Image, spec: SquareEditSpec) -> Image.Image:
    """Apply brightness, contrast, saturation, and sharpness while preserving alpha."""
    if (
        abs(spec.brightness - 1.0) < 1e-3
        and abs(spec.contrast - 1.0) < 1e-3
        and abs(spec.saturation - 1.0) < 1e-3
        and abs(spec.sharpness - 1.0) < 1e-3
    ):
        return img

    has_alpha = img.mode == "RGBA"
    alpha = img.getchannel("A") if has_alpha else None
    work = img.convert("RGB")

    if abs(spec.brightness - 1.0) >= 1e-3:
        work = ImageEnhance.Brightness(work).enhance(spec.brightness)
    if abs(spec.contrast - 1.0) >= 1e-3:
        work = ImageEnhance.Contrast(work).enhance(spec.contrast)
    if abs(spec.saturation - 1.0) >= 1e-3:
        work = ImageEnhance.Color(work).enhance(spec.saturation)
    if abs(spec.sharpness - 1.0) >= 1e-3:
        work = ImageEnhance.Sharpness(work).enhance(spec.sharpness)

    out = work.convert("RGBA")
    if alpha is not None:
        out.putalpha(alpha)
    return out


def default_centered_crop(width: int, height: int) -> tuple[int, int, int]:
    """Return (x, y, side) for the largest centered 1:1 square inside width x height."""
    side = min(width, height)
    x = max(0, (width - side) // 2)
    y = max(0, (height - side) // 2)
    return x, y, side


def apply_square_edit(source_rgba: Image.Image, spec: SquareEditSpec) -> Image.Image:
    """Produce a guaranteed 1:1 square RGBA image from source and edit specification."""
    geo = apply_geometry(source_rgba, spec.rotate_steps, spec.flip_h, spec.flip_v)
    w, h = geo.size

    if spec.mode == "pad":
        side = max(w, h)
        if spec.pad_bg == "transparent":
            bg = (0, 0, 0, 0)
        elif spec.pad_bg == "black":
            bg = (0, 0, 0, 255)
        elif spec.pad_bg == "white":
            bg = (255, 255, 255, 255)
        elif spec.pad_bg == "edge":
            r, g, b = sample_edge_color(geo)
            bg = (r, g, b, 255)
        else:
            r, g, b = spec.pad_custom_rgb
            bg = (r, g, b, 255)

        canvas = Image.new("RGBA", (side, side), bg)
        ox = (side - w) // 2
        oy = (side - h) // 2
        canvas.alpha_composite(geo, (ox, oy))
        squared = canvas
    else:
        max_side = min(w, h)
        side = spec.crop_side if spec.crop_side > 0 else max_side
        side = max(1, min(side, max_side))
        x = max(0, min(spec.crop_x, w - side))
        y = max(0, min(spec.crop_y, h - side))
        if spec.crop_side <= 0:
            x, y, side = default_centered_crop(w, h)
        squared = geo.crop((x, y, x + side, y + side))

    enhanced = apply_enhancements(squared, spec)

    if spec.target_size and spec.target_size > 0 and spec.target_size != enhanced.width:
        enhanced = enhanced.resize(
            (spec.target_size, spec.target_size),
            Image.Resampling.LANCZOS,
        )

    # Hard invariant: strictly 1:1 square
    if enhanced.width != enhanced.height:
        s = min(enhanced.width, enhanced.height)
        enhanced = enhanced.crop((0, 0, s, s))
    return enhanced


def save_square_image(square_rgba: Image.Image, dest_path: Path, fmt: Optional[str] = None) -> Path:
    """Save 1:1 square image as PNG or JPG."""
    assert square_rgba.width == square_rgba.height, "Output image must be 1:1 square"
    ext = (fmt or dest_path.suffix.lstrip(".") or "png").lower()
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if ext in {"jpg", "jpeg"}:
        # Flatten alpha onto dark slate background if transparent
        bg = Image.new("RGB", square_rgba.size, (20, 22, 26))
        if square_rgba.mode == "RGBA":
            bg.paste(square_rgba, mask=square_rgba.getchannel("A"))
        else:
            bg.paste(square_rgba)
        bg.save(dest_path, format="JPEG", quality=95)
    else:
        square_rgba.save(dest_path, format="PNG", optimize=True)
    return dest_path


def generate_app_icons(assets_dir: Path) -> tuple[Path, Path]:
    """Generate a clean CK3-inspired golden shield icon in PNG and multi-size ICO."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded dark slate badge
    draw.rounded_rectangle(
        (12, 12, size - 12, size - 12),
        radius=52,
        fill=(22, 25, 32, 255),
        outline=(212, 175, 55, 255),
        width=8,
    )

    # Heraldic shield polygon
    shield = [
        (68, 54),
        (188, 54),
        (188, 128),
        (178, 162),
        (156, 188),
        (128, 208),
        (100, 188),
        (78, 162),
        (68, 128),
    ]
    draw.polygon(shield, fill=(44, 52, 68, 255), outline=(229, 193, 88, 255))
    draw.line(shield + [shield[0]], fill=(229, 193, 88, 255), width=7)

    # Inner 1:1 square motif inside the shield
    draw.rectangle((96, 84, 160, 148), outline=(245, 224, 150, 255), width=6)
    draw.rectangle((112, 100, 144, 132), fill=(212, 175, 55, 255))

    png_path = assets_dir / "app_icon.png"
    ico_path = assets_dir / "app_icon.ico"
    img.save(png_path, format="PNG")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    return png_path, ico_path
