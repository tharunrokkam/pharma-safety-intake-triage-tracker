"""Heuristic layout check for the generated deck: estimates wrapped text height with real Calibri metrics and
flags text boxes / shapes / tables that overflow their box or the slide. Usage: python scripts/check_deck_layout.py"""
from __future__ import annotations

from pathlib import Path

from PIL import ImageFont
from pptx import Presentation
from pptx.util import Emu

DECK = Path(__file__).resolve().parents[1] / "docs" / "presentation" / "Pharma_Safety_Intake_Capstone.pptx"
FONTS = {False: "C:/Windows/Fonts/calibri.ttf", True: "C:/Windows/Fonts/calibrib.ttf"}
_cache: dict = {}
SLIDE_BOTTOM_IN = 7.05


def font(size_pt: float, bold: bool):
    key = (round(size_pt * 4), bold)
    if key not in _cache:
        _cache[key] = ImageFont.truetype(FONTS[bold], max(1, int(size_pt * 4)))  # 4x for precision
    return _cache[key]


def para_height(p, width_in: float, default_size: float = 18.0) -> float:
    runs = [(r.text, (r.font.size.pt if r.font.size else (p.font.size.pt if p.font.size else default_size)),
             bool(r.font.bold or p.font.bold)) for r in p.runs] or [(p.text, p.font.size.pt if p.font.size else default_size, bool(p.font.bold))]
    size = max(s for _, s, _ in runs) if runs else default_size
    text = "".join(t for t, _, _ in runs)
    f = font(size, any(b for _, _, b in runs))
    max_px = width_in * 72 * 4  # points*4
    lines, cur = 1, ""
    for word in text.split(" "):
        trial = (cur + " " + word).strip()
        if f.getlength(trial) > max_px and cur:
            lines += 1
            cur = word
        else:
            cur = trial
    space = (p.space_after.pt if p.space_after is not None else 0) + (p.space_before.pt if p.space_before is not None else 0)
    return (lines * size * 1.2 + space) / 72  # inches


def frame_height(tf, width_in: float) -> float:
    return sum(para_height(p, width_in) for p in tf.paragraphs)


def main() -> int:
    prs = Presentation(DECK)
    problems = 0
    for i, slide in enumerate(prs.slides, 1):
        for shp in slide.shapes:
            x, y = Emu(shp.left).inches, Emu(shp.top).inches
            w, h = Emu(shp.width).inches, Emu(shp.height).inches
            if shp.has_text_frame and shp.text_frame.text.strip():
                tf = shp.text_frame
                ml = Emu(tf.margin_left).inches + Emu(tf.margin_right).inches
                mt = Emu(tf.margin_top).inches + Emu(tf.margin_bottom).inches
                need = frame_height(tf, w - ml) + mt
                is_box = shp.shape_type == 1  # autoshape (card) - fixed height
                limit = h if is_box else max(h, SLIDE_BOTTOM_IN - y)
                if need > limit + 0.05 or (not is_box and y + need > SLIDE_BOTTOM_IN + 0.1 and y < 7):
                    problems += 1
                    print(f"slide {i:2d}: TEXT overflow need {need:.2f}in > {limit:.2f}in  '{tf.text[:60]!r}'")
            if shp.has_table:
                tbl = shp.table
                total = 0.0
                for r in tbl.rows:
                    row_need = 0.0
                    for c_idx, cell in enumerate(r.cells):
                        cw = Emu(tbl.columns[c_idx].width).inches - 0.12
                        row_need = max(row_need, frame_height(cell.text_frame, cw) + 0.06)
                    total += max(row_need, Emu(r.height).inches)
                if y + total > SLIDE_BOTTOM_IN:
                    problems += 1
                    print(f"slide {i:2d}: TABLE bottom {y + total:.2f}in > {SLIDE_BOTTOM_IN}in (est. height {total:.2f})")
                tw = sum(Emu(c.width).inches for c in tbl.columns)
                if x + tw > 13.333 - 0.3:
                    problems += 1
                    print(f"slide {i:2d}: TABLE too wide ({x + tw:.2f}in)")
            if x + w > 13.34 or y + h > 7.51:
                problems += 1
                print(f"slide {i:2d}: SHAPE off-slide ({x + w:.2f}, {y + h:.2f})")
    print(f"{len(prs.slides)} slides checked - {problems} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
