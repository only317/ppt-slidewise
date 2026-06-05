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
        x = float(re.search(r'x="([\d.]+)"', attrs).group(1)) if re.search(r'x="([\d.]+)"', attrs) else 0.0
        y = float(re.search(r'y="([\d.]+)"', attrs).group(1)) if re.search(r'y="([\d.]+)"', attrs) else 0.0
        font_size = float(re.search(r'font-size="([\d.]+)"', attrs).group(1)) if re.search(r'font-size="([\d.]+)"', attrs) else 18.0
        font_family = re.search(r'font-family="([^"]*)"', attrs).group(1) if re.search(r'font-family="([^"]*)"', attrs) else "Microsoft YaHei"
        el_id = re.search(r'id="([^"]*)"', attrs).group(1) if re.search(r'id="([^"]*)"', attrs) else ""

        # Extract text content
        content_match = re.search(r'<text[^>]*>(.*?)</text>', block_text, re.DOTALL)
        if not content_match:
            continue
        content = content_match.group(1)

        # Strip nested tags (<tspan>)
        content = re.sub(r'<tspan[^>]*>', '', content)
        content = re.sub(r'</tspan>', '', content)
        content = content.strip()
        if not content:
            continue

        # Estimate container width from parent rect
        container_w = _find_container_width(svg_content, x)

        elements.append(TextElement(
            text=content, font_size=font_size, font_family=font_family,
            x=x, y=y, element_id=el_id, container_width=container_w,
        ))

    return elements


def _find_container_width(svg_content: str, text_x: float) -> float:
    """
    Heuristic: find the nearest <rect> or layout zone that contains text_x.
    Defaults to 1280 - margins if not found.
    """
    rects = re.finditer(
        r'<rect[^>]*x="([\d.]+)"[^>]*width="([\d.]+)"',
        svg_content
    )
    best_w = 1120.0  # default safe width (1280 - 80*2 margins)
    for r in rects:
        rx = float(r.group(1))
        rw = float(r.group(2))
        if rx <= text_x <= rx + rw:
            return rw
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
