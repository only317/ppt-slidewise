"""
Precise text pixel-width measurement engine.

Two-layer design:
  Layer A — estimate_width()    : fast heuristic (no external font files)
  Layer B — measure_width()     : PIL ImageFont.getlength() for pixel accuracy

Used by ConstraintValidator for text overflow detection.
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TextElement:
    """Parsed representation of an SVG <text> element."""
    text: str
    font_size: float
    font_family: str
    x: float
    y: float
    element_id: str = ""
    container_width: float = 0  # parent rect/zone width (0 = unknown)
    container_height: float = 0


@dataclass
class MeasuredText:
    """Text element with measured rendering width."""
    text: str
    font_size: float
    measured_width: float  # pixels
    container_width: float
    overflow_ratio: float  # measured / container, >1 = overflow
    element_id: str = ""
    method: str = "estimate"  # "estimate" | "pil"


_ATTR_RE = re.compile(r'([:\w-]+)\s*=\s*"([^"]*)"')


def _parse_attrs(attr_text: str) -> Dict[str, str]:
    """Parse simple SVG attributes from a tag."""
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(attr_text)}


def _float_attr(attrs: Dict[str, str], name: str, default: float = 0.0) -> float:
    raw = attrs.get(name)
    if raw is None:
        return default
    match = re.match(r'\s*(-?\d+(?:\.\d+)?)', raw)
    return float(match.group(1)) if match else default


def _strip_svg_tags(content: str) -> str:
    content = re.sub(r'<tspan[^>]*>', '', content)
    content = re.sub(r'</tspan>', '', content)
    content = re.sub(r'<[^>]+>', '', content)
    return content.strip()


# ============================================================
# Layer A: Fast heuristic estimation (no dependencies)
# ============================================================

def estimate_text_width(text: str, font_size: float) -> float:
    """
    Heuristic width estimation. Works without PIL or font files.

    Rules:
      - CJK character (U+4E00-U+9FFF, U+3000-U+303F, U+FF00-U+FFEF): 1.0 × font_size
      - Latin / digit / punctuation: 0.55 × font_size
      - Space: 0.3 × font_size
    """
    width = 0.0
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF or 0x3000 <= cp <= 0x303F or
                0xFF00 <= cp <= 0xFFEF or 0x3040 <= cp <= 0x309F or
                0x30A0 <= cp <= 0x30FF or 0xAC00 <= cp <= 0xD7AF):
            width += font_size * 1.0
        elif ch == ' ':
            width += font_size * 0.3
        else:
            width += font_size * 0.55
    return width


# ============================================================
# Layer B: PIL precise measurement
# ============================================================

# Platform-specific font paths
_FONT_SEARCH_PATHS = [
    # Windows
    "C:/Windows/Fonts",
    # macOS
    "/System/Library/Fonts",
    "/Library/Fonts",
    # Linux
    "/usr/share/fonts",
]

_FONT_FALLBACKS = {
    "microsoft yahei": ["msyh.ttc", "msyhbd.ttc", "Microsoft YaHei.ttf"],
    "simhei": ["simhei.ttf", "SimHei.ttf"],
    "simsun": ["simsun.ttc", "SimSun.ttf"],
    "arial": ["arial.ttf", "Arial.ttf"],
    "helvetica neue": ["HelveticaNeue.ttf", "Helvetica.ttf"],
    "pingfang sc": ["PingFang SC.ttf"],
}


def _find_font_file(font_family: str) -> Optional[str]:
    """Search for a font file on the system."""
    family_lower = font_family.lower().strip().strip('"\'')
    candidates = _FONT_FALLBACKS.get(family_lower, [f"{family_lower}.ttf"])

    for search_root in _FONT_SEARCH_PATHS:
        if not os.path.isdir(search_root):
            continue
        for root, _, files in os.walk(search_root):
            for candidate in candidates:
                if candidate.lower() in [f.lower() for f in files]:
                    for f in files:
                        if f.lower() == candidate.lower():
                            return os.path.join(root, f)
    return None


def measure_text_width_pil(
    text: str, font_size: float, font_family: str = "Microsoft YaHei"
) -> Tuple[float, str]:
    """
    Measure text width using PIL ImageFont.

    Returns (width_px, method) where method is "pil" or "estimate".
    Falls back to estimate if font file not found.
    """
    try:
        from PIL import ImageFont

        font_path = _find_font_file(font_family)
        if font_path is None:
            # Try common defaults
            for fallback in ["msyh.ttc", "arial.ttf"]:
                font_path = _find_font_file(fallback)
                if font_path:
                    break

        if font_path:
            font = ImageFont.truetype(font_path, size=int(font_size))
            # getlength() works for all text; getbbox() is per-glyph
            width = font.getlength(text)
            return width, "pil"

    except (ImportError, OSError):
        pass

    # Fallback to estimation
    return estimate_text_width(text, font_size), "estimate"


# ============================================================
# SVG Text Element Parser
# ============================================================

def parse_svg_text_elements(svg_content: str) -> List[TextElement]:
    """
    Extract all <text> elements from SVG content with their container sizes.

    Handles:
      - <text x="..." y="..." font-size="..." font-family="...">content</text>
      - <tspan x="..." y="...">content</tspan> within <text>
      - Container width from parent <rect> or layout zone heuristic
    """
    elements: List[TextElement] = []

    # Find all <text> blocks
    text_blocks = re.finditer(
        r'<text[^>]*?(?:>.*?</text>)',
        svg_content, re.DOTALL
    )

    for block in text_blocks:
        block_text = block.group()
        attrs_match = re.search(r'<text([^>]*)>', block_text)
        if not attrs_match:
            continue
        attrs = attrs_match.group(1)

        # Parse attributes
        parsed_attrs = _parse_attrs(attrs)
        x = _float_attr(parsed_attrs, "x", 0.0)
        y = _float_attr(parsed_attrs, "y", 0.0)
        font_size = _float_attr(parsed_attrs, "font-size", 18.0)
        font_family = parsed_attrs.get("font-family", "Microsoft YaHei")
        el_id = parsed_attrs.get("id", "")

        # Extract text content
        content_match = re.search(r'<text[^>]*>(.*?)</text>', block_text, re.DOTALL)
        if not content_match:
            continue
        content = content_match.group(1)

        content = _strip_svg_tags(content)
        if not content:
            continue

        # Estimate container width from parent rect
        container_w = _find_container_width(svg_content, x, y)

        elements.append(TextElement(
            text=content, font_size=font_size, font_family=font_family,
            x=x, y=y, element_id=el_id, container_width=container_w,
        ))

    return elements


def _find_container_width(svg_content: str, text_x: float, text_y: Optional[float] = None) -> float:
    """
    Heuristic: find the nearest <rect> or layout zone that contains text_x.
    Defaults to 1280 - margins if not found.
    """
    best_w = 1120.0  # default safe width (1280 - 80*2 margins)
    candidates: List[float] = []
    for r in re.finditer(r'<rect\b([^>]*)>', svg_content, re.IGNORECASE):
        attrs = _parse_attrs(r.group(1))
        rx = _float_attr(attrs, "x", 0.0)
        ry = _float_attr(attrs, "y", 0.0)
        rw = _float_attr(attrs, "width", 0.0)
        rh = _float_attr(attrs, "height", 0.0)
        if rw <= 0 or rw >= 1200:
            continue
        if text_y is not None and rh > 0 and not (ry <= text_y <= ry + rh + 8):
            continue
        if rx <= text_x <= rx + rw:
            candidates.append(rw)
    if candidates:
        non_page = [w for w in candidates if w < 1200]
        best_w = min(non_page or candidates)
    return best_w


# ============================================================
# Unified measurement API
# ============================================================

def measure_svg_text(svg_content: str, use_pil: bool = True) -> List[MeasuredText]:
    """
    Parse all <text> elements from SVG and measure their rendering widths.

    Returns a list of MeasuredText ready for ConstraintValidator.
    """
    elements = parse_svg_text_elements(svg_content)
    results: List[MeasuredText] = []

    for el in elements:
        if use_pil:
            width, method = measure_text_width_pil(el.text, el.font_size, el.font_family)
        else:
            width, method = estimate_text_width(el.text, el.font_size), "estimate"

        container_w = el.container_width if el.container_width > 0 else 1120.0
        overflow = width / max(container_w, 1)

        results.append(MeasuredText(
            text=el.text, font_size=el.font_size,
            measured_width=width, container_width=container_w,
            overflow_ratio=overflow, element_id=el.element_id, method=method,
        ))

    return results


def _role_min_font_size(font_size: float) -> float:
    """Return the conservative lower bound for the inferred typography role."""
    if font_size >= 72:
        return 48.0
    if font_size >= 48:
        return 40.0
    if font_size >= 28:
        return 28.0
    if font_size >= 14:
        return 12.0
    return 8.0


def _fit_font_size(
    text: str,
    current_size: float,
    font_family: str,
    container_width: float,
    use_pil: bool = True,
) -> float:
    """Find the largest safe font size no larger than current_size."""
    lower = min(_role_min_font_size(current_size), current_size)
    upper = current_size

    def width_at(size: float) -> float:
        if use_pil:
            return measure_text_width_pil(text, size, font_family)[0]
        return estimate_text_width(text, size)

    if width_at(upper) <= container_width:
        return current_size
    if width_at(lower) > container_width:
        return lower

    for _ in range(12):
        mid = (lower + upper) / 2.0
        if width_at(mid) <= container_width:
            lower = mid
        else:
            upper = mid
    return lower


def optimize_svg_text_sizes(
    svg_content: str,
    use_pil: bool = True,
    overflow_threshold: float = 1.02,
) -> Tuple[str, int]:
    """
    Shrink overflowing text within typography-role lower bounds.

    This is intentionally conservative: it never increases font sizes and it
    only rewrites the font-size attribute of text elements whose measured width
    exceeds their inferred container.
    """
    changed_count = 0

    def replace_block(match: re.Match) -> str:
        nonlocal changed_count
        block = match.group(0)
        attrs_match = re.search(r'<text([^>]*)>', block, re.DOTALL)
        content_match = re.search(r'<text[^>]*>(.*?)</text>', block, re.DOTALL)
        if not attrs_match or not content_match:
            return block

        attrs_text = attrs_match.group(1)
        attrs = _parse_attrs(attrs_text)
        old_size = _float_attr(attrs, "font-size", 18.0)
        x = _float_attr(attrs, "x", 0.0)
        font_family = attrs.get("font-family", "Microsoft YaHei")
        text = _strip_svg_tags(content_match.group(1))
        if not text or old_size <= 0:
            return block

        y = _float_attr(attrs, "y", 0.0)
        container_width = _find_container_width(svg_content, x, y)
        measured = (
            measure_text_width_pil(text, old_size, font_family)[0]
            if use_pil else estimate_text_width(text, old_size)
        )
        if measured / max(container_width, 1.0) <= overflow_threshold:
            return block

        new_size = _fit_font_size(text, old_size, font_family, container_width, use_pil)
        if old_size - new_size < 0.75:
            return block

        new_size_text = str(int(round(new_size)))
        if "font-size" in attrs:
            new_block = re.sub(
                r'font-size="[^"]*"',
                f'font-size="{new_size_text}"',
                block,
                count=1,
            )
        else:
            new_block = block.replace("<text", f'<text font-size="{new_size_text}"', 1)
        changed_count += 1
        return new_block

    optimized = re.sub(r'<text\b[^>]*>.*?</text>', replace_block, svg_content, flags=re.DOTALL)
    return optimized, changed_count
