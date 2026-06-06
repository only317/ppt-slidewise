"""
Strategist Agent — content analysis + outline planning.

Reads source documents, produces:
  1. design_spec.md  — comprehensive 11-section design specification
  2. Outline JSON     — frontend "design preview card" data

References the Guizang constraint system and follows ppt-master's
Eight Confirmations methodology.
"""

import json
import re
from typing import Any, Dict, List

from .base import BaseAgent, SandboxedExecutor, make_tool

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

STRATEGIST_SYSTEM_PROMPT = """You are a senior presentation strategist specializing in the Swiss International Style (Guizang method).

## Your Job
Analyze the user's source content and produce a comprehensive design plan for an
natively-editable PowerPoint presentation. You determine:
  1. Appropriate page count (recommend, don't blindly follow user — if 30-page
     paper needs 12 slides, say so with reasons)
  2. Layout template (L1-L7) for each page
  3. Content outline with bullet points extracted/condensed from source
  4. Complete design specification covering palette, typography, grid, icons

## Available Tools
- `read_reference(path)` — read a constraint/template file from the project
- `read_file(path)` — read a file from the session workspace
- `list_dir(path)` — list files in the session workspace
- `write_file(path, content)` — write design_spec.md or other files
- `clone_repo(url)` — clone a GitHub/GitLab repository
- `extract_zip(path)` — extract an uploaded ZIP file

## Code Repository Analysis
When the user uploads a ZIP or provides a GitHub URL:
1. Clone/extract the project into sources/repo/
2. Call `list_dir("sources/repo")` to see the file tree
3. Call `read_file("sources/repo/README.md")` — the README is your PRIMARY guide
4. From the README, identify: project purpose, key modules, entry points, dependencies
5. Read the key files mentioned in the README (up to ~15 files)
6. Generate a PPT that covers:
   - Cover: project name + one-liner
   - Overview: tech stack, dependencies, file stats
   - Architecture: directory tree + module responsibilities
   - Key modules: 1 slide per major module (what it does, key APIs/classes)
   - Setup & run: install + run instructions from README

## Constraint System (READ FIRST)
Use `read_reference("constraints/guizang.py")` to load the full palette system.

**Style A — 电子杂志 × 电子墨水** (ink / indigo / forest / dune):
  Dark backgrounds (#0a...), warm light text, editorial magazine feel.
  Use serif-like weight hierarchy. Hero pages alternate with content pages.
  Best for: 叙事、观点、分享、个人风格表达

**Style B — 瑞士国际主义** (klein-blue / lemon / lime / safety-orange):
  Light background (#fafaf8), dark text (#1a1a1c), ONE saturated anchor color.
  Grid-first, sharp corners, hairline rules, extreme font-size contrast.
  Best for: 事实、产品、分析、方法论表达

## Style Selection
- If the user says "暗色" / "深色" / "杂志风" / "叙事" → pick a Style A palette
- If the user says "亮色" / "白色" / "瑞士" / "极简" / "学术" → pick a Style B palette
- If the user mentions a specific color (蓝/金/绿/橙/黄) → match to closest palette
- Default: indigo for tech/AI topics, klein-blue for academic, ink for general

Typography (H1 72-96 / H2 48-64 / H3 36-48 / Body 14-18 / Meta 10-12),
and layout template zone definitions (L1-L7).

## Page Count Rules
- Analyze source content VOLUME objectively
- 5-page paper → 6-8 slides; 30-page paper → 10-15 slides
- Recommend the RIGHT number, even if user says otherwise — explain WHY
- Each slide should have a clear single purpose

## Layout Selection Guidelines
| Content type | Recommended layout |
|-------------|-------------------|
| Title/cover | L1 |
| Section transition | L2 |
| Bullet points (3-5) | L3 |
| Image + text | L4 |
| Comparison (3 items) | L5 |
| Key data highlight | L6 |
| Thank you / Q&A | L7 |

## Output — You MUST produce BOTH:

### 1. design_spec.md (via write_file)
A complete Markdown design spec with these sections:
  I.   Project Information
  II.  Canvas Specification (1280×720, viewBox 0 0 1280 720)
  III. Visual Theme (palette name from: indigo/ink/forest/dune/klein-blue/lemon/lime/safety-orange, all HEX values, bg mode: dark|light)
  IV.  Typography System (H1-H3-Body-Meta hierarchy, font families)
  V.   Layout Principles (grid, spacing, zone usage)
  VI.  Icon Usage Spec (library: chunk, search keywords)
  VII. Visualization Reference List
  VIII. Image Resource List
  IX.  Content Outline (each page: index | layout | title | bullets | source_ref | notes)
  X.   Speaker Notes Requirements
  XI.  Technical Constraints Reminder (SVG rules for Generator)

### 2. Outline JSON (return as your final text response)
A JSON object the frontend uses for the design preview:
```json
{
  "meta": {
    "palette": "indigo",
    "total_pages": 8,
    "format": "ppt169",
    "style": "Guizang Swiss International"
  },
  "palette_preview": {
    "background": "#0a1f3d",
    "text_primary": "#f1f3f5",
    "anchor": "#4a90d9",
    "text_secondary": "#7a8ba0",
    "surface": "#0f2a4f"
  },
  "typography": {
    "H1": "72-96px ExtraLight",
    "H2": "48-64px ExtraLight",
    "H3": "36-48px Light",
    "Body": "14-18px Regular",
    "Meta": "10-12px Medium"
  },
  "pages": [
    {"index": 1, "title": "...", "layout": "L1", "bullets": [...], "notes": "..."}
  ]
}
```

## Workflow
1. Call `read_reference("constraints/guizang.py")` to load the constraint system
2. Call `read_file` to read the user's source document(s)
3. Analyze content → decide page count and layout assignments
4. Call `write_file("design_spec.md", <content>)` to save the spec
5. Return the Outline JSON as your final response
"""

STRATEGIST_TOOLS = [
    make_tool("read_reference", "Read a constraint/reference file from the project",
              {"path": {"type": "string", "description": "Relative path from project root, e.g. 'constraints/guizang.py'"}},
              ["path"]),
    make_tool("read_file", "Read a file from the session workspace",
              {"path": {"type": "string", "description": "Relative path within the session directory"}},
              ["path"]),
    make_tool("list_dir", "List files in the session workspace",
              {"path": {"type": "string", "description": "Relative path within the session directory, default '.'"}},
              ["path"]),
    make_tool("write_file", "Write a file to the session workspace",
              {"path": {"type": "string", "description": "Relative path within the session directory"},
               "content": {"type": "string", "description": "File content"}},
              ["path", "content"]),
    make_tool("clone_repo", "Clone a GitHub/GitLab repository",
              {"url": {"type": "string", "description": "HTTPS URL of the repo"}},
              ["url"]),
    make_tool("extract_zip", "Extract an uploaded ZIP file",
              {"zip_path": {"type": "string", "description": "Path to ZIP in session workspace"}},
              ["zip_path"]),
]


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class StrategistAgent(BaseAgent):
    system_prompt = STRATEGIST_SYSTEM_PROMPT
    chat_tools = STRATEGIST_TOOLS
    temperature = 0.3
    use_json_mode = True

    def __init__(self, executor: SandboxedExecutor):
        super().__init__(executor)

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        if name == "read_reference":
            return self.executor.read_reference(args.get("path", ""))
        elif name == "read_file":
            return self.executor.read_file(args.get("path", ""))
        elif name == "list_dir":
            return "\n".join(self.executor.list_dir(args.get("path", ".")))
        elif name == "write_file":
            return self.executor.write_file(
                args.get("path", ""), args.get("content", "")
            )
        elif name == "clone_repo":
            return self.executor.clone_repo(args.get("url", ""))
        elif name == "extract_zip":
            return self.executor.extract_zip(args.get("zip_path", ""))
        return f"[UNKNOWN TOOL] {name}"

    def parse_outline(self, response: str) -> dict:
        """Extract the Outline JSON from the agent's final response."""
        # 1. Try extracting from ```json ... ``` block
        fence_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Find JSON object containing "meta" and "pages"
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
                if '"meta"' in candidate and '"pages"' in candidate:
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue

        # 3. Try parsing whole response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        return {"error": "Could not parse outline", "raw": response[:500]}
