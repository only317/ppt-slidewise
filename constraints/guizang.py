"""
Guizang Swiss International Style — Constraint Definitions.

Four palettes, five typography levels, seven layout templates, and
strict anti-decoration rules. All values are canonical; the Reviewer
Agent and ConstraintValidator both reference this file.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============================================================
# 1. PALETTES — 4 colour families
# ============================================================

@dataclass(frozen=True)
class Palette:
    name: str
    background: str      # slide background
    text_primary: str     # body / headings
    anchor: str           # single accent highlight per page
    text_secondary: str   # muted text (meta, page numbers)
    surface: str          # card / panel background
    divider: str          # thin rules / separators

PALETTES: Dict[str, Palette] = {
    "indigo": Palette(
        name="靛蓝 Indigo",
        background="#0a1f3d",
        text_primary="#f1f3f5",
        anchor="#4a90d9",
        text_secondary="#7a8ba0",
        surface="#0f2a4f",
        divider="#1e3d66",
    ),
    "ink": Palette(
        name="墨水 Ink",
        background="#0a0a0b",
        text_primary="#f1efea",
        anchor="#c9a96e",
        text_secondary="#8a8578",
        surface="#161614",
        divider="#2e2d29",
    ),
    "forest": Palette(
        name="森林 Forest",
        background="#1a2e1f",
        text_primary="#f5f1e8",
        anchor="#7a9a6e",
        text_secondary="#8a9a82",
        surface="#1f3625",
        divider="#2e4a33",
    ),
    "dune": Palette(
        name="沙丘 Dune",
        background="#1f1a14",
        text_primary="#f0e6d2",
        anchor="#d4956a",
        text_secondary="#9a8e7e",
        surface="#2a241c",
        divider="#4a4036",
    ),
}

# Swiss-light palettes — Guizang B-style original: light bg + single saturated accent
PALETTES.update({
    "klein-blue": Palette(
        name="克莱因蓝 Klein Blue",
        background="#f5f4f0",
        text_primary="#1a1a1c",
        anchor="#002FA7",
        text_secondary="#6b6b6e",
        surface="#ebeae6",
        divider="#d6d4cf",
    ),
    "lemon": Palette(
        name="柠檬黄 Lemon Yellow",
        background="#f5f4f0",
        text_primary="#1a1a1c",
        anchor="#c8a200",
        text_secondary="#6b6b6e",
        surface="#ebeae6",
        divider="#d6d4cf",
    ),
    "lime": Palette(
        name="柠绿 Lime Green",
        background="#f5f4f0",
        text_primary="#1a1a1c",
        anchor="#7a9900",
        text_secondary="#6b6b6e",
        surface="#ebeae6",
        divider="#d6d4cf",
    ),
    "safety-orange": Palette(
        name="安全橙 Safety Orange",
        background="#f5f4f0",
        text_primary="#1a1a1c",
        anchor="#d45a2e",
        text_secondary="#6b6b6e",
        surface="#ebeae6",
        divider="#d6d4cf",
    ),
})

# Hard rules (validated by Reviewer + ConstraintValidator)
FORBIDDEN_COLORS = {"#FFFFFF", "#ffffff", "#000000", "#000000"}
MAX_ANCHOR_ELEMENTS_PER_PAGE = 1

# ============================================================
# 2. TYPOGRAPHY — 5-level hierarchy
# ============================================================

@dataclass(frozen=True)
class TypographyLevel:
    name: str
    size_range: Tuple[int, int]   # (min_px, max_px)
    weight: str                   # CSS font-weight
    usage: str

TYPOGRAPHY: Dict[str, TypographyLevel] = {
    "H1": TypographyLevel("Cover Title",   (72, 96),  "200", "Cover main title"),
    "H2": TypographyLevel("Section Title", (48, 64),  "200", "Section divider pages"),
    "H3": TypographyLevel("Page Title",    (36, 48),  "300", "Content page headings"),
    "Body": TypographyLevel("Body Text",   (14, 18),  "400", "Bullets, paragraphs"),
    "Meta": TypographyLevel("Meta",        (10, 12),  "500", "Page numbers, citations"),
}

# The Iron Law: H1_min / Body_max >= 8:1
TYPOGRAPHY_IRON_RATIO = 8.0  # H1.min(72) / Body.max(18) = 4? No -> must use relaxed body

# Relaxed body for 8:1 enforcement: H1 72 / Body 9 → but minimum readable is 14px.
# So we allow 72/18 = 4:1 with a WARNING rather than error when < 8:1.
# Reviewer checks: H1/H3 >= 1.5, H3/Body >= 2.0 (enforceable).
TYPOGRAPHY_RATIO_CHECKS = {
    ("H1", "H3"): 1.5,   # H1 must be >= 1.5× H3
    ("H3", "Body"): 2.0,  # H3 must be >= 2.0× Body
}

# Forbidden: pure black, pure white text
FORBIDDEN_TEXT_COLORS = FORBIDDEN_COLORS

# ============================================================
# 3. LAYOUT TEMPLATES — 7 predefined zone skeletons
# ============================================================

@dataclass
class LayoutZone:
    """A rectangular zone within a layout template."""
    x: int
    y: int
    w: int
    h: int
    semantic: str        # "title" | "body" | "meta" | "image" | "decoration"
    align: str = "left"  # "left" | "center" | "right"
    optional: bool = False

@dataclass
class LayoutTemplate:
    id: str
    name: str
    usage: str
    zones: List[LayoutZone]
    rules: List[str] = field(default_factory=list)

LAYOUTS: Dict[str, LayoutTemplate] = {
    "L1": LayoutTemplate(
        id="L1", name="封面 Cover",
        usage="First page — centered title + subtitle + author info",
        zones=[
            LayoutZone(100, 260, 1080, 140, "title", "center"),
            LayoutZone(100, 420, 1080, 60,  "subtitle", "center"),
            LayoutZone(100, 600, 1080, 30,  "meta", "center"),
        ],
        rules=["title: H1 72-96px ExtraLight", "subtitle: Body 18px Regular",
               "meta: Meta 12px Medium", "vertically centered block"]
    ),
    "L2": LayoutTemplate(
        id="L2", name="章节分隔 Section Divider",
        usage="Section transition — large number + section title (hero page)",
        zones=[
            LayoutZone(80, 200, 200, 200, "section_number", "left"),
            LayoutZone(300, 280, 880, 100, "title", "left"),
            LayoutZone(300, 400, 560, 30,  "subtitle", "left", optional=True),
        ],
        rules=["section_number: 120px ExtraLight, anchor color",
               "title: H2 48-64px ExtraLight"]
    ),
    "L3": LayoutTemplate(
        id="L3", name="要点列表 Bullet List",
        usage="Content page — left-aligned title + 3-5 vertical bullets",
        zones=[
            LayoutZone(80, 80,  480, 80,  "title", "left"),
            LayoutZone(80, 200, 800, 420, "body", "left"),
            LayoutZone(1200, 680, 40, 20, "meta", "right"),
        ],
        rules=["title: H3 36-48px Light", "body: Body 14-18px Regular",
               "max 5 bullets", "bullet gap: 24px", "bullet marker: anchor color filled circle r=4"]
    ),
    "L4": LayoutTemplate(
        id="L4", name="图文双栏 Image+Text",
        usage="Explanation — left text + right image (or vice versa)",
        zones=[
            LayoutZone(80, 80,  480, 80,  "title", "left"),
            LayoutZone(80, 200, 520, 400, "body", "left"),
            LayoutZone(640, 160, 560, 440, "image", "center"),
            LayoutZone(1200, 680, 40, 20,  "meta", "right"),
        ],
        rules=["image zone keeps aspect ratio", "body max 4 bullets",
               "can mirror: image left, text right"]
    ),
    "L5": LayoutTemplate(
        id="L5", name="三列对比 Three-Column Compare",
        usage="Comparison — three equal-width columns",
        zones=[
            LayoutZone(80, 80,  1120, 80,  "title", "left"),
            LayoutZone(80, 200, 346, 400, "col_1", "center"),
            LayoutZone(466, 200, 346, 400, "col_2", "center"),
            LayoutZone(853, 200, 346, 400, "col_3", "center"),
            LayoutZone(1200, 680, 40, 20,  "meta", "right"),
        ],
        rules=["column gap: 40px", "each column: icon + heading + 2-3 bullets",
               "column heading: Body 18px Medium"]
    ),
    "L6": LayoutTemplate(
        id="L6", name="数据焦点 Data Focus",
        usage="Key insight — single large number + interpretation",
        zones=[
            LayoutZone(80, 160, 1120, 200, "hero_number", "center"),
            LayoutZone(80, 380, 560, 200, "body", "left"),
            LayoutZone(1200, 680, 40, 20,  "meta", "right"),
        ],
        rules=["hero_number: 120-160px ExtraLight anchor color",
               "body: max 3 bullets interpreting the number"]
    ),
    "L7": LayoutTemplate(
        id="L7", name="封底 Back Cover",
        usage="Last page — Thank you / Q&A + contact",
        zones=[
            LayoutZone(100, 280, 1080, 100, "title", "center"),
            LayoutZone(100, 400, 1080, 60,  "subtitle", "center"),
            LayoutZone(100, 600, 1080, 30,  "meta", "center"),
        ],
        rules=["title: H2 48-64px ExtraLight", "subtitle: Body 18px Regular",
               "cover/backcover anchor color must match"]
    ),
}

# ============================================================
# 4. GRID & ANTI-DECORATION RULES
# ============================================================

GRID_COLUMNS = 16
GRID_GAP = 16            # px between columns
GRID_COL_WIDTH = 62      # px per column (16*62 + 15*16 = 992+240 → close to 1280)

# Forbidden visual treatments (Swiss Internationalism)
FORBIDDEN_CSS = {
    "border-radius": "No rounded corners — only 90° angles",
    "box-shadow": "No drop shadows — flat design only",
    "linear-gradient": "No gradients — solid colors only",
    "radial-gradient": "No gradients — solid colors only",
}

# Breathing rhythm: max 2 consecutive pages with same layout
BREATHING_RHYTHM_MAX_CONSECUTIVE = 2

# Text density threshold (text area / slide area)
MAX_TEXT_DENSITY = 0.65  # 65% — Reviewer flags as error above this
