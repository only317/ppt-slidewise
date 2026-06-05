"""
Reviewer Agent — layout & typography quality auditor.

Reads all generated SVGs, produces a structured issue report across
four dimensions: style, layout, content, hierarchy.

Layer 1 text overflow detection is done here via heuristic estimation.
Layer 2 (PIL precise measurement) runs separately in the engine.
"""

import json
import re
from typing import Any, Dict, List

from .base import BaseAgent, SandboxedExecutor, make_tool

REVIEWER_SYSTEM_PROMPT = """You are a presentation design auditor — the quality gatekeeper
for Swiss International Style slides. Review SVG source code and report issues.

## Your Job
Read all generated SVG files from svg_output/ and inspect each one across four dimensions.
YOU MUST examine the raw SVG XML source code for each slide.

## Four Review Dimensions

### 1. Style Compliance (style)
- Are any colors outside the allowed palette?
- Is #FFFFFF or #000000 used anywhere?
- Is the anchor color used more than once per page?
- Are border-radius, box-shadow, or gradients used?
- Does H3/Body font size ratio satisfy ≥ 2.0?
- Does the cover (L1) and back cover (L7) use matching anchor colors?

### 2. Layout Quality (layout)
- Do any text elements overflow their containers? Estimate: CJK≈font_size×chars, Latin≈font_size×0.55×chars
- Does text density exceed 65% of the slide area?
- Are elements properly aligned to the 16-column grid?
- Do images maintain aspect ratio? (L4 layout)
- Are there any empty or orphaned elements?

### 3. Content Logic (content)
- Does the page title accurately reflect the content?
- Are there redundant or duplicate bullet points?
- Do facts/data contradict across pages?
- Is source attribution present where needed?

### 4. Information Hierarchy (hierarchy)
- Does each page have a clear primary focal point?
- Is the breathing rhythm broken? (max 2 consecutive same-layout pages)
- Is the reading order logical? (top→bottom, left→right)

## Severity Levels
- **error**: Must fix (blocks export). Overflow > 15%, forbidden elements, broken rhythm.
- **warning**: Should fix (user decides). Near overflow 5-15%, weak hierarchy.
- **suggestion**: Nice to have. Better wording, alternative layout idea.

## Available Tools
- `read_file(path)` — read an SVG file from the session workspace
- `list_dir(path)` — list files (e.g. svg_output/ to see all slides)
- `read_reference(path)` — read constraint definitions

## Output Format
Return ONLY a JSON object (no markdown, no explanation):

```json
{
  "issues": [
    {
      "page": 3,
      "severity": "error",
      "category": "layout",
      "element_id": "t3",
      "description": "Text 'Very long bullet point...' (est. 842px) overflows container (720px) by 16.9%",
      "suggestion": "Shorten bullet to under 50 characters or split into 2 bullets"
    }
  ],
  "summary": "Checked 8 pages. Found 2 errors, 3 warnings, 1 suggestion.",
  "text_overflow_details": [
    {"page": 3, "element_id": "t3", "estimated_width": 842, "container_width": 720}
  ],
  "breathing_rhythm_violations": []
}
```

## Workflow
1. Call `list_dir("svg_output")` to see available SVG files
2. Call `read_file` for EACH SVG file (every page must be reviewed)
3. Analyze each SVG across all four dimensions
4. Return the final JSON report
"""

REVIEWER_TOOLS = [
    make_tool("read_file", "Read an SVG file from the session workspace",
              {"path": {"type": "string", "description": "Path within session dir, e.g. svg_output/slide_03.svg"}},
              ["path"]),
    make_tool("list_dir", "List files in the session workspace",
              {"path": {"type": "string", "description": "Relative path within session dir"}},
              ["path"]),
    make_tool("read_reference", "Read a constraint definition file",
              {"path": {"type": "string", "description": "Path relative to project root"}},
              ["path"]),
]


class ReviewerAgent(BaseAgent):
    system_prompt = REVIEWER_SYSTEM_PROMPT
    chat_tools = REVIEWER_TOOLS
    temperature = 0.2  # lower temp for more consistent auditing
    use_json_mode = True

    def __init__(self, executor: SandboxedExecutor):
        super().__init__(executor)

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "read_file":
            return self.executor.read_file(args.get("path", ""))
        elif name == "list_dir":
            return "\n".join(self.executor.list_dir(args.get("path", ".")))
        elif name == "read_reference":
            return self.executor.read_reference(args.get("path", ""))
        return f"[UNKNOWN TOOL] {name}"

    def parse_review_report(self, response: str) -> dict:
        """Extract the review report JSON from agent response."""
        import re

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
