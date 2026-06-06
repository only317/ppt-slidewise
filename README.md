# SlideWise

> Agent-driven PPT generation with Guizang aesthetics. Chat with AI → get a truly editable `.pptx`.  
> 计算机图形学 Project 3 — 生成式AI实践

Drop a PDF, paste a GitHub link, upload a ZIP, or just type a topic. SlideWise generates a professionally styled `.pptx` — every text box and shape is a native PowerPoint object.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API key
cp .env.example .env
# Edit .env → paste your DEEPSEEK_API_KEY

# 3. Build frontend
cd frontend && npm install && npm run build && cd ..

# 4. Launch
python main.py
```

Open **http://localhost:8888**.

## Features

- **Chat-driven**: natural language interface — just describe what you want
- **Multi-input**: topic text, PDF papers, Markdown outlines, GitHub repos, ZIP projects
- **Dual-agent quality loop**: Generator → Reviewer → fix cycle
- **SVG → DrawingML compiler**: editable `.pptx` output (not flat images)
- **Session persistence**: refresh-safe, resume previous sessions
- **Cancel generation**: stop mid-generation if you change your mind

## Style System

Copied from [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill) by 歸藏.

### Style A — 电子杂志 × 电子墨水

Hero pages (dark ink bg) alternate with content pages (warm paper bg) for magazine breathing rhythm.

| Theme | Hero BG | Content BG | Anchor |
|-------|---------|------------|--------|
| 墨水经典 Ink | `#0a0a0b` | `#f1efea` | `#c9a96e` |
| 靛蓝瓷 Indigo | `#0a1f3d` | `#f1f3f5` | `#4a90d9` |
| 森林墨 Forest | `#1a2e1f` | `#f5f1e8` | `#7a9a6e` |
| 牛皮纸 Kraft | `#2a1e13` | `#eedfc7` | `#b8753e` |
| 沙丘 Dune | `#1f1a14` | `#f0e6d2` | `#d4956a` |

### Style B — 瑞士国际主义

Unified warm off-white background + single saturated accent. Grid-first, sharp corners, hairline rules.

| Theme | BG | Text | Accent |
|-------|-----|------|--------|
| 克莱因蓝 IKB | `#fafaf8` | `#0a0a0a` | `#002FA7` |
| 柠檬黄 Lemon | `#fafaf8` | `#0a0a0a` | `#FFD500` |
| 柠绿 Lime | `#fafaf8` | `#0a0a0a` | `#C5E803` |
| 安全橙 Safety Orange | `#fafaf8` | `#0a0a0a` | `#FF6B35` |

## Architecture

```
Browser (React SPA) ←WebSocket→ FastAPI Backend
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
          Strategist       Generator        Reviewer
          (outline)        (per-page SVG)   (quality audit)
                                │
                                ▼
                      SVG → DrawingML → .pptx
```

Three DeepSeek V4 Flash agents with role separation via System Prompts. Programmatic `ConstraintValidator` and PIL-based text measurement supplement the Reviewer.

## Project Structure

```
├── main.py               # FastAPI + WebSocket server
├── agents/               # 3 agents: strategist, generator, reviewer
├── constraints/          # Guizang palettes + layout templates + validator
├── engine/
│   ├── svg_to_pptx/      # SVG → native PowerPoint DrawingML
│   ├── svg_finalize/     # SVG post-processing
│   ├── source_to_md/     # PDF / DOCX / web converters
│   └── text_measurer.py  # PIL pixel-level overflow detection
├── protocols/            # Typed WebSocket messages (Pydantic)
├── frontend/             # React SPA (Vite + TypeScript)
├── templates/            # 640 SVG icons + 52 chart templates
└── sessions/             # Session state (auto-cleaned)
```

## Credits

- PPT generation: [PPT Master](https://github.com/hugohe3/ppt-master)
- Design system: [Guizang PPT Skill](https://github.com/op7418/guizang-ppt-skill)
- LLM: DeepSeek V4 Flash
