"""Unit tests for workspace pairing, converter CLI building, and 1:1 image editing."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.composer import (
    HERALDIC_TEMPLATES,
    CompositeStyle,
    SlotImageState,
    merge_coa_txt_scripts,
    render_heraldic_composite,
)
from src.core.converter import ConvertParams
from src.core.image_ops import SquareEditSpec, apply_square_edit, save_square_image
from src.core.workspace import inspect_txt_file, rename_entry, scan_workspace


class TestCore(unittest.TestCase):
    def test_workspace_pairing_and_txt_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            Image.new("RGB", (128, 128), (200, 50, 50)).save(ws / "sample_crest.png")
            (ws / "sample_crest.txt").write_text(
                'coa_rd_dynasty_0001={\n\tpattern="pattern_solid.dds"\n}\n',
                encoding="utf-8",
            )
            Image.new("RGB", (300, 150), (10, 20, 30)).save(ws / "wide.jpg")
            (ws / "orphan_title.txt").write_text(
                'coa_title_999={\n\tpattern="pattern_solid.dds"\n}\n',
                encoding="utf-8",
            )
            (ws / "note.txt").write_text("just a command note", encoding="utf-8")

            entries = scan_workspace(ws)
            by_stem = {e.stem: e for e in entries}

            self.assertEqual(len(entries), 4)
            self.assertTrue(by_stem["sample_crest"].is_paired)
            self.assertTrue(by_stem["sample_crest"].is_square)
            self.assertEqual(by_stem["sample_crest"].txt_meta.coa_kind, "dynasty")

            self.assertTrue(by_stem["wide"].has_image)
            self.assertFalse(by_stem["wide"].has_txt)
            self.assertFalse(by_stem["wide"].is_square)

            self.assertFalse(by_stem["orphan_title"].has_image)
            self.assertTrue(by_stem["orphan_title"].has_txt)
            self.assertEqual(by_stem["orphan_title"].txt_meta.coa_kind, "title")

            self.assertEqual(by_stem["note"].txt_meta.coa_kind, "other")

    def test_rename_entry_syncs_image_and_txt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp)
            Image.new("RGB", (64, 64)).save(ws / "alpha.png")
            (ws / "alpha.txt").write_text("coa_rd_dynasty_1={}", encoding="utf-8")

            entry = scan_workspace(ws)[0]
            new_img, new_txt = rename_entry(entry, "beta")
            self.assertTrue((ws / "beta.png").is_file())
            self.assertTrue((ws / "beta.txt").is_file())
            self.assertFalse((ws / "alpha.png").exists())
            self.assertEqual(new_img.name, "beta.png")
            self.assertEqual(new_txt.name, "beta.txt")

    def test_square_edit_crop_and_pad_invariants(self) -> None:
        rect_img = Image.new("RGBA", (320, 180), (120, 40, 200, 255))

        cropped = apply_square_edit(
            rect_img,
            SquareEditSpec(mode="crop", crop_x=20, crop_y=0, crop_side=180, target_size=256),
        )
        self.assertEqual(cropped.size, (256, 256))

        padded = apply_square_edit(
            rect_img,
            SquareEditSpec(mode="pad", pad_bg="edge", rotate_steps=1, target_size=512),
        )
        self.assertEqual(padded.size, (512, 512))

        with tempfile.TemporaryDirectory() as tmp:
            out = save_square_image(padded, Path(tmp) / "out.jpg", "jpg")
            with Image.open(out) as saved:
                self.assertEqual(saved.size, (512, 512))

    def test_converter_cli_args(self) -> None:
        params = ConvertParams(
            source_path=Path(r"C:\demo\sample_crest.png"),
            resolution=150,
            color_mode="Reduced",
            color_limit=20,
            landed_title=True,
        )
        args = params.build_args()
        self.assertEqual(
            args,
            [
                "-s",
                r"C:\demo\sample_crest.png",
                "-d",
                r"C:\demo\sample_crest.txt",
                "-r",
                "150",
                "-c",
                "Reduced",
                "-k",
                "20",
                "-t",
            ],
        )

    def test_heraldic_composite_templates_and_txt_merger(self) -> None:
        sample_img = Image.new("RGBA", (128, 128), (220, 60, 60, 255))
        for tpl in HERALDIC_TEMPLATES:
            states = {s.slot_id: SlotImageState(pil_image=sample_img) for s in tpl.slots}
            out = render_heraldic_composite(
                tpl,
                states,
                CompositeStyle(outer_shield_frame=True),
                output_size=256,
            )
            self.assertEqual(out.size, (256, 256))

        script_a = (
            'coa_rd_dynasty_1={\n'
            '\tcolored_emblem={\n'
            '\t\ttexture="ce_block_02.dds"\n'
            '\t\tinstance={\n'
            '\t\t\tposition={ 0.500000 0.500000 }\n'
            '\t\t\tscale={ 0.200000 0.200000 }\n'
            '\t\t}\n'
            '\t}\n'
            '}\n'
        )
        merged = merge_coa_txt_scripts(
            [
                (script_a, (0.0, 0.0, 0.5, 0.5)),
                (script_a, (0.5, 0.5, 1.0, 1.0)),
            ]
        )
        self.assertIn("position={ 0.250000 0.250000 }", merged)
        self.assertIn("position={ 0.750000 0.750000 }", merged)
        self.assertIn("scale={ 0.100000 0.100000 }", merged)


if __name__ == "__main__":
    unittest.main()
