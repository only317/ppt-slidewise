"""
Programmatic Constraint Validator.

Runs deterministic checks against Guizang constraints on SVG output.
Used as a supplement to the Reviewer Agent — catches issues that can
be verified by code rather than LLM judgement.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

try:
    from engine.text_measurer import estimate_text_width
except ImportError:  # pragma: no cover - validator can be imported from engine scripts
    from text_measurer import estimate_text_width

from .guizang import (
    PALETTES,
    TYPOGRAPHY,
    LAYOUTS,
    TYPOGRAPHY_RATIO_CHECKS,
    FORBIDDEN_COLORS,
    MAX_ANCHOR_ELEMENTS_PER_PAGE,
    BREATHING_RHYTHM_MAX_CONSECUTIVE,
    MAX_TEXT_DENSITY,
)

# SVG features banned by ppt-master compiler
FORBIDDEN_ELEMENTS = {
    "foreignObject", "mask", "style", "textPath",
    "animate", "animateMotion", "animateTransform",
    "animateColor", "set", "script", "iframe",
}

FORBIDDEN_PATTERNS = [
    (r"rgba\s*\(", "rgba() — use fill-opacity/stroke-opacity instead"),
    (r"@font-face", "@font-face not allowed"),
    (r'<\?xml-stylesheet\b', "xml-stylesheet not allowed"),
    (r'<link[^>]*rel\s*=\s*["\']stylesheet["\']', "external CSS not allowed"),
    (r'@import\s+', "@import not allowed"),
    (r'<g[^>]*\sopacity\s*=', "group opacity — set on children instead"),
    (r'<image[^>]*\sopacity\s*=', "image opacity — use overlay instead"),
]

_ATTR_RE = re.compile(r'([:\w-]+)\s*=\s*"([^"]*)"')


@dataclass
class ValidationIssue:
    page_index: int
    severity: str       # "error" | "warning"
    category: str        # "style" | "layout" | "content" | "hierarchy" | "svg_compat"
    description: str
    element_id: str = ""
    suggested_fix: str = ""


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)
    pages_checked: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def all_clear(self) -> bool:
        return self.error_count == 0


class ConstraintValidator:
    """Validates SVG output against Guizang & ppt-master constraints."""

    def __init__(self, palette_name: str = "indigo"):
        self.palette = PALETTES.get(palette_name, PALETTES["indigo"])
        self._allowed_hex: Set[str] = {
            self.palette.background.lower(),
            self.palette.paper.lower(),
            self.palette.ink.lower(),
            self.palette.text_on_paper.lower(),
            self.palette.anchor.lower(),
            self.palette.text_secondary.lower(),
            self.palette.surface.lower(),
            self.palette.divider.lower(),
        }

    # --- Public API ---

    def validate_svg_content(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        """Run all checks on a single SVG string."""
        issues: List[ValidationIssue] = []
        issues += self._check_svg_compat(svg_text, page_index)
        issues += self._check_color_usage(svg_text, page_index)
        issues += self._check_typography(svg_text, page_index)
        issues += self._check_contrast(svg_text, page_index)
        issues += self._check_overlaps(svg_text, page_index)
        return issues

    def validate_breathing_rhythm(self, layout_sequence: List[str]) -> List[ValidationIssue]:
        """Check that no 3+ consecutive pages use the same layout."""
        issues: List[ValidationIssue] = []
        run_start = 0
        for i in range(1, len(layout_sequence) + 1):
            if i == len(layout_sequence) or layout_sequence[i] != layout_sequence[run_start]:
                run_len = i - run_start
                if run_len > BREATHING_RHYTHM_MAX_CONSECUTIVE:
                    issues.append(ValidationIssue(
                        page_index=run_start + 1,
                        severity="error",
                        category="hierarchy",
                        description=f"Pages {run_start+1}-{i} use same layout "
                                    f"'{layout_sequence[run_start]}' ({run_len} consecutive — max {BREATHING_RHYTHM_MAX_CONSECUTIVE})",
                        suggested_fix=f"Change at least one page to a different layout."
                    ))
                run_start = i
        return issues

    def validate_text_overflow(
        self, text_elements: List[Dict], page_index: int
    ) -> List[ValidationIssue]:
        """
        Check text overflow using pre-measured widths from TextMeasurer.

        Args:
            text_elements: List of {text, font_size, measured_width, container_width, element_id}
        """
        issues: List[ValidationIssue] = []
        for el in text_elements:
            ratio = el["measured_width"] / max(el["container_width"], 1)
            if ratio > 1.15:
                issues.append(ValidationIssue(
                    page_index=page_index,
                    severity="error",
                    category="layout",
                    description=f"Text overflow: '{el['text'][:40]}...' "
                                f"({el['measured_width']:.0f}px) exceeds container "
                                f"({el['container_width']:.0f}px) by {ratio-1:.0%}",
                    element_id=el.get("element_id", ""),
                    suggested_fix="Reduce text, split into 2 columns, or decrease font size."
                ))
            elif ratio > 1.05:
                issues.append(ValidationIssue(
                    page_index=page_index,
                    severity="warning",
                    category="layout",
                    description=f"Text near overflow: '{el['text'][:40]}...' "
                                f"({el['measured_width']:.0f}px) in container ({el['container_width']:.0f}px, {ratio-1:.0%})",
                    element_id=el.get("element_id", ""),
                    suggested_fix="Consider reducing text length slightly."
                ))
        return issues

    # --- Private checks ---

    def _check_svg_compat(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        svg_lower = svg_text.lower()

        for el in FORBIDDEN_ELEMENTS:
            if f"<{el}" in svg_lower or f"</{el}>" in svg_lower:
                issues.append(ValidationIssue(
                    page_index=page_index, severity="error",
                    category="svg_compat",
                    description=f"Forbidden SVG element <{el}> — not convertible to DrawingML",
                    suggested_fix=f"Replace <{el}> with supported SVG elements (rect, text, path, etc.)"
                ))

        for pattern, desc in FORBIDDEN_PATTERNS:
            if re.search(pattern, svg_text, re.IGNORECASE):
                issues.append(ValidationIssue(
                    page_index=page_index, severity="error",
                    category="svg_compat", description=desc,
                ))

        return issues

    def _check_color_usage(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        hex_colors = set(re.findall(r'#[0-9A-Fa-f]{6}', svg_text))

        for c in hex_colors:
            if c.lower() in FORBIDDEN_COLORS:
                issues.append(ValidationIssue(
                    page_index=page_index, severity="error",
                    category="style",
                    description=f"Forbidden color {c} — pure black/white not allowed in Guizang",
                    suggested_fix=f"Use {self.palette.paper} for background, {self.palette.ink} for text"
                ))

        anchor_count = sum(
            1 for c in hex_colors if c.lower() == self.palette.anchor.lower()
        )
        # Count anchor-colored elements (rough heuristic)
        anchor_refs = len(re.findall(
            re.escape(self.palette.anchor), svg_text, re.IGNORECASE
        ))
        if anchor_refs > MAX_ANCHOR_ELEMENTS_PER_PAGE + 3:  # +3 tolerance for small elements
            issues.append(ValidationIssue(
                page_index=page_index, severity="warning",
                category="style",
                description=f"Anchor color used ~{anchor_refs} times (max {MAX_ANCHOR_ELEMENTS_PER_PAGE} recommended)",
                suggested_fix="Limit anchor color to 1-2 highlight elements per page"
            ))

        return issues

    def _check_typography(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        font_sizes = [int(s) for s in re.findall(r'font-size="(\d+)"', svg_text)]
        if not font_sizes:
            return issues

        h1_candidates = [s for s in font_sizes if s >= 72]
        h3_candidates = [s for s in font_sizes if 36 <= s <= 48]
        body_sizes = [s for s in font_sizes if 14 <= s <= 18]

        # Check H3 / Body ratio
        if h3_candidates and body_sizes:
            min_h3 = min(h3_candidates)
            max_body = max(body_sizes)
            ratio = min_h3 / max_body if max_body > 0 else 999
            min_ratio = TYPOGRAPHY_RATIO_CHECKS.get(("H3", "Body"), 2.0)
            if ratio < min_ratio:
                issues.append(ValidationIssue(
                    page_index=page_index, severity="warning",
                    category="style",
                    description=f"Typography ratio H3({min_h3}px)/Body({max_body}px) = {ratio:.1f} (min {min_ratio})",
                    suggested_fix=f"Increase H3 to ≥{int(max_body * min_ratio)}px or reduce Body"
                ))

        return issues

    def _check_contrast(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        rects = _parse_rects(svg_text)
        default_bg = _first_background_fill(svg_text) or self.palette.paper

        for text_el in _parse_text_elements(svg_text):
            fill = text_el.get("fill") or self.palette.ink
            bg = _background_at(text_el["x"], text_el["y"], rects, default_bg)
            ratio = _contrast_ratio(fill, bg)
            if ratio is None:
                continue
            threshold = 3.0 if text_el["font_size"] >= 24 else 4.5
            if ratio < threshold:
                issues.append(ValidationIssue(
                    page_index=page_index,
                    severity="error" if ratio < threshold * 0.7 else "warning",
                    category="accessibility",
                    description=(
                        f"Text contrast {ratio:.2f}:1 below WCAG AA "
                        f"threshold {threshold:.1f}:1 for '{text_el['text'][:30]}...'"
                    ),
                    element_id=text_el.get("id", ""),
                    suggested_fix=(
                        f"Use a higher-contrast text color such as {self.palette.ink} "
                        f"or {self.palette.text_on_paper}."
                    ),
                ))

        return issues

    def _check_overlaps(self, svg_text: str, page_index: int) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        texts = _text_boxes(svg_text)

        for i, a in enumerate(texts):
            for b in texts[i + 1:]:
                ratio = _overlap_ratio(a, b)
                if ratio <= 0.05:
                    continue
                issues.append(ValidationIssue(
                    page_index=page_index,
                    severity="warning" if ratio < 0.2 else "error",
                    category="layout",
                    description=(
                        f"Text elements overlap by {ratio:.0%}: "
                        f"'{a['text'][:18]}...' vs '{b['text'][:18]}...'"
                    ),
                    element_id=a.get("id") or b.get("id", ""),
                    suggested_fix="Move one text element or reduce font size to avoid overlap.",
                ))

        return issues


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


def _parse_text_elements(svg_text: str) -> List[Dict]:
    elements: List[Dict] = []
    for match in re.finditer(r'<text\b([^>]*)>(.*?)</text>', svg_text, re.DOTALL | re.IGNORECASE):
        attrs = _parse_attrs(match.group(1))
        content = _strip_tags(match.group(2))
        if not content:
            continue
        elements.append({
            "id": attrs.get("id", ""),
            "text": content,
            "x": _float_attr(attrs, "x", 0.0),
            "y": _float_attr(attrs, "y", 0.0),
            "font_size": _float_attr(attrs, "font-size", 18.0),
            "fill": attrs.get("fill", ""),
        })
    return elements


def _parse_rects(svg_text: str) -> List[Dict]:
    rects: List[Dict] = []
    for order, match in enumerate(re.finditer(r'<rect\b([^>]*)>', svg_text, re.IGNORECASE)):
        attrs = _parse_attrs(match.group(1))
        fill = attrs.get("fill", "")
        if not fill.startswith("#"):
            continue
        rects.append({
            "order": order,
            "x": _float_attr(attrs, "x", 0.0),
            "y": _float_attr(attrs, "y", 0.0),
            "w": _float_attr(attrs, "width", 0.0),
            "h": _float_attr(attrs, "height", 0.0),
            "fill": fill,
        })
    return rects


def _first_background_fill(svg_text: str) -> Optional[str]:
    match = re.search(r'<rect\b([^>]*)>', svg_text, re.IGNORECASE)
    if not match:
        return None
    attrs = _parse_attrs(match.group(1))
    fill = attrs.get("fill", "")
    return fill if fill.startswith("#") else None


def _background_at(x: float, y: float, rects: List[Dict], default_bg: str) -> str:
    bg = default_bg
    for rect in rects:
        if rect["w"] <= 0 or rect["h"] <= 0:
            continue
        if rect["x"] <= x <= rect["x"] + rect["w"] and rect["y"] <= y <= rect["y"] + rect["h"]:
            bg = rect["fill"]
    return bg


def _hex_to_rgb(color: str) -> Optional[Tuple[int, int, int]]:
    match = re.fullmatch(r'#([0-9a-fA-F]{6})', color.strip())
    if not match:
        return None
    raw = match.group(1)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _linear_channel(value: int) -> float:
    c = value / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> Optional[float]:
    rgb = _hex_to_rgb(color)
    if rgb is None:
        return None
    r, g, b = (_linear_channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str) -> Optional[float]:
    l1 = _relative_luminance(fg)
    l2 = _relative_luminance(bg)
    if l1 is None or l2 is None:
        return None
    light, dark = max(l1, l2), min(l1, l2)
    return (light + 0.05) / (dark + 0.05)


def _text_boxes(svg_text: str) -> List[Dict]:
    boxes: List[Dict] = []
    for el in _parse_text_elements(svg_text):
        width = estimate_text_width(el["text"], el["font_size"])
        height = el["font_size"] * 1.25
        top = el["y"] - height * 0.8
        boxes.append({
            **el,
            "left": el["x"],
            "right": el["x"] + width,
            "top": top,
            "bottom": top + height,
            "area": max(width * height, 1.0),
        })
    return boxes


def _overlap_ratio(a: Dict, b: Dict) -> float:
    x_overlap = max(0.0, min(a["right"], b["right"]) - max(a["left"], b["left"]))
    y_overlap = max(0.0, min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]))
    return (x_overlap * y_overlap) / max(min(a["area"], b["area"]), 1.0)
