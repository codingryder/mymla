"""Render the MyMLA WhatsApp Business profile picture.

Single-author script — runs once, produces:
  assets/mymla_profile.png       1024×1024
  assets/mymla_profile_512.png    512×512  (Meta API upload size)

Design follows assets/PHILOSOPHY.md — "Civic Vellum".
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ─── Palette ────────────────────────────────────────────────────────────────

TEAL      = (11,  78,  86, 255)   # #0B4E56  monsoon-darkened brass
INK       = (245, 241, 232, 255)  # #F5F1E8  warm ivory
INK_DIM   = (245, 241, 232, 110)  # ivory at low opacity for vignette inside ring
GOLD_HAIR = (210, 187, 132, 200)  # #D2BB84  barely-gold hairline

# Fonts
FONTS_DIR = Path(
    "/Users/rakeshgogoi/Library/Application Support/Claude/local-agent-mode-sessions/"
    "skills-plugin/c244e1b1-c0ac-433e-ae40-b32e8603b777/"
    "59003e96-0152-4c9b-812f-60316141f3cf/skills/canvas-design/canvas-fonts"
)
LATIN_FONT_PATH = FONTS_DIR / "BigShoulders-Bold.ttf"  # condensed display sans for arched text
LATIN_FALLBACK  = FONTS_DIR / "InstrumentSans-Bold.ttf"

# macOS ships Malayalam Sangam MN — true OpenType shaping for ML script
MALAYALAM_FONT_PATH = Path("/System/Library/Fonts/Supplemental/Malayalam Sangam MN.ttc")


# ─── Canvas ─────────────────────────────────────────────────────────────────

SIZE = 1024
CENTER = SIZE / 2

# Concentric geometry (all measurements are radii):
R_OUTER         = SIZE * 0.470   # outer edge of main ring
R_OUTER_INNER   = SIZE * 0.430   # inner edge of main ring (band width = 4%)
R_GOLD          = SIZE * 0.405   # hairline gold ring
R_TEXT_TOP      = SIZE * 0.376   # baseline for top arc text
R_TEXT_BOTTOM   = SIZE * 0.378   # for malayalam bottom

# Building footprint relative to center
BUILDING_BASE_Y = CENTER + SIZE * 0.10    # ground line
BUILDING_TOP_Y  = CENTER - SIZE * 0.13    # finial tip
BUILDING_HALF_W = SIZE * 0.155            # half-width at columns


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_canvas() -> Image.Image:
    return Image.new("RGB", (SIZE, SIZE), TEAL[:3])


def draw_vignette(img: Image.Image) -> Image.Image:
    """Whisper-quiet vignette beyond the ring — reads as depth, not effect."""
    overlay = Image.new("L", (SIZE, SIZE), 0)
    d = ImageDraw.Draw(overlay)
    # Only darken OUTSIDE the outer ring — keep the seal field clean.
    for r in range(int(SIZE * 0.48), int(SIZE * 0.55), 1):
        alpha = max(0, int((r - SIZE * 0.48) / (SIZE * 0.07) * 28))
        d.ellipse(
            [CENTER - r, CENTER - r, CENTER + r, CENTER + r],
            outline=alpha,
            width=2,
        )
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=14))
    dark = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    img = Image.composite(dark, img, overlay)
    return img


def draw_rings(d: ImageDraw.ImageDraw) -> None:
    # Main heavy ring — ivory, struck like a die
    band_w = int(R_OUTER - R_OUTER_INNER)
    cx, cy = CENTER, CENTER
    r_mid = (R_OUTER + R_OUTER_INNER) / 2
    d.ellipse(
        [cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid],
        outline=INK,
        width=band_w,
    )
    # Hairline gold ring inside — the held breath
    d.ellipse(
        [cx - R_GOLD, cy - R_GOLD, cx + R_GOLD, cy + R_GOLD],
        outline=GOLD_HAIR,
        width=2,
    )


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        # last-resort fall back to default; should never trigger
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size)


# ─── Building silhouette ────────────────────────────────────────────────────

def draw_building(img: Image.Image) -> None:
    """Stylized colonial-revival assembly hall — dome, columns, plinth, steps."""
    d = ImageDraw.Draw(img, "RGBA")
    cx = CENTER
    base_y = BUILDING_BASE_Y
    half_w = BUILDING_HALF_W

    # ── Plinth + 3 steps ────────────────────────────────────────────────
    step_h = 12
    for i, w_mult in enumerate((1.20, 1.10, 1.00)):
        y_top = base_y - step_h * (3 - i)
        y_bot = y_top + step_h
        w = half_w * w_mult
        d.rectangle([cx - w, y_top, cx + w, y_bot], fill=INK)

    # ── Architrave above columns ─────────────────────────────────────────
    columns_top_y = base_y - step_h * 3 - SIZE * 0.135
    arch_h = 16
    d.rectangle(
        [cx - half_w * 1.02, columns_top_y - arch_h, cx + half_w * 1.02, columns_top_y],
        fill=INK,
    )

    # ── Columns (6, classical) ───────────────────────────────────────────
    col_count = 6
    col_w = 16
    columns_bottom_y = base_y - step_h * 3
    inner_span = half_w * 1.80         # span between outermost column edges
    pitch = inner_span / (col_count - 1)
    left_edge = cx - inner_span / 2
    for i in range(col_count):
        x = left_edge + i * pitch
        # capital
        cap_w = col_w + 8
        d.rectangle([x - cap_w / 2, columns_top_y, x + cap_w / 2, columns_top_y + 6], fill=INK)
        # shaft
        d.rectangle([x - col_w / 2, columns_top_y + 6, x + col_w / 2, columns_bottom_y - 6], fill=INK)
        # base
        d.rectangle([x - cap_w / 2, columns_bottom_y - 6, x + cap_w / 2, columns_bottom_y], fill=INK)

    # ── Drum below dome ──────────────────────────────────────────────────
    drum_top_y = columns_top_y - arch_h - 38
    drum_h = 38
    drum_w = half_w * 0.72
    d.rectangle(
        [cx - drum_w, drum_top_y, cx + drum_w, columns_top_y - arch_h],
        fill=INK,
    )
    # tiny molding under drum
    d.rectangle(
        [cx - drum_w * 1.10, drum_top_y - 6, cx + drum_w * 1.10, drum_top_y],
        fill=INK,
    )

    # ── Dome (semicircle on top of drum) ─────────────────────────────────
    dome_r = drum_w * 0.95
    dome_cy = drum_top_y - 6
    d.pieslice(
        [cx - dome_r, dome_cy - dome_r, cx + dome_r, dome_cy + dome_r],
        start=180, end=360, fill=INK,
    )

    # ── Finial: small ball + spire ───────────────────────────────────────
    finial_x = cx
    ball_y = dome_cy - dome_r
    d.ellipse([finial_x - 7, ball_y - 14, finial_x + 7, ball_y], fill=INK)
    # spire
    spire_top = ball_y - 36
    d.polygon(
        [(finial_x - 3, ball_y - 14),
         (finial_x + 3, ball_y - 14),
         (finial_x, spire_top)],
        fill=INK,
    )

    # ── Ground baseline under steps ──────────────────────────────────────
    ground_y = base_y + 18
    d.line(
        [(cx - half_w * 1.55, ground_y), (cx + half_w * 1.55, ground_y)],
        fill=INK, width=3,
    )
    # two whisper-thin flourishes
    flourish_y = ground_y + 14
    for sign in (-1, +1):
        d.line(
            [(cx + sign * half_w * 0.30, flourish_y),
             (cx + sign * half_w * 1.30, flourish_y)],
            fill=INK, width=1,
        )


# ─── Arched top text ────────────────────────────────────────────────────────

def draw_top_arc_text(img: Image.Image, text: str) -> None:
    """Set each glyph radially so its spine points at the seal's centre."""
    font_size = 110
    font = load_font(LATIN_FONT_PATH, font_size)
    if font is ImageFont.load_default():
        font = load_font(LATIN_FALLBACK, font_size)

    # Measure widths to compute an even angular spread.
    widths: list[int] = []
    dummy = Image.new("RGB", (10, 10))
    dd = ImageDraw.Draw(dummy)
    for ch in text:
        bbox = dd.textbbox((0, 0), ch, font=font)
        widths.append(bbox[2] - bbox[0])

    radius = R_TEXT_TOP - font_size * 0.45  # radius of the visual baseline
    # Tracking — extra letterspacing for that engraved feel
    tracking_px = 24
    total_arc_px = sum(widths) + tracking_px * (len(text) - 1)
    total_angle = total_arc_px / radius  # radians
    # Center the arc at the top of the circle (angle = -π/2)
    start_angle = -math.pi / 2 - total_angle / 2

    cursor = 0
    for ch, w in zip(text, widths):
        glyph_center_arc = cursor + w / 2
        cursor += w + tracking_px
        theta = start_angle + glyph_center_arc / radius
        # Position
        gx = CENTER + radius * math.cos(theta)
        gy = CENTER + radius * math.sin(theta)
        # Rotate so the glyph's local y-axis points outward FROM centre
        rotation_deg = -math.degrees(theta + math.pi / 2)
        # Render the glyph on a transparent tile, then paste rotated
        bbox = dd.textbbox((0, 0), ch, font=font)
        tile_w = bbox[2] - bbox[0] + 20
        tile_h = bbox[3] - bbox[1] + 20
        tile = Image.new("RGBA", (tile_w, tile_h), (0, 0, 0, 0))
        td = ImageDraw.Draw(tile)
        td.text((10 - bbox[0], 10 - bbox[1]), ch, font=font, fill=INK)
        rotated = tile.rotate(rotation_deg, resample=Image.BICUBIC, expand=True)
        rw, rh = rotated.size
        img.paste(rotated, (int(gx - rw / 2), int(gy - rh / 2)), rotated)


# ─── Malayalam — straight, anchored at bottom inside ring ───────────────────

def draw_bottom_malayalam(img: Image.Image, text: str) -> None:
    """Malayalam requires complex shaping (vowel signs, chillu, joiners),
    so we draw the string as a single horizontal block — PIL + FreeType
    handles full shaping for system fonts.

    The line sits comfortably inside the ring chord at this latitude, with
    margin of at least 40 px between text edge and ring inner edge.
    """
    font_size = 54
    font = load_font(MALAYALAM_FONT_PATH, font_size)
    d = ImageDraw.Draw(img, "RGBA")
    bbox = d.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Target a vertical centre at 64 % from canvas centre to inner ring — high
    # enough that the chord (≈ 720 px wide at this latitude) clears the text
    # by a wide margin on both sides.
    target_cy = CENTER + R_OUTER_INNER * 0.64
    y = target_cy - th / 2 - bbox[1]
    x = CENTER - tw / 2 - bbox[0]
    d.text((x, y), text, font=font, fill=INK)

    # Small ornamental dots flanking the line
    dot_y = target_cy
    dot_offset = tw / 2 + 44
    for sign in (-1, +1):
        cx = CENTER + sign * dot_offset
        d.ellipse([cx - 4, dot_y - 4, cx + 4, dot_y + 4], fill=INK)


# ─── Composer ───────────────────────────────────────────────────────────────

def build() -> Image.Image:
    img = make_canvas()
    img = draw_vignette(img)
    d = ImageDraw.Draw(img, "RGBA")
    draw_rings(d)
    draw_building(img)
    draw_top_arc_text(img, "MYMLA")
    draw_bottom_malayalam(img, "എന്റെ എം.എൽ.എ")
    return img


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    img = build()
    big = out_dir / "mymla_profile.png"
    small = out_dir / "mymla_profile_512.png"
    img.save(big, "PNG")
    img.resize((512, 512), Image.LANCZOS).save(small, "PNG")
    print(f"WROTE {big}")
    print(f"WROTE {small}")


if __name__ == "__main__":
    main()
