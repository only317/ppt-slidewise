"""
Guizang Style System — copied from guizang-ppt-skill by 歸藏.

Style A: 电子杂志 × 电子墨水 — 5 themes, hero dark + content light alternating.
Style B: 瑞士国际主义 — 4 themes, unified light bg + single saturated accent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    family: str            # "A" | "B"
    description: str
    # Style A uses: (background=dark ink) for hero pages, (paper=light) for content pages
    # Style B uses: (paper) for all pages, (accent) for highlights, (ink) for text
    background: str        # hero-page background (Style A) or unused (Style B)
    paper: str             # content-page background (Style A & B)
    ink: str               # hero-page text (Style A) or all-page text (Style B)
    text_on_paper: str     # text color when on paper background
    anchor: str            # accent / highlight color
    text_secondary: str    # muted text
    surface: str           # card/panel surface on paper
    divider: str           # thin rules


# ============================================================
# Style A — 电子杂志 × 电子墨水
# Hero页用 background(暗底)，内容页用 paper(暖白底)
# ============================================================

PALETTES_A: Dict[str, Palette] = {
    "ink": Palette(
        id="ink", name="墨水经典 Monocle Default", family="A",
        description="纯墨黑 + 暖米白，杂志感最强。通用 / 商业发布",
        background="#0a0a0b",   # hero页：暗墨底
        paper="#f1efea",        # 内容页：暖米白底
        ink="#f1efea",          # hero页文字：暖白
        text_on_paper="#0a0a0b",# 内容页文字：墨黑
        anchor="#c9a96e",       # 强调色：暖金
        text_secondary="#8a8578",
        surface="#e8e5de",
        divider="#d4d0c8",
    ),
    "indigo": Palette(
        id="indigo", name="靛蓝瓷 Indigo Porcelain", family="A",
        description="深靛蓝 + 瓷白，冷静理性。科技 / 研究 / 技术发布",
        background="#0a1f3d", paper="#f1f3f5",
        ink="#f1f3f5", text_on_paper="#0a1f3d",
        anchor="#4a90d9", text_secondary="#7a8ba0",
        surface="#e4e8ec", divider="#c8ced6",
    ),
    "forest": Palette(
        id="forest", name="森林墨 Forest Ink", family="A",
        description="深森林绿 + 象牙，沉稳有呼吸感。自然 / 文化 / 非虚构",
        background="#1a2e1f", paper="#f5f1e8",
        ink="#f5f1e8", text_on_paper="#1a2e1f",
        anchor="#7a9a6e", text_secondary="#8a9a82",
        surface="#ece7da", divider="#d4cec0",
    ),
    "kraft": Palette(
        id="kraft", name="牛皮纸 Kraft Paper", family="A",
        description="深棕 + 暖米，像牛皮信封。怀旧 / 人文 / 文学",
        background="#2a1e13", paper="#eedfc7",
        ink="#eedfc7", text_on_paper="#2a1e13",
        anchor="#b8753e", text_secondary="#8a7565",
        surface="#e0d0b6", divider="#c8b89e",
    ),
    "dune": Palette(
        id="dune", name="沙丘 Dune", family="A",
        description="炭灰 + 沙色，克制高级。艺术 / 设计 / 创意",
        background="#1f1a14", paper="#f0e6d2",
        ink="#f0e6d2", text_on_paper="#1f1a14",
        anchor="#d4956a", text_secondary="#9a8e7e",
        surface="#e3d7bf", divider="#c8bca4",
    ),
}

# ============================================================
# Style B — 瑞士国际主义
# 统一暖白底 + 深灰字，仅 accent 色不同
# ============================================================

PALETTES_B: Dict[str, Palette] = {
    "klein-blue": Palette(
        id="klein-blue", name="克莱因蓝 IKB", family="B",
        description="纯白底 + IKB 克莱因蓝。学术 / 通用 / AI产品",
        background="#fafaf8", paper="#fafaf8",
        ink="#0a0a0a", text_on_paper="#0a0a0a",
        anchor="#002FA7", text_secondary="#737373",
        surface="#f0f0ee", divider="#d4d4d2",
    ),
    "lemon": Palette(
        id="lemon", name="柠檬黄 Lemon Yellow", family="B",
        description="浅米白底 + 柠檬黄。年轻 / 运动 / Y2K复古",
        background="#fafaf8", paper="#fafaf8",
        ink="#0a0a0a", text_on_paper="#0a0a0a",
        anchor="#FFD500", text_secondary="#737373",
        surface="#f0f0ee", divider="#d4d4d2",
    ),
    "lime": Palette(
        id="lime", name="柠绿 Lemon Green", family="B",
        description="浅米白底 + 荧光柠绿。生态 / 未来 / Z世代",
        background="#fafaf8", paper="#fafaf8",
        ink="#0a0a0a", text_on_paper="#0a0a0a",
        anchor="#C5E803", text_secondary="#737373",
        surface="#f0f0ee", divider="#d4d4d2",
    ),
    "safety-orange": Palette(
        id="safety-orange", name="安全橙 Safety Orange", family="B",
        description="浅米白底 + 安全橙。工业 / 新闻 / 运动",
        background="#fafaf8", paper="#fafaf8",
        ink="#0a0a0a", text_on_paper="#0a0a0a",
        anchor="#FF6B35", text_secondary="#737373",
        surface="#f0f0ee", divider="#d4d4d2",
    ),
}

PALETTES = {**PALETTES_A, **PALETTES_B}

def get_palette(id: str) -> Palette:
    return PALETTES.get(id, PALETTES["indigo"])

STYLE_A_IDS = list(PALETTES_A.keys())
STYLE_B_IDS = list(PALETTES_B.keys())

# Hard rules
FORBIDDEN_COLORS = {"#FFFFFF", "#ffffff", "#000000", "#000000"}
MAX_ANCHOR_ELEMENTS_PER_PAGE = 1

# ============================================================
# Typography
# ============================================================

@dataclass(frozen=True)
class TypographyLevel:
    name: str; size_range: Tuple[int, int]; weight: str; usage: str

TYPOGRAPHY: Dict[str, TypographyLevel] = {
    "H1": TypographyLevel("Cover Title",   (72, 96),  "200", "封面主标题"),
    "H2": TypographyLevel("Section Title", (48, 64),  "200", "章节分隔页"),
    "H3": TypographyLevel("Page Title",    (36, 48),  "300", "内容页标题"),
    "Body": TypographyLevel("Body Text",   (14, 18),  "400", "要点 / 段落"),
    "Meta": TypographyLevel("Meta",        (10, 12),  "500", "页码 / 引用"),
}

TYPOGRAPHY_RATIO_CHECKS = {("H1","H3"): 1.5, ("H3","Body"): 2.0}
FORBIDDEN_TEXT_COLORS = FORBIDDEN_COLORS

# ============================================================
# Layout Templates
# ============================================================

@dataclass
class LayoutZone:
    x: int; y: int; w: int; h: int; semantic: str; align: str = "left"; optional: bool = False

@dataclass
class LayoutTemplate:
    id: str; name: str; usage: str; zones: List[LayoutZone]
    page_type: str = "content"   # "hero" | "content"
    rules: List[str] = field(default_factory=list)

LAYOUTS: Dict[str, LayoutTemplate] = {
    "L1": LayoutTemplate(id="L1", name="封面 Cover", page_type="hero",
        usage="First page", zones=[
            LayoutZone(100,260,1080,140,"title","center"),
            LayoutZone(100,420,1080,60,"subtitle","center"),
            LayoutZone(100,600,1080,30,"meta","center"),
        ]),
    "L2": LayoutTemplate(id="L2", name="章节分隔 Section Divider", page_type="hero",
        usage="Section transition", zones=[
            LayoutZone(80,200,200,200,"section_number","left"),
            LayoutZone(300,280,880,100,"title","left"),
            LayoutZone(300,400,560,30,"subtitle","left",optional=True),
        ]),
    "L3": LayoutTemplate(id="L3", name="要点列表 Bullet List",
        usage="Content — left title + 3-5 bullets", zones=[
            LayoutZone(80,80,480,80,"title","left"),
            LayoutZone(80,200,800,420,"body","left"),
            LayoutZone(1200,680,40,20,"meta","right"),
        ]),
    "L4": LayoutTemplate(id="L4", name="图文双栏 Image+Text",
        usage="Explanation", zones=[
            LayoutZone(80,80,480,80,"title","left"),
            LayoutZone(80,200,520,400,"body","left"),
            LayoutZone(640,160,560,440,"image","center"),
            LayoutZone(1200,680,40,20,"meta","right"),
        ]),
    "L5": LayoutTemplate(id="L5", name="三列对比 Three-Column",
        usage="Comparison", zones=[
            LayoutZone(80,80,1120,80,"title","left"),
            LayoutZone(80,200,346,400,"col_1","center"),
            LayoutZone(466,200,346,400,"col_2","center"),
            LayoutZone(853,200,346,400,"col_3","center"),
            LayoutZone(1200,680,40,20,"meta","right"),
        ]),
    "L6": LayoutTemplate(id="L6", name="数据焦点 Data Focus",
        usage="Key insight", zones=[
            LayoutZone(80,160,1120,200,"hero_number","center"),
            LayoutZone(80,380,560,200,"body","left"),
            LayoutZone(1200,680,40,20,"meta","right"),
        ]),
    "L7": LayoutTemplate(id="L7", name="封底 Back Cover", page_type="hero",
        usage="Last page", zones=[
            LayoutZone(100,280,1080,100,"title","center"),
            LayoutZone(100,400,1080,60,"subtitle","center"),
            LayoutZone(100,600,1080,30,"meta","center"),
        ]),
}

# ============================================================
# Grid & Anti-Decoration
# ============================================================

GRID_COLUMNS = 16
GRID_GAP = 16
GRID_COL_WIDTH = 62

FORBIDDEN_CSS = {
    "border-radius": "No rounded corners",
    "box-shadow": "No drop shadows",
    "linear-gradient": "No gradients",
    "radial-gradient": "No gradients",
}

BREATHING_RHYTHM_MAX_CONSECUTIVE = 2
MAX_TEXT_DENSITY = 0.65


# ============================================================
# Page-style helpers
# ============================================================

def get_page_colors(palette_id: str, layout_id: str) -> dict:
    """Return {bg, text, anchor} for a specific page based on layout type."""
    p = get_palette(palette_id)
    layout = LAYOUTS.get(layout_id)
    is_hero = layout.page_type == "hero" if layout else False

    if p.family == "A":
        if is_hero:
            return {"bg": p.background, "text": p.ink, "anchor": p.anchor}
        else:
            return {"bg": p.paper, "text": p.text_on_paper, "anchor": p.anchor}
    else:  # family B — all pages use same paper bg
        return {"bg": p.paper, "text": p.ink, "anchor": p.anchor}
