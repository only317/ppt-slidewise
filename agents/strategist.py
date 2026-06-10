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
When the user uploads a ZIP or provides a GitHub URL (repo at sources/repo/):

### Workflow
1. First, call `read_file("sources/repo/README.md")`
2. **If README exists**: use it as your primary guide. Identify project purpose, key modules, entry points, dependencies. Then read the files mentioned in README.
3. **If README is NOT FOUND**: DON'T PANIC. Execute these steps yourself:
   a. Call `list_dir("sources/repo")` to see the top-level structure
   b. Identify the project type from config files: package.json→Node, requirements.txt/pyproject.toml→Python, go.mod→Go, Cargo.toml→Rust, etc. Read the relevant config file.
   c. Find the main entry point: look for main.py, index.js/ts, app.py, src/ directory, etc. Call `list_dir` deeper into key directories.
   d. Read 5-10 of the most important source files (entry point + core logic modules).
   e. Generate PPT with: Cover→Overview→Architecture→Key Modules→Setup & Run

4. **If no files are found at all**: tell the user and ask for guidance.

### PPT Content for Repos
- Cover: project name (from dir name or config) + one-liner description
- Overview (L6): tech stack, file count, language, license
- Architecture (L3/L4): directory tree + each module's responsibility
- Key Modules (L3): 1 slide per major module (what it does, key APIs/classes/functions)
- Setup & Run (L3): install, configure, run — extracted from README or config files

**IMPORTANT — After reading the repo, your outline JSON MUST include detailed bullets:**
- Do NOT leave bullets empty just because the repo has many files.
- For architecture slides: list each module with a 1-line description as a bullet.
- For module slides: list the key functions/classes/files as bullets.
- For setup slides: list the install steps / config options as bullets.
- Copy specific file paths, function names, and descriptions from the actual repo files.
- If you cannot produce bullets for a content page, that page should not exist.

## Constraint System (READ FIRST)
Use `read_reference("constraints/guizang.py")` to load the full palette and layout system.

**Style A — 电子杂志 × 电子墨水** (ink/indigo/forest/kraft/dune):
  Hero pages (L1封面/L2章节/L7封底) → dark ink background + light text.
  Content pages (L3/L4/L5/L6) → warm paper background + dark ink text.
  Alternating hero/content rhythm creates magazine breathing effect.
  Best for: 叙事、观点、分享、个人风格表达

**Style B — 瑞士国际主义** (klein-blue/lemon/lime/safety-orange):
  ALL pages → unified warm off-white paper (#fafaf8) + near-black text.
  ONE saturated anchor color per deck. Grid-first, sharp corners, hairline rules.
  Extreme font-size contrast (≥8:1 H1:Body). No gradients/shadows/rounded corners.
  Best for: 事实、产品、分析、方法论

## Style Selection
- "杂志感" / "人文" / "Monocle" / 不指定 → Style A, 推荐 ink
- "瑞士风" / "Swiss" / "极简" / "数据" / "产品分析" → Style B, 推荐 klein-blue
- 科技/AI/组会 → Style A indigo or Style B klein-blue
- 水课 → Style A ink (默认)
- User mentions specific color → match to closest

Typography: H1(72-96) / H2(48-64) / H3(36-48) / Body(14-18) / Meta(10-12)

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

## CRITICAL — BULLET CONTENT REQUIREMENTS
- **Every non-hero page (L3/L4/L5/L6) MUST have 3-5 substantive bullet points.**
- Each bullet must be a complete sentence or meaningful phrase (15-40 Chinese chars)
  directly extracted or summarized from the source materials.
- Empty bullets (`"bullets": []`) will cause the Generator to fabricate content.
- For GitHub repos: extract bullets from README sections, key modules, architecture descriptions.
- For L1/L2/L7 (cover/section/back): bullets can be empty — these pages use large titles anyway.
- Bullets IS the primary content the Generator uses — if they are missing, the output will be WRONG.
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
    max_tool_rounds = 50

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
