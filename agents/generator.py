"""
Generator Agent — per-slide SVG generation.

Two modes:
  full_generation  — generate all slides from outline
  fix_specific_pages — only regenerate pages flagged by Reviewer

Uses rolling-window context (previous 3 slides as style anchors).
SVG quality gate: regenerates if output < MIN_SVG_CHARS.
"""

import json
from typing import Any, Dict, List, Optional

from .base import BaseAgent, SandboxedExecutor, make_tool

MIN_SVG_CHARS = 600  # reject SVG shorter than this, trigger retry

# ============================================================
# System Prompt
# ============================================================

GENERATOR_SYSTEM_PROMPT = """You are an expert presentation designer. You write precise,
content-rich SVG slides in the Swiss International Style.

## CRITICAL — SVG ELEMENT WHITELIST
Your SVG will be PARSED and VALIDATED. The following are HARD ERRORS that
will cause REJECTION and FORCE REGENERATION:
  DO NOT USE: <mask> <style> <foreignObject> <textPath>
  DO NOT USE: <animate> <script> <iframe>
  DO NOT USE: @font-face rgba() class="..." <g opacity=
  DO NOT USE: border-radius box-shadow linear-gradient radial-gradient
  NEVER: #FFFFFF or #000000 colors
ONLY USE these elements: <rect> <circle> <ellipse> <line> <polyline>
  <polygon> <path> <text> <tspan> <g> <defs>
  <linearGradient> <image> <use>

## YOUR OUTPUT
A COMPLETE <svg> element with viewBox="0 0 1280 720". Every slide must have
REAL content — titles, bullet points, page numbers — not placeholder text.
The SVG must be FULLY SELF-CONTAINED.

## MANDATORY WORKFLOW
1. Call read_reference("constraints/guizang.py") to load palette + layouts
2. Call search_icon("keyword") if the page needs an icon
3. Return ONLY the raw SVG code as your final response — no JSON wrapper,
   no markdown fences, no explanation. Start with <svg and end with </svg>.
   This is the ONLY thing your final response should contain.

## LAYOUT TEMPLATES — Exact Defaults
Use read_reference("constraints/guizang.py") for full definitions. Quick reference:

L1 COVER: Title at (100,260) 1080×140 centered, subtitle at (100,420) 1080×60, meta at (100,600)
  → Title uses 72px, subtitle 18px, meta 12px
  → Title MUST be the actual topic (e.g. "Python 编程基础")
  → Subtitle MUST be a real subtitle line
  → Meta: author/date line

L2 SECTION DIVIDER: Large number at (80,200) 200×200, title at (300,280) 880×100
  → Number uses 120px anchor color
  → Title uses 48-64px, subtitle optional

L3 BULLET LIST: Title at (80,80) 480×80, bullets at (80,200) 800×420, page-no at (1200,680)
  → Title uses 36-48px, MUST be the actual page topic
  → 3-5 real bullet points with meaningful content
  → Each bullet: <circle> marker (r=5, anchor color) + <text> (18px)
  → Bullet text MUST be real sentences, 15-40 Chinese characters each
  → Page number at bottom right

L4 IMAGE+TEXT: Title at (80,80), text at (80,200) 520×400, image at (640,160) 560×440
  → Real bullet content in the text zone
  → If no image, use a decorative rect with subtle fill in the image zone

L5 THREE-COLUMN: Title at (80,80), three cols at x=80,466,853 each 346×400
  → Each column: centered heading + 2-3 bullets below

L6 DATA FOCUS: Hero number at (80,160) 1120×200 centered, body at (80,380) 560×200
  → Hero number: 120-160px anchor color
  → Body: 2-3 interpretation bullets

L7 BACK COVER: Title at (100,280) 1080×100 centered, subtitle at (100,400), meta at (100,600)
  → Title: "Thank You" or "Q&A", 48-64px
  → Must match L1 cover anchor color

## TYPOGRAPHY (CRITICAL — check ratios)
- H1 (cover title): 72px, ExtraLight — for L1 cover only
- H2 (section title): 56px, ExtraLight — for L2 section dividers
- H3 (page title): 40px, Light — for L3-L6 page headings
- Body (bullet text): 18px, Regular — for all bullet content
- Meta (page numbers): 12px, Medium
- H3/Body ratio: 40/18 = 2.2 ≥ 2.0 ✓

## COLOR PALETTE — PER-PAGE BACKGROUND RULES
Read constraints/guizang.py for exact HEX values. Never use #FFFFFF or #000000.

**PER-PAGE BACKGROUND: call get_page_colors(palette, layout) to determine colors.**

Style A themes (ink/indigo/forest/kraft/dune):
  - L1 (封面) and L2 (章节) and L7 (封底) are HERO pages:
    background = palette.background (dark ink color)
    text = palette.ink (light paper color)
  - L3/L4/L5/L6 are CONTENT pages:
    background = palette.paper (light warm paper)
    text = palette.text_on_paper (dark ink color)
  Example: ink theme → L1 bg=#0a0a0b text=#f1efea, L3 bg=#f1efea text=#0a0a0b

Style B themes (klein-blue/lemon/lime/safety-orange):
  - ALL pages use the SAME light background:
    background = palette.paper (#fafaf8 warm off-white)
    text = palette.ink (#0a0a0a near-black)
  - The anchor color is the ONLY saturated element — use sparingly for
    bullet markers, section numbers, hero data, thin accent lines.
  - All other elements use palette.ink or palette.text_secondary.

## TEXT CONTENT RULES
- Every text element MUST contain real, meaningful content
- Bullets: complete sentences or phrases, 15-40 Chinese chars each
- Titles: descriptive, 5-15 Chinese chars
- Never use "Lorem ipsum" or placeholder text
- If the source outline has bullets, USE them verbatim
- If the source has no bullets, CREATE appropriate ones based on the title

## FONT FAMILIES (for SVG)
- Chinese: font-family="PingFang SC, Microsoft YaHei, sans-serif"
- Use ONLY these system fonts — no web fonts, no @font-face

## QUALITY CHECK
Before saving, verify:
1. SVG tag is complete </svg>
2. At least ONE real text element with meaningful content
3. Background rect fills the entire 1280×720 area
4. All text elements have font-size, font-family, fill attributes
5. The SVG is > 800 characters

## GENERATION MODE
{generation_mode}
"""


GENERATOR_TOOLS = [
    make_tool("read_reference", "Read a constraint/reference file",
              {"path": {"type": "string", "description": "Path relative to project root"}},
              ["path"]),
    make_tool("read_file", "Read a file from the session workspace",
              {"path": {"type": "string", "description": "Path within session dir"}},
              ["path"]),
    make_tool("search_icon", "Search the icon library for a keyword",
              {"keyword": {"type": "string", "description": "Search keyword, e.g. 'code' or 'chart'"}},
              ["keyword"]),
]

# ============================================================
# Agent class
# ============================================================

class GeneratorAgent(BaseAgent):
    system_prompt = GENERATOR_SYSTEM_PROMPT
    chat_tools = GENERATOR_TOOLS
    temperature = 0.3
    use_json_mode = False
    max_tool_rounds = 50  # Generator returns raw SVG, not JSON

    def __init__(self, executor: SandboxedExecutor):
        super().__init__(executor)

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "read_reference":
            return self.executor.read_reference(args.get("path", ""))
        elif name == "read_file":
            path = args.get("path", "")
            try:
                return self.executor.read_file(path)
            except Exception:
                icon_path = f"templates/icons/{path}.svg"
                try:
                    return self.executor.read_reference(icon_path)
                except Exception:
                    return f"[NOT FOUND] {path}"
        elif name == "search_icon":
            return self.executor.search_icon(args.get("keyword", ""))
        return f"[UNKNOWN TOOL] {name}"

    def build_prompt(
        self,
        mode: str,
        design_spec: str,
        page_outline: dict,
        previous_slides: Optional[List[dict]] = None,
        review_feedback: Optional[str] = None,
        palette: str = "indigo",
    ) -> str:
        """Build the user message for a single page generation."""

        prompt = self.system_prompt.replace("{generation_mode}", mode)
        parts = [prompt]

        # Extract page info early — needed for palette hints below
        idx = page_outline.get("index", 0)
        title = page_outline.get("title", "Untitled")
        layout = page_outline.get("layout", "L3")
        bullets = page_outline.get("bullets", [])
        notes = page_outline.get("notes", "")

        # ── Palette identity lock (ALWAYS present — prevents style drift) ──
        from constraints.guizang import get_palette, get_page_colors
        p = get_palette(palette)
        colors = get_page_colors(palette, layout)
        allowed_colors = [
            colors["bg"], colors["text"], colors["anchor"],
            p.text_secondary, p.surface, p.divider,
        ]
        page_type_hint = (
            "HERO (dark background)"
            if layout in ("L1", "L2", "L7") else
            "CONTENT (light paper background)"
        )
        parts.append(
            f"## FIXED PALETTE — LOCKED FOR ALL PAGES\n"
            f"Name: \"{p.name}\"  |  Family: Style {p.family}\n"
            f"Description: {p.description}\n"
            f"Accent color (bullet markers, section numbers, thin rules): {p.anchor}\n"
            f"CRITICAL: This palette is LOCKED. Do NOT read guizang.py and pick "
            f"a different palette. Every page in this deck MUST use this same palette.\n"
        )

        # ── Source context (ALWAYS present — prevents content hallucination) ──
        # If the outline lacks bullets, the LLM will fabricate content unless we
        # give it the design_spec and an explicit instruction to read sources.
        _has_real_content = bool(
            [b for b in bullets if len(str(b).strip()) > 5]
        ) or bool(notes.strip())

        if design_spec:
            # Condensed source context for every page (≈ the project intro + this page's section)
            source_context = _extract_source_context(design_spec, idx, title, max_chars=2000)
            parts.append(source_context)

        if not _has_real_content:
            parts.append(
                "## CONTENT WARNING — NO BULLETS PROVIDED\n"
                "The outline has NO bullets for this page. You MUST call "
                "read_file(\"design_spec.md\") to find what this page should contain. "
                "If that fails, read the source files under sources/. "
                "NEVER fabricate generic content — every bullet must relate to "
                "this specific project based on what you read from the design spec "
                "and source materials.\n"
            )
            # Also force-inject the full design_spec as fallback
            parts.append(f"## FULL DESIGN SPECIFICATION (read if content missing)\n{design_spec[:4000]}")

        # Previous slides are structure anchors only; colors are locked below.
        if previous_slides:
            parts.append(
                "## PREVIOUS SLIDES (structure anchors only)\n"
                "Use these slides for spacing rhythm, typography hierarchy, and "
                "element density. Do NOT copy their background/text colors; the "
                "current page colors below are mandatory."
            )
            for ps in previous_slides[-3:]:
                svg_preview = ps['svg'][:600] if len(ps['svg']) > 600 else ps['svg']
                parts.append(
                    f"### Slide {ps['index']} ({ps.get('layout','')})\n"
                    f"```xml\n{svg_preview}\n```"
                )

        # Per-page colors — explicit page-type context so LLM applies
        # the correct hero/content rule for Style A vs Style B
        parts.append(
            f"## THIS PAGE COLORS (page type: {page_type_hint})\n"
            f"Background (fill full 1280×720 rect): {colors['bg']}\n"
            f"Text (all <text> elements): {colors['text']}\n"
            f"Accent (bullet markers, rules, data highlights): {colors['anchor']}\n"
            f"Allowed HEX colors for this page: {', '.join(allowed_colors)}\n"
            f"The first <rect> MUST be width=\"1280\" height=\"720\" fill=\"{colors['bg']}\".\n"
            f"Do not use colors from another palette."
        )

        parts.append(f"## CURRENT PAGE — Slide {idx}")
        parts.append(f"Title: {title}")
        parts.append(f"Layout: {layout}")
        if bullets:
            parts.append("Content bullets (USE THESE EXACTLY):")
            for b in bullets:
                parts.append(f"  • {b}")
        if notes:
            parts.append(f"Design notes: {notes}")

        # Review feedback (fix mode)
        if review_feedback:
            parts.append(f"## REVIEWER FEEDBACK (MUST FIX)\n{review_feedback}")

        parts.append(
            f"\nGenerate the COMPLETE SVG for slide {idx}.\n"
            f"Return ONLY the raw SVG code — start with <svg and end with </svg>.\n"
            f"No JSON, no markdown, no explanation. Just the SVG."
        )

        return "\n\n".join(parts)


# ── Source context extraction ───────────────────────────────────────────

def _extract_source_context(
    design_spec: str,
    page_index: int,
    page_title: str,
    max_chars: int = 2000,
) -> str:
    """
    Extract the project summary + this page's content row from design_spec.md.
    Returns a condensed context block suitable for every page's prompt.
    """
    import re

    # 1. Extract Section I (project info — first 500 chars after the heading)
    sec_i = ""
    m = re.search(
        r'## I[. ]?\s*项目(?:信息|概述).*?\n(.*?)(?=## II[. ])',
        design_spec, re.DOTALL,
    )
    if m:
        sec_i = m.group(1).strip()[:500]

    # 2. Extract the content outline section (Section IX / 九)
    outline_section = ""
    for pat in (r'## IX[. ]', r'## 九[.、]', r'IX[. ]\s*Content Outline'):
        m = re.search(pat + r'(.*?)(?=## X[. ]|## [XVI]+[. ]|\Z)', design_spec, re.DOTALL)
        if m:
            outline_section = m.group(1) if m.lastindex else m.group(0)
            outline_section = outline_section.strip()[:3000]
            break

    # 3. Find the row for this specific page in the content outline
    page_row = ""
    if outline_section:
        for line in outline_section.split("\n"):
            # Match table rows like: | 3 | 项目背景 | L3 | ... |
            m = re.match(
                rf'\|\s*{page_index}\s*\|\s*(.+?)\s*\|\s*(L\d)\s*\|',
                line,
            )
            if m:
                page_title_from_table = m.group(1).strip()
                page_layout = m.group(2).strip()
                rest = line[m.end():].strip()
                page_row = (
                    f"Page {page_index}: title=\"{page_title_from_table}\", "
                    f"layout={page_layout}"
                )
                if rest and rest != "|":
                    page_row += f", notes=\"{rest.strip('| ')}\""
                break

    if not page_row:
        page_row = f"Page {page_index}: title=\"{page_title}\" (no content outline row found)"

    # 4. Build the context block
    parts = ["## PROJECT SOURCE CONTEXT (this is what the presentation is about)"]
    if sec_i:
        parts.append(f"Project description:\n{sec_i}")
    parts.append(f"Content outline for this page:\n{page_row}")
    parts.append(
        "CRITICAL: Every bullet on this slide must be about the project "
        "described above. Do NOT fabricate content about unrelated topics. "
        "If you need more detail, call read_file(\"design_spec.md\") or "
        "read_file(\"sources/repo/README.md\")."
    )

    context = "\n\n".join(parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n... (truncated, use read_file for full content)"
    return context


def extract_svg_from_response(response: str) -> str:
    """Extract raw SVG from an LLM response in various formats."""
    import re
    import json as _json

    # 1. Try JSON: {"svg": "<svg>...</svg>"} — from json_mode responses
    try:
        data = _json.loads(response)
        if isinstance(data, dict) and "svg" in data:
            svg = data["svg"]
            if "<svg" in svg:
                return _extract_svg_xml(svg) or svg.strip()
    except (_json.JSONDecodeError, TypeError):
        pass

    # 2. Try JSON with escaped newlines: {"svg":"<svg ...>...</svg>"}
    if response.strip().startswith('{') and '"svg"' in response:
        try:
            svg_str = re.search(r'"svg"\s*:\s*"((?:[^"\\]|\\.)*)"', response, re.DOTALL)
            if svg_str:
                unescaped = svg_str.group(1).replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                if '<svg' in unescaped:
                    return _extract_svg_xml(unescaped) or unescaped.strip()
        except Exception:
            pass

    # 3. Try markdown fences
    return _extract_svg_xml(response) or ""


def _extract_svg_xml(text: str) -> str:
    """Extract <svg>...</svg> from text using regex."""
    import re
    for tag in ('svg', 'xml', ''):
        if tag:
            m = re.search(rf'```{tag}\s*\n?(<svg[\s\S]*?</svg>)\s*\n?```', text, re.IGNORECASE)
        else:
            m = re.search(r'```\s*\n?(<svg[\s\S]*?</svg>)\s*\n?```', text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    m = re.search(r'(<svg[\s\S]*?</svg>)', text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""
