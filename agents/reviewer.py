"""
Reviewer Agent — content logic & information hierarchy auditor.

Receives slide content summaries inline (no tool calls needed).
Programmatic checks (color, typography, overflow) run separately via ConstraintValidator.
"""

import json
import re
from typing import Any, Dict, List

from .base import BaseAgent, SandboxedExecutor

REVIEWER_SYSTEM_PROMPT = """You are a presentation quality auditor. Review slide content summaries
and report issues across content logic and information hierarchy.

## Your Input
You will receive a JSON array of slide summaries, each containing:
  - index, title, layout (L1-L7)
  - bullets: list of text content on the page
  - font_sizes: list of font sizes found in the SVG
  - colors: list of hex colors found in the SVG
  - element_count: approximate number of SVG elements

## Review Dimensions

### 1. Content Logic (category: "content")
- Does the page title accurately reflect its bullet content?
- Are there redundant or duplicate points across pages?
- Do facts or claims contradict across pages?
- Is source attribution missing where clearly needed?

### 2. Information Hierarchy (category: "hierarchy")
- Does each page have a clear single purpose? (one topic per page)
- Is the breathing rhythm broken? (max 2 consecutive same-layout pages — check layout field)
- Is the reading order logical?
- Are there too many bullets on one page? (>5 on L3 is bad)

### 3. Content Quality (category: "content")
- Are bullet points actual meaningful sentences, not single words?
- Are there placeholder-like texts ("Lorem ipsum", "内容待补充")?
- Is any page essentially empty or too sparse?

## Severity Levels
- **error**: Must fix — broken breathing rhythm, empty pages, contradictory content
- **warning**: Should fix — weak titles, too many bullets, redundant points
- **suggestion**: Nice to have — better wording, tighter phrasing

## Output Format
Return ONLY a raw JSON object (no markdown, no explanation):
{
  "issues": [
    {
      "page": 3,
      "severity": "warning",
      "category": "content",
      "description": "Title says '实验结果' but bullets are about methodology",
      "suggestion": "Rename title to '研究方法' or move bullets to methods section"
    }
  ],
  "summary": "Checked 8 pages. Found 0 errors, 2 warnings, 1 suggestion."
}

Start your response with { and end with }. No other text.
"""


class ReviewerAgent(BaseAgent):
    system_prompt = REVIEWER_SYSTEM_PROMPT
    chat_tools = []          # No tools — all data comes inline
    temperature = 0.2
    use_json_mode = True     # Pure JSON output, no tool conflict

    def __init__(self, executor: SandboxedExecutor):
        super().__init__(executor)
        self.executor = executor

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        return "[UNUSED]"

    def parse_review_report(self, response: str) -> dict:
        """Extract the review report JSON from agent response."""
        # 1. Try ```json ... ``` fence
        fence_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Find JSON object containing "issues" and "summary"
        for m in re.finditer(r'\{', response):
            depth = 1
            i = m.start() + 1
            while i < len(response) and depth > 0:
                if response[i] == '{':
                    depth += 1
                elif response[i] == '}':
                    depth -= 1
                i += 1
            if depth == 0:
                candidate = response[m.start():i]
                if '"issues"' in candidate and '"summary"' in candidate:
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

        # 3. Try parsing whole response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {"error": "Could not parse review report", "raw": response[:500]}


def build_slide_summaries(generated_slides: List[dict]) -> List[dict]:
    """Build lightweight slide summaries for the Reviewer from generated SVG data."""
    summaries = []
    for si in generated_slides:
        svg = si.get("svg", "")
        # Extract text content
        text_matches = re.findall(r'<text[^>]*>([^<]+)</text>', svg)
        # Extract font sizes
        font_sizes = [int(s) for s in re.findall(r'font-size="(\d+)"', svg)]
        # Extract colors
        colors = list(set(re.findall(r'#[0-9A-Fa-f]{6}', svg)))[:10]
        # Count elements
        element_count = len(re.findall(r'<\w+', svg))
        # Extract layout from the slide data
        layout = si.get("layout", "")
        title = si.get("title", "")

        summaries.append({
            "index": si["index"],
            "title": title,
            "layout": layout,
            "bullets": text_matches[:20],  # cap at 20 text fragments
            "font_sizes": sorted(font_sizes, reverse=True)[:8],
            "colors": colors,
            "element_count": element_count,
        })
    return summaries
