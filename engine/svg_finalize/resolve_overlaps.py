"""
Conservative SVG overlap resolver.

Only resolves obvious text-vs-text overlaps. Decorative overlaps are often
intentional in slide design, so they are reported by the validator but not
rewritten here.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

try:
    from text_measurer import estimate_text_width
except ImportError:  # pragma: no cover - package import path
    from engine.text_measurer import estimate_text_width


_ATTR_RE = re.compile(r'([:\w-]+)\s*=\s*"([^"]*)"')


@dataclass
class TextBox:
    index: int
    start: int
    end: int
    attrs: Dict[str, str]
    text: str
    x: float
    y: float
    width: float
    height: float
    font_size: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def top(self) -> float:
        return self.y - self.height * 0.8

    @property
    def bottom(self) -> float:
        return self.top + self.height


def _parse_attrs(attr_text: str) -> Dict[str, str]:
    return {m.group(1): m.group(2) for m in _ATTR_RE.finditer(attr_text)}


def _float_attr(attrs: Dict[str, str], name: str, default: float = 0.0) -> float:
    raw = attrs.get(name)
    if raw is None:
        return default
    match = re.match(r'\s*(-?\d+(?:\.\d+)?)', raw)
    return float(match.group(1)) if match else default


def _strip_tags(text: str) -> str:
    text = re.sub(r'<tspan[^>]*>', '', text)
    text = re.sub(r'</tspan>', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def _text_boxes(svg_content: str) -> List[TextBox]:
    boxes: List[TextBox] = []
    for idx, match in enumerate(re.finditer(r'<text\b([^>]*)>(.*?)</text>', svg_content, re.DOTALL)):
        attrs = _parse_attrs(match.group(1))
        text = _strip_tags(match.group(2))
        if not text:
            continue
        font_size = _float_attr(attrs, "font-size", 18.0)
        x = _float_attr(attrs, "x", 0.0)
        y = _float_attr(attrs, "y", 0.0)
        width = estimate_text_width(text, font_size)
        height = font_size * 1.25
        boxes.append(TextBox(
            index=idx,
            start=match.start(),
            end=match.end(),
            attrs=attrs,
            text=text,
            x=x,
            y=y,
            width=width,
            height=height,
            font_size=font_size,
        ))
    return boxes


def _overlap(a: TextBox, b: TextBox) -> Tuple[float, float, float]:
    x_overlap = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    y_overlap = max(0.0, min(a.bottom, b.bottom) - max(a.top, b.top))
    area = x_overlap * y_overlap
    min_area = max(min(a.width * a.height, b.width * b.height), 1.0)
    return x_overlap, y_overlap, area / min_area


def _infer_canvas_height(svg_content: str) -> float:
    match = re.search(r'viewBox="[^"]*?\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)"', svg_content)
    if match:
        return float(match.group(2))
    return 720.0


def _replace_text_y(svg_content: str, box: TextBox, new_y: float) -> str:
    block = svg_content[box.start:box.end]
    if ' y="' in block:
        new_block = re.sub(r'y="[^"]*"', f'y="{new_y:.1f}"', block, count=1)
    else:
        new_block = block.replace("<text", f'<text y="{new_y:.1f}"', 1)
    return svg_content[:box.start] + new_block + svg_content[box.end:]


def resolve_text_overlaps(svg_content: str, max_rounds: int = 3) -> Tuple[str, int]:
    """
    Push lower-priority overlapping text downward.

    Priority is approximated by larger font size first, then earlier z-order.
    Returns (updated_svg, fix_count).
    """
    updated = svg_content
    fixes = 0
    canvas_h = _infer_canvas_height(svg_content)

    for _ in range(max_rounds):
        boxes = _text_boxes(updated)
        applied = False

        for i, a in enumerate(boxes):
            for b in boxes[i + 1:]:
                _, y_overlap, ratio = _overlap(a, b)
                if ratio <= 0.05:
                    continue

                if a.font_size < b.font_size:
                    victim = a
                    blocker = b
                elif b.font_size < a.font_size:
                    victim = b
                    blocker = a
                else:
                    victim = b if b.index > a.index else a
                    blocker = a if victim is b else b

                shift = y_overlap + max(6.0, victim.font_size * 0.25)
                new_y = min(canvas_h - victim.height * 0.25, max(victim.y, blocker.bottom + victim.height * 0.8 + 4.0, victim.y + shift))
                if new_y <= victim.y + 0.5:
                    continue

                updated = _replace_text_y(updated, victim, new_y)
                fixes += 1
                applied = True
                break
            if applied:
                break

        if not applied:
            break

    return updated, fixes
