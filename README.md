# SlideWise

> Agent-driven PPT generation with Guizang Swiss International aesthetics.  
> 计算机图形学 Project 3 — 生成式AI实践

Type a topic or drop a PDF. SlideWise generates a professionally styled, truly editable `.pptx` deck — every text box and shape is a native PowerPoint object.

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure your DeepSeek API key
cp .env.example .env
# Edit .env → paste your DEEPSEEK_API_KEY

# 3. Build the frontend
cd frontend
npm install
npm run build
cd ..

# 4. Launch
python main.py
```

Open **http://localhost:8888** in your browser.

## What You Can Do

| Scenario | How |
|----------|-----|
| Group meeting | Drop a paper PDF → "组会用，靛蓝色" |
| Course assignment | Type a topic → "水课随便搞一下" |
| Study sharing | Paste an outline → "克莱因蓝，瑞士风格" |

## Style System (8 Palettes)

**Dark palettes** — dark background, light text:

| Palette | Anchor | Best for |
|---------|--------|----------|
| 靛蓝 Indigo | `#4a90d9` | Tech, AI, group meetings |
| 墨水 Ink | `#c9a96e` | General, formal |
| 森林 Forest | `#7a9a6e` | Nature, interdisciplinary |
| 沙丘 Dune | `#d4956a` | Creative, humanities |

**Light palettes** (Swiss B-style) — light background, dark text, single saturated accent:

| Palette | Anchor | Best for |
|---------|--------|----------|
| 克莱因蓝 Klein Blue | `#002FA7` | Academic, clean |
| 柠檬黄 Lemon | `#c8a200` | Youth, energetic |
| 柠绿 Lime | `#7a9900` | Ecology, health |
| 安全橙 Safety Orange | `#d45a2e` | News, sports |

## Project Structure

```
├── main.py               # FastAPI + WebSocket entry point
├── agents/
│   ├── base.py            # DeepSeek API client + tool-use loop
│   ├── strategist.py      # Content analysis + outline planning
│   ├── generator.py       # Per-slide SVG generation
│   └── reviewer.py        # 4-dimension quality audit
├── constraints/
│   ├── guizang.py         # Palette, typography, layout definitions
│   └── validator.py       # Programmatic constraint checker
├── engine/
│   ├── svg_to_pptx/       # SVG → DrawingML compiler (native shapes)
│   ├── svg_finalize/      # SVG post-processing pipeline
│   ├── source_to_md/      # PDF / DOCX / web → Markdown converters
│   └── text_measurer.py   # Pixel-level text overflow detection
├── protocols/
│   └── websocket.py       # 15 typed WebSocket message types
├── frontend/
│   └── src/components/    # React SPA (12 components)
└── templates/
    ├── icons/             # 640 SVG icons
    └── charts/            # 52 chart templates
```

## Requirements

- Python 3.10+
- Node.js 18+ (frontend build only)
- DeepSeek API key (set `DEEPSEEK_API_KEY` in `.env`)

## Architecture

```
User (browser chat + slide preview)
  │ WebSocket
  ▼
Strategist Agent → outline
  │
Generator Agent → per-slide SVG (streamed)
  │
Reviewer Agent → issue report
  │
User decides → fix / ignore
  │
SVG → DrawingML compiler → .pptx download
```

Three DeepSeek V4 Flash agents with role separation via System Prompts. A programmatic `ConstraintValidator` supplements the Reviewer for deterministic checks (color, typography ratios, breathing rhythm).

## Credits

Built on ideas from [PPT Master](https://github.com/hugohe3/ppt-master) (SVG→PPTX compilation) and [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) (Swiss International Style). Project 3 for CS Graphics Course, 2026 Spring.
