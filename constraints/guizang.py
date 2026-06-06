"""
Guizang Style System — Two distinct style families.

Style A: 电子杂志 × 电子墨水 (Editorial Magazine × E-Ink)
  Dark backgrounds, warm text, serif titles, alternating hero/info rhythm.
  Best for: narrative, opinion, sharing, personal expression.
  Palettes: ink, indigo, forest, dune

Style B: 瑞士国际主义 (Swiss Internationalism)
  Light backgrounds, single saturated anchor color, 16-col grid,
  sharp corners, hairline rules, extreme font-size contrast.
  Best for: facts, products, analysis, methodology.
  Palettes: klein-blue, lemon, lime, safety-orange
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ============================================================
# Palette
# ============================================================

@dataclass(frozen=True)
class Palette:
    name: str
    family: str           # "A" = dark magazine, "B" = light Swiss
    description: str
    background: str
    text_primary: str
    anchor: str
    text_secondary: str
    surface: str
    divider: str

# ============================================================
# Style A — 电子杂志 × 电子墨水 (Dark, editorial, narrative)
# ============================================================

PALETTES: Dict[str, Palette] = {
    "ink": Palette(
        name="墨水 Ink",
        family="A",
        description="像 Monocle 杂志 — 深邃、权威、适合叙事与观点表达",
        background="#0a0a0b",
        text_primary="#f1efea",
        anchor="#c9a96e",
        text_secondary="#8a8578",
        surface="#161614",
        divider="#2e2d29",
    ),
    "indigo": Palette(
        name="靛蓝瓷 Indigo",
        family="A",
        description="暗夜蓝底 — 科技感、适合 AI / 研究 / 正式汇报",
        background="#0a1f3d",
        text_primary="#f1f3f5",
        anchor="#4a90d9",
        text_secondary="#7a8ba0",
        surface="#0f2a4f",
        divider="#1e3d66",
    ),
    "forest": Palette(
        name="森林墨 Forest",
        family="A",
        description="墨绿色调 — 自然、文化、跨学科话题",
        background="#1a2e1f",
        text_primary="#f5f1e8",
        anchor="#7a9a6e",
        text_secondary="#8a9a82",
        surface="#1f3625",
        divider="#2e4a33",
    ),
    "dune": Palette(
        name="沙丘 Dune",
        family="A",
        description="暖棕底色 — 怀旧、人文、创意表达",
        background="#1f1a14",
        text_primary="#f0e6d2",
        anchor="#d4956a",
        text_secondary="#9a8e7e",
        surface="#2a241c",
        divider="#4a4036",
    ),
}

# ============================================================
# Style B — 瑞士国际主义 (Light, Swiss, analytical)
# ============================================================

PALETTES.update({
    "klein-blue": Palette(
        name="克莱因蓝 Klein Blue",
        family="B",
        description="国际克莱因蓝 IKB — 纯净、学术、产品分析",
        background="#fafaf8",
        text_primary="#1a1a1c",
        anchor="#002FA7",       # Authentic International Klein Blue
        text_secondary="#6b6b6e",
        surface="#f0efec",
        divider="#d6d4cf",
    ),
    "lemon": Palette(
        name="柠檬黄 Lemon Yellow",
        family="B",
        description="明亮柠檬黄 — 年轻、零售、Y2K 美学",
        background="#fafaf8",
        text_primary="#1a1a1c",
        anchor="#FFD500",       # Original Guizang Lemon Yellow
        text_secondary="#6b6b6e",
        surface="#f0efec",
        divider="#d6d4cf",
    ),
    "lime": Palette(
        name="柠绿 Lime Green",
        family="B",
        description="荧光柠绿 — 生态、健康、Z 世代",
        background="#fafaf8",
        text_primary="#1a1a1c",
        anchor="#C5E803",       # Original Guizang Lime Green
        text_secondary="#6b6b6e",
        surface="#f0efec",
        divider="#d6d4cf",
    ),
    "safety-orange": Palette(
        name="安全橙 Safety Orange",
        family="B",
        description="高饱和安全橙 — 新闻、运动、工业风",
        background="#fafaf8",
        text_primary="#1a1a1c",
        anchor="#FF6B35",       # Original Guizang Safety Orange
        text_secondary="#6b6b6e",
        surface="#f0efec",
        divider="#d6d4cf",
    ),
})

# Style family helpers
def get_palette_ids_by_family(family: str) -> List[str]:
    return [k for k, v in PALETTES.items() if v.family == family]

STYLE_A_IDS = get_palette_ids_by_family("A")
STYLE_B_IDS = get_palette_ids_by_family("B")

# Hard rules
FORBIDDEN_COLORS = {"#FFFFFF", "#ffffff", "#000000", "#000000"}
MAX_ANCHOR_ELEMENTS_PER_PAGE = 1

# ============================================================
# Typography — 5-level hierarchy
# ============================================================

@dataclass(frozen=True)
class TypographyLevel:
    name: str
    size_range: Tuple[int, int]
    weight: str
    usage: str

TYPOGRAPHY: Dict[str, TypographyLevel] = {
    "H1": TypographyLevel("Cover Title",   (72, 96),  "200", "Cover main title"),
    "H2": TypographyLevel("Section Title", (48, 64),  "200", "Section divider pages"),
    "H3": TypographyLevel("Page Title",    (36, 48),  "300", "Content page headings"),
    "Body": TypographyLevel("Body Text",   (14, 18),  "400", "Bullets, paragraphs"),
    "Meta": TypographyLevel("Meta",        (10, 12),  "500", "Page numbers, citations"),
}

# Style B enforces ≥8:1 H1:Body; Style A is more relaxed
TYPOGRAPHY_RATIO_CHECKS = {
    ("H1", "H3"): 1.5,
    ("H3", "Body"): 2.0,
}

FORBIDDEN_TEXT_COLORS = FORBIDDEN_COLORS

# ============================================================
# Layout Templates — 7 predefined zone skeletons
# ============================================================

@dataclass
class LayoutZone:
    x: int; y: int; w: int; h: int
    semantic: str
    align: str = "left"
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
# Grid & Anti-Decoration
# ============================================================

GRID_COLUMNS = 16
GRID_GAP = 16
GRID_COL_WIDTH = 62

FORBIDDEN_CSS = {
    "border-radius": "No rounded corners — only 90° angles",
    "box-shadow": "No drop shadows — flat design only",
    "linear-gradient": "No gradients — solid colors only",
    "radial-gradient": "No gradients — solid colors only",
}

BREATHING_RHYTHM_MAX_CONSECUTIVE = 2
MAX_TEXT_DENSITY = 0.65
