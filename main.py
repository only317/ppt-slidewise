"""
SlideWise — FastAPI Application Entry Point.

Orchestrates the 3-Agent pipeline via WebSocket:
  Strategist → Generator ⇆ Reviewer → Export
"""

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import sys
import traceback
from pathlib import Path
from typing import List, Optional

# Load .env file
_ENV_PATH = Path(__file__).resolve().parent / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _, _val = _line.partition("=")
            os.environ.setdefault(_key.strip(), _val.strip())
    print(f"[slidewise] Loaded .env from {_ENV_PATH}")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from sessions.manager import SessionManager
from agents.base import SandboxedExecutor
from agents.strategist import StrategistAgent
from agents.generator import GeneratorAgent, extract_svg_from_response
from agents.reviewer import ReviewerAgent, build_slide_summaries
from constraints.validator import ConstraintValidator
from protocols.websocket import (
    MessageType, WSProtocol,
    OutlineMessage, OutlinePayload, OutlinePage,
    SlideGeneratedMessage, SlideGeneratedPayload,
    ReviewReportMessage, ReviewReportPayload, ReviewIssue,
    SlideFixedMessage, SlideFixedPayload,
    DoneMessage, DonePayload,
    ErrorMessage, ErrorPayload,
    UserMessageMessage,
    ConfirmOutlineMessage,
    FixDecisionsMessage,
    AgentThinkingMessage, AgentThinkingPayload,
    AgentMessageMessage, AgentMessagePayload,
    FixBatchDoneMessage, FixBatchDonePayload,
    ConfirmPageFixMessage,
    UndoFixMessage,
)
from engine.text_measurer import measure_svg_text

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("slidewise")

app = FastAPI(title="SlideWise", version="0.1.0")
session_mgr = SessionManager.get_instance()

# ---------------------------------------------------------------------------
# Agent message helpers
# ---------------------------------------------------------------------------

async def send_agent_thinking(ws, agent: str, text: str = "", tool_name: str = "", tool_args: str = ""):
    """Send an agent thinking/tool-call update to the frontend."""
    try:
        await ws.send_json(AgentThinkingMessage(
            data=AgentThinkingPayload(agent=agent, text=text, tool_name=tool_name, tool_args=tool_args)
        ).model_dump())
    except Exception:
        pass

async def send_agent_message(ws, agent: str, text: str):
    """Send an agent natural-language message to the frontend."""
    try:
        await ws.send_json(AgentMessageMessage(
            data=AgentMessagePayload(agent=agent, text=text)
        ).model_dump())
    except Exception:
        pass


# Serve frontend
FRONTEND_DIR = PROJECT_ROOT / "frontend"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# Serve built React frontend (production) or raw HTML (development)
FRONTEND_BUILD = PROJECT_ROOT / "frontend" / "dist"
FRONTEND_DEV = PROJECT_ROOT / "frontend" / "index.html"


@app.get("/")
async def index():
    # Production: serve React build
    index_html = FRONTEND_BUILD / "index.html"
    if index_html.exists():
        return HTMLResponse(index_html.read_text(encoding="utf-8"))
    # Development: serve raw HTML
    if FRONTEND_DEV.exists():
        return HTMLResponse(FRONTEND_DEV.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>SlideWise</h1><p>Frontend not found. Run: cd frontend && npm run build</p>")


@app.get("/assets/{path:path}")
async def static_assets(path: str):
    """Serve Vite-built static assets."""
    asset_path = FRONTEND_BUILD / "assets" / path
    if not asset_path.exists():
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Not found", status_code=404)
    # Guess content type
    if path.endswith(".css"):
        from fastapi.responses import Response
        return Response(content=asset_path.read_bytes(), media_type="text/css")
    elif path.endswith(".js"):
        from fastapi.responses import Response
        return Response(content=asset_path.read_bytes(), media_type="application/javascript")
    return FileResponse(asset_path)


@app.get("/download/{session_id}")
async def download(session_id: str):
    """Serve the generated PPTX file for download."""
    session_dir = session_mgr.get_work_dir(session_id)
    exports = session_dir / "exports"
    pptx_files = sorted(exports.glob("*.pptx"), key=os.path.getmtime, reverse=True)
    if not pptx_files:
        return {"error": "No PPTX found"}
    return FileResponse(
        pptx_files[0],
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=pptx_files[0].name,
    )


# ---------------------------------------------------------------------------
# WebSocket handler
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()

    # Create new session if requested
    if session_id == "new":
        session_id = session_mgr.create()
        logger.info(f"New session created: {session_id}")
        # Notify the client of the real session ID
        await ws.send_json({"type": "state_sync", "data": {"session_id": session_id, "phase": "idle"}})
    else:
        logger.info(f"WebSocket connected: {session_id}")

    # Validate session
    try:
        work_dir = session_mgr.get_work_dir(session_id)
    except KeyError:
        await ws.send_json({"type": "error", "data": {"message": "Session not found", "recoverable": False}})
        await ws.close()
        return

    executor = SandboxedExecutor(work_dir)

    try:
        while True:
            raw = await ws.receive_json()
            msg_type = raw.get("type", "")

            if msg_type == MessageType.USER_MESSAGE:
                # Route based on current phase
                state = session_mgr.get_state(session_id)
                current_phase = state.get("phase", "idle") if state else "idle"
                if current_phase == "reviewing":
                    await handle_review_feedback(ws, raw, executor, session_id)
                else:
                    await handle_user_message(ws, raw, executor, session_id)

            elif msg_type == MessageType.CONFIRM_OUTLINE:
                await handle_confirm_outline(ws, raw, executor, session_id)

            elif msg_type == MessageType.FIX_DECISIONS:
                await handle_fix_decisions(ws, raw, executor, session_id)

            elif msg_type == MessageType.DOWNLOAD:
                await handle_download(ws, executor, session_id)

            elif msg_type == MessageType.LIST_SESSIONS:
                sessions = session_mgr.list_sessions()
                await ws.send_json({"type": "session_list", "data": sessions})

            elif msg_type == MessageType.RESUME_SESSION:
                await _handle_resume(ws, executor, session_id)

            elif msg_type == MessageType.CANCEL:
                session_mgr.cancel(session_id)
                logger.info(f"Session {session_id} cancelled by user")

            elif msg_type == "confirm_page_fix":
                await handle_confirm_page_fix(ws, raw, executor, session_id)

            elif msg_type == "undo_fix":
                await handle_undo_fix(ws, executor, session_id)

            else:
                await ws.send_json({
                    "type": "error",
                    "data": {"message": f"Unknown message type: {msg_type}", "phase": "", "recoverable": True}
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {traceback.format_exc()}")
        try:
            await ws.send_json({
                "type": "error",
                "data": {"message": str(e), "phase": "", "recoverable": False}
            })
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Session resume
# ---------------------------------------------------------------------------

async def _handle_resume(ws: WebSocket, executor: SandboxedExecutor, session_id: str):
    """Restore session state after page reload."""
    state = session_mgr.get_state(session_id)
    phase = state.get("phase", "idle") if state else "idle"
    state_data: dict = {"session_id": session_id, "phase": phase}

    # Restore outline if available
    try:
        outline_raw = executor.read_file("outline_confirmed.json")
        outline = json.loads(outline_raw)
        pages = [
            OutlinePage(
                index=p.get("index", i + 1),
                title=p.get("title", ""),
                layout=p.get("layout", "L3"),
                bullets=p.get("bullets", []),
                notes=p.get("notes", ""),
            )
            for i, p in enumerate(outline.get("pages", []))
        ]
        state_data["outline"] = OutlinePayload(
            pages=pages,
            design_spec=outline.get("meta", {}),
            meta=outline.get("meta", {}),
        ).model_dump()
    except Exception:
        pass

    # Restore existing SVGs
    slides_dir = executor._safe_path("svg_output")
    if slides_dir.exists():
        slides = {}
        for svg_file in sorted(slides_dir.glob("slide_*.svg")):
            try:
                idx = int(svg_file.stem.split("_")[1])
                slides[str(idx)] = svg_file.read_text(encoding="utf-8")
            except (ValueError, IndexError):
                pass
        if slides:
            state_data["slides"] = slides

    await ws.send_json({"type": "state_sync", "data": state_data})
    logger.info(f"Session {session_id} resumed at phase '{phase}'")

# ---------------------------------------------------------------------------
# Pipeline handlers
# ---------------------------------------------------------------------------

async def handle_user_message(ws: WebSocket, raw: dict, executor: SandboxedExecutor, session_id: str):
    """Phase 1: User sends message → Strategist analyzes → return outline."""
    msg = UserMessageMessage(**raw)
    text = msg.data.text
    files = msg.data.files

    # Save uploaded files
    for f in files:
        name = f.get("name", "upload")
        content = base64.b64decode(f.get("content_base64", ""))
        file_path = executor._safe_path(f"sources/{name}")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(content)
        logger.info(f"Saved uploaded file: {name}")

    # Convert non-Markdown files
    await _convert_sources(executor)

    session_mgr.update_phase(session_id, "planning")

    # Detect GitHub URL in user text → clone before running Strategist
    github_url = _detect_github_url(text)
    if github_url:
        try:
            clone_result = await asyncio.to_thread(executor.clone_repo, github_url)
            logger.info(f"Repo cloned: {clone_result[:200]}")
        except Exception as e:
            logger.warning(f"Clone failed ({github_url}): {e}")

    # Run Strategist Agent
    repo_hint = ""
    if github_url:
        repo_hint = f"\nA GitHub repository has been cloned to sources/repo/ — analyze it thoroughly."
    if (executor._safe_path("sources/repo") / "README.md").exists():
        repo_hint += "\nA code repository is available at sources/repo/ — read its README and key files."

    agent = StrategistAgent(executor)

    await send_agent_thinking(ws, "strategist", "正在分析您的需求...")
    if github_url:
        await send_agent_thinking(ws, "strategist", f"正在读取代码仓库 {github_url}")
    if files:
        file_names = [f.get("name", "?") for f in files]
        await send_agent_thinking(ws, "strategist", f"正在处理文件: {', '.join(file_names)}")

    try:
        response = await asyncio.to_thread(
            agent.run,
            f"Analyze the source documents and create a design_spec.md + Outline JSON.\n\n"
            f"User request: {text}{repo_hint}",
        )
    except Exception as e:
        logger.error(f"Strategist error: {e}")
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(message=str(e), phase="planning", recoverable=True)
        ).model_dump())
        return

    # Parse outline
    print(f"[STRATEGIST] raw ({len(response)} chars): {response[:300]}", flush=True)
    outline_data = agent.parse_outline(response)
    print(f"[STRATEGIST] parsed: {'OK' if 'error' not in outline_data else outline_data}", flush=True)

    if "error" in outline_data:
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(message=outline_data.get("error", "Parse failed"), phase="planning")
        ).model_dump())
        return

    # Save outline for subsequent phases
    executor.write_file("outline_confirmed.json", json.dumps(outline_data, ensure_ascii=False, indent=2))

    # Read design_spec.md
    design_spec_content = ""
    try:
        design_spec_content = executor.read_file("design_spec.md")
    except Exception:
        pass

    # Save design_spec to state
    session_mgr.update_phase(session_id, "planning")

    # Agent message with summary
    total = len(outline_data.get("pages", []))
    palette = outline_data.get("meta", {}).get("palette", "indigo")
    await send_agent_message(ws, "strategist",
        f"分析完成！建议 {total} 页，使用 {palette} 风格。\n"
        f"请检查下方大纲，可在输入框中用文字告诉我需要修改的地方，或直接确认开始生成。"
    )

    # Send outline to frontend
    pages = [
        OutlinePage(
            index=p.get("index", i + 1),
            title=p.get("title", ""),
            layout=p.get("layout", "L3"),
            bullets=p.get("bullets", []),
            notes=p.get("notes", ""),
        )
        for i, p in enumerate(outline_data.get("pages", []))
    ]

    await ws.send_json(OutlineMessage(
        data=OutlinePayload(
            pages=pages,
            design_spec=outline_data.get("meta", {}),
            meta={
                "palette": outline_data.get("meta", {}).get("palette", "indigo"),
                "total_pages": len(pages),
                "design_spec_saved": bool(design_spec_content),
            }
        )
    ).model_dump())


async def handle_confirm_outline(ws: WebSocket, raw: dict, executor: SandboxedExecutor, session_id: str):
    """Phase 2: User confirms outline → Generator produces SVGs → Reviewer audits."""
    msg = ConfirmOutlineMessage(**raw)

    if not msg.data.approved and msg.data.modified_outline:
        # User modified the outline — save it
        outline_json = json.dumps(
            {"pages": [p.model_dump() for p in msg.data.modified_outline]},
            ensure_ascii=False, indent=2,
        )
        executor.write_file("outline_confirmed.json", outline_json)

    session_mgr.update_phase(session_id, "generating")

    # Load outline
    try:
        outline_raw = executor.read_file("outline_confirmed.json")
        outline = json.loads(outline_raw)
    except Exception:
        # Fallback: read design_spec.md and parse outline
        try:
            spec = executor.read_file("design_spec.md")
            outline = {"pages": _parse_pages_from_spec(spec)}
            executor.write_file("outline_confirmed.json", json.dumps(outline, ensure_ascii=False, indent=2))
        except Exception as e:
            await ws.send_json(ErrorMessage(
                data=ErrorPayload(message=f"No outline found: {e}", phase="generating")
            ).model_dump())
            return

    pages = outline.get("pages", [])
    total = len(pages)
    session_mgr.update_slides(session_id, 0, total)

    # Load design_spec
    try:
        design_spec = executor.read_file("design_spec.md")
    except Exception:
        design_spec = ""

    # Generator Agent
    gen_agent = GeneratorAgent(executor)
    meta = outline.get("meta") or {}
    palette = meta.get("palette", "indigo") if isinstance(meta, dict) else "indigo"

    generated_slides: List[dict] = []
    previous_slides: List[dict] = []

    SVG_MIN_CHARS = 600
    FORBIDDEN_IN_SVG = ["<foreignObject", "<mask", "<style>", "<textPath", "@font-face",
                         "<animate", "<script", "<iframe", "rgba("]

    session_mgr.reset_cancelled(session_id)

    await send_agent_message(ws, "generator", f"开始生成 {total} 页幻灯片...")

    for i, page in enumerate(pages):
        if session_mgr.is_cancelled(session_id):
            logger.info(f"Generation cancelled by user at slide {i+1}/{total}")
            await ws.send_json(ErrorMessage(
                data=ErrorPayload(message="已取消生成", phase="generating", recoverable=True)
            ).model_dump())
            session_mgr.update_phase(session_id, "idle")
            return
        try:
            idx = page.get("index", i + 1)
            svg_content = ""

            await send_agent_thinking(ws, "generator", f"正在生成第 {idx}/{total} 页: {page.get('title', '')}", tool_name="generate_svg")

            for retry in range(2):  # max 2 attempts
                user_prompt = gen_agent.build_prompt(
                    mode="full_generation",
                    design_spec=design_spec if retry == 0 else "",
                    page_outline=page,
                    previous_slides=previous_slides,
                    palette=palette,
                )
                svg_response = await asyncio.to_thread(gen_agent.run, user_prompt)

                svg_content = extract_svg_from_response(svg_response)

                # If extract failed, try reading the saved file (Agent may have used write_file)
                if not svg_content:
                    try:
                        saved = executor.read_file(f"svg_output/slide_{idx:02d}.svg")
                        svg_from_file = extract_svg_from_response(saved)
                        if svg_from_file:
                            svg_content = svg_from_file
                    except Exception:
                        pass

                # If still no SVG, use raw response as last resort
                if not svg_content:
                    svg_content = svg_response.strip()

                # Validate: must contain actual SVG tag AND be long enough AND no forbidden elements
                is_svg = "<svg" in svg_content[:200]
                has_forbidden = any(f in svg_content for f in FORBIDDEN_IN_SVG)
                too_short = len(svg_content) < SVG_MIN_CHARS

                if is_svg and not too_short and not has_forbidden:
                    break
                if not is_svg:
                    logger.warning(f"Slide {idx} attempt {retry+1}: response is not SVG (starts with: {svg_content[:80]})")
                if has_forbidden:
                    logger.warning(f"Slide {idx} attempt {retry+1}: contains forbidden SVG elements, retrying...")
                if too_short:
                    logger.warning(f"Slide {idx} attempt {retry+1}: SVG too short ({len(svg_content)} chars), retrying...")

            # Save SVG
            svg_path = f"svg_output/slide_{idx:02d}.svg"
            executor.write_file(svg_path, svg_content)

            slide_info = {"index": idx, "layout": page.get("layout", "L3"), "svg": svg_content}
            generated_slides.append(slide_info)
            previous_slides.append(slide_info)

            # Push to frontend
            await ws.send_json(SlideGeneratedMessage(
                data=SlideGeneratedPayload(index=idx, svg=svg_content, layout=page.get("layout", "L3"))
            ).model_dump())

            session_mgr.update_slides(session_id, i + 1, total)

        except Exception as e:
            logger.error(f"Generator error on slide {i+1}: {e}")
            await ws.send_json(ErrorMessage(
                data=ErrorPayload(message=f"Failed to generate slide {i+1}: {e}", phase="generating")
            ).model_dump())

    await send_agent_message(ws, "generator", f"全部 {total} 页生成完毕！交由 Reviewer 审查...")

    # Auto-trigger Reviewer
    session_mgr.update_phase(session_id, "reviewing")
    session_mgr.update_review(session_id, 1)

    await send_agent_thinking(ws, "reviewer", "正在审查内容逻辑与信息层级...")

    reviewer = ReviewerAgent(executor)
    summaries = build_slide_summaries(generated_slides)
    try:
        review_response = await asyncio.to_thread(
            reviewer.run,
            f"Review these slide summaries and report content/hierarchy issues:\n\n"
            f"{json.dumps(summaries, ensure_ascii=False, indent=2)}"
        )
        review_data = reviewer.parse_review_report(review_response)
    except Exception as e:
        logger.error(f"Reviewer error: {e}")
        review_data = {"issues": [], "summary": f"Reviewer unavailable: {e}"}

    # Supplement with ConstraintValidator
    validator = ConstraintValidator(palette)
    for si in generated_slides:
        svg_issues = validator.validate_svg_content(si["svg"], si["index"])
        for iss in svg_issues:
            review_data.setdefault("issues", []).append({
                "page": iss.page_index,
                "severity": iss.severity,
                "category": iss.category,
                "element_id": iss.element_id,
                "description": iss.description,
                "suggestion": iss.suggested_fix,
            })

    # Text measurement (Layer 2 — PIL precise)
    for si in generated_slides:
        measured = measure_svg_text(si["svg"], use_pil=True)
        overflow_items = [m for m in measured if m.overflow_ratio > 1.02]
        for m in overflow_items:
            sev = "error" if m.overflow_ratio > 1.15 else "warning" if m.overflow_ratio > 1.05 else "suggestion"
            review_data.setdefault("issues", []).append({
                "page": si["index"],
                "severity": sev,
                "category": "layout",
                "element_id": m.element_id,
                "description": f"PIL measured overflow: '{m.text[:30]}...' ({m.measured_width:.0f}px) in container ({m.container_width:.0f}px, {m.overflow_ratio-1:.0%})",
                "suggestion": "Shorten text or reduce font size to fit container",
            })

    # Reviewer speaks
    issue_count = len(review_data.get("issues", []))
    if issue_count == 0:
        await send_agent_message(ws, "reviewer", "审查完成，所有页面均通过检查！可以直接导出。")
    else:
        errors = sum(1 for i in review_data.get("issues", []) if i.get("severity") == "error")
        warnings = sum(1 for i in review_data.get("issues", []) if i.get("severity") == "warning")
        await send_agent_message(ws, "reviewer",
            f"审查完成，发现 {issue_count} 个问题"
            + (f"（{errors} 严重" + (f", {warnings} 警告" if warnings else "") + "）" if errors else "")
            + "。请在下方查看并决定如何处理。"
        )

    # Save review data for fix cycle
    executor.write_file("review_report.json", json.dumps(review_data, ensure_ascii=False, indent=2))

    # Send review report to frontend
    issues = [
        ReviewIssue(
            page=iss.get("page", 0),
            severity=iss.get("severity", "warning"),
            category=iss.get("category", "layout"),
            description=iss.get("description", ""),
            suggestion=iss.get("suggestion", ""),
            element_id=iss.get("element_id", ""),
        )
        for iss in review_data.get("issues", [])
    ]

    await ws.send_json(ReviewReportMessage(
        data=ReviewReportPayload(
            issues=issues,
            summary=review_data.get("summary", f"Checked {total} pages"),
            current_round=1,
            max_rounds=3,
        )
    ).model_dump())


async def handle_fix_decisions(ws: WebSocket, raw: dict, executor: SandboxedExecutor, session_id: str):
    """Phase 3: User decides what to fix → Generator fixes → Reviewer re-checks."""
    msg = FixDecisionsMessage(**raw)
    fix_pages = msg.data.fix
    feedback = msg.data.feedback
    ignore_pages = msg.data.ignore

    if not fix_pages:
        # Nothing to fix, proceed to export
        await _do_export(ws, executor, session_id)
        return

    # Load review report for context
    try:
        review_data = json.loads(executor.read_file("review_report.json"))
    except Exception:
        review_data = {"issues": [], "round": 0}

    current_round = review_data.get("round", 0) + 1
    session_mgr.update_phase(session_id, "generating")
    session_mgr.update_review(session_id, current_round)

    # Load outline for correct layout + title info per page
    try:
        outline_data = json.loads(executor.read_file("outline_confirmed.json"))
    except Exception:
        outline_data = {"pages": [], "meta": {}}
    pages_lookup = {p.get("index"): p for p in outline_data.get("pages", [])}
    meta = outline_data.get("meta") or {}
    palette = meta.get("palette", "indigo") if isinstance(meta, dict) else "indigo"

    # Build per-page review context
    issues_by_page: dict = {}
    for iss in review_data.get("issues", []):
        pg = iss.get("page", 0)
        if pg in fix_pages:
            issues_by_page.setdefault(pg, []).append(iss)

    # Parse structured feedback: extract per-page notes from the combined string.
    global_feedback = feedback.strip() if feedback else ""
    per_page_feedback: dict = {}
    if feedback:
        for m in re.finditer(r'\[\u7b2c(\d+)\u9875\]\s*(.*)', feedback):
            pg_num = int(m.group(1))
            per_page_feedback[pg_num] = m.group(2).strip()
        first_bracket = feedback.find("[\u7b2c")
        if first_bracket > 0:
            global_feedback = feedback[:first_bracket].strip()
        elif first_bracket == 0:
            global_feedback = ""

    # Load existing SVGs for style context (include ALL slides as anchors)
    previous_slides = []
    for f in sorted(executor.list_dir("svg_output")):
        if f.endswith(".svg") and ".before_fix" not in f:
            try:
                content_f = executor.read_file(f"svg_output/{f}")
                idx_match = re.search(r'slide_(\d+)', f)
                idx = int(idx_match.group(1)) if idx_match else 0
                layout = ""
                page_info = pages_lookup.get(idx, {})
                if page_info:
                    layout = page_info.get("layout", "")
                previous_slides.append({"index": idx, "svg": content_f, "layout": layout})
            except Exception:
                pass

    gen_agent = GeneratorAgent(executor)
    design_spec = ""
    try:
        design_spec = executor.read_file("design_spec.md")
    except Exception:
        pass

    await send_agent_message(ws, "reviewer", f"正在修复 {len(fix_pages)} 页...")

    fixed_pages_list = []

    for pg in fix_pages:
        page_info = pages_lookup.get(pg, {"title": f"Slide {pg}", "layout": "L3", "bullets": []})
        page_feedback = "\n".join(
            f"[{iss.get('severity')}] {iss.get('category')}: {iss.get('description')}\n"
            f"  Suggested fix: {iss.get('suggestion', 'N/A')}"
            for iss in issues_by_page.get(pg, [])
        )
        pg_user = per_page_feedback.get(pg, "")
        if pg_user:
            page_feedback = f"User feedback for this page: {pg_user}\n\n{page_feedback}"
        if global_feedback:
            page_feedback = f"User feedback: {global_feedback}\n\n{page_feedback}"

        try:
            # Backup current SVG before fixing
            backup_path = f"svg_output/slide_{pg:02d}.before_fix.svg"
            try:
                old_svg = executor.read_file(f"svg_output/slide_{pg:02d}.svg")
                executor.write_file(backup_path, old_svg)
            except Exception:
                old_svg = ""

            await send_agent_thinking(ws, "generator", f"正在修复第 {pg} 页: {page_info.get('title', '')}", tool_name="fix_svg")

            user_prompt = gen_agent.build_prompt(
                mode="fix_specific_pages",
                design_spec=design_spec,
                page_outline=page_info,
                previous_slides=previous_slides[-3:],
                review_feedback=page_feedback,
                palette=palette,
            )
            svg_response = await asyncio.to_thread(gen_agent.run, user_prompt)
            svg_content = _extract_svg(svg_response)
            if not svg_content:
                svg_content = svg_response

            executor.write_file(f"svg_output/slide_{pg:02d}.svg", svg_content)
            fixed_pages_list.append(pg)

            await ws.send_json(SlideFixedMessage(
                data=SlideFixedPayload(index=pg, svg=svg_content, fix_round=current_round)
            ).model_dump())

        except Exception as e:
            logger.error(f"Fix error on slide {pg}: {e}")

    # Re-run Reviewer
    await send_agent_thinking(ws, "reviewer", "正在重新审查修复后的页面...")
    session_mgr.update_phase(session_id, "reviewing")
    reviewer = ReviewerAgent(executor)
    try:
        review_response = await asyncio.to_thread(
            reviewer.run,
            f"Review all SVG files again (fix round {current_round}). "
            f"Focus on pages that were just fixed: {fix_pages}"
        )
        new_review = reviewer.parse_review_report(review_response)
    except Exception as e:
        new_review = {"issues": [], "summary": f"Re-review failed: {e}"}

    new_review["round"] = current_round
    executor.write_file("review_report.json", json.dumps(new_review, ensure_ascii=False, indent=2))

    remaining = len(new_review.get("issues", []))

    if remaining == 0:
        await send_agent_message(ws, "reviewer", "所有问题已修复！可以导出了。")
    else:
        await send_agent_message(ws, "reviewer",
            f"修复完成，还剩 {remaining} 个问题。请查看并决定是否继续修复或直接导出。"
        )

    # Send batch done — user decides next step via FixBatchDoneCard
    await ws.send_json(FixBatchDoneMessage(
        data=FixBatchDonePayload(fixed_pages=fixed_pages_list, total_issues_remaining=remaining)
    ).model_dump())


async def handle_confirm_page_fix(ws: WebSocket, raw: dict, executor: SandboxedExecutor, session_id: str):
    """User confirms or rejects a single page fix."""
    msg = ConfirmPageFixMessage(**raw)
    idx = msg.data.index
    approved = msg.data.approved
    feedback = msg.data.feedback

    if approved:
        # Page is good, keep the fix
        # Delete backup
        try:
            backup = f"svg_output/slide_{idx:02d}.before_fix.svg"
            executor.delete_file(backup)
        except Exception:
            pass
        await send_agent_message(ws, "reviewer", f"第 {idx} 页已确认。")
    else:
        # User wants to re-fix or revert
        if "放弃" in feedback or "revert" in feedback.lower():
            # Revert to pre-fix version
            try:
                old_svg = executor.read_file(f"svg_output/slide_{idx:02d}.before_fix.svg")
                executor.write_file(f"svg_output/slide_{idx:02d}.svg", old_svg)
                await ws.send_json(SlideFixedMessage(
                    data=SlideFixedPayload(index=idx, svg=old_svg, fix_round=0)
                ).model_dump())
                await send_agent_message(ws, "reviewer", f"第 {idx} 页已回退到修复前版本。")
            except Exception:
                await send_agent_message(ws, "reviewer", f"第 {idx} 页无法回退（备份不存在）。")
        else:
            # Re-fix with new feedback - delegate to fix flow
            await send_agent_message(ws, "reviewer", f"收到，正在根据意见重新修复第 {idx} 页...")
            # We can reuse the fix logic by calling a mini fix
            try:
                gen_agent = GeneratorAgent(executor)
                design_spec = ""
                try:
                    design_spec = executor.read_file("design_spec.md")
                except Exception:
                    pass
                try:
                    outline_data = json.loads(executor.read_file("outline_confirmed.json"))
                except Exception:
                    outline_data = {"pages": []}
                pages_lookup = {p.get("index"): p for p in outline_data.get("pages", [])}
                page_info = pages_lookup.get(idx, {"title": f"Slide {idx}", "layout": "L3", "bullets": []})
                meta = outline_data.get("meta") or {}
                palette = meta.get("palette", "indigo") if isinstance(meta, dict) else "indigo"

                page_feedback = f"User feedback: {feedback}"

                await send_agent_thinking(ws, "generator", f"正在重新修复第 {idx} 页...", tool_name="fix_svg")

                user_prompt = gen_agent.build_prompt(
                    mode="fix_specific_pages",
                    design_spec=design_spec,
                    page_outline=page_info,
                    previous_slides=[],
                    review_feedback=page_feedback,
                    palette=palette,
                )
                svg_response = await asyncio.to_thread(gen_agent.run, user_prompt)
                svg_content = _extract_svg(svg_response)
                if not svg_content:
                    svg_content = svg_response
                executor.write_file(f"svg_output/slide_{idx:02d}.svg", svg_content)

                await ws.send_json(SlideFixedMessage(
                    data=SlideFixedPayload(index=idx, svg=svg_content, fix_round=0)
                ).model_dump())
                await send_agent_message(ws, "reviewer", f"第 {idx} 页已重新修复，请查看。")
            except Exception as e:
                logger.error(f"Re-fix error on slide {idx}: {e}")
                await send_agent_message(ws, "reviewer", f"重新修复失败: {e}")


async def handle_undo_fix(ws: WebSocket, executor: SandboxedExecutor, session_id: str):
    """User wants to revert all fixes from the last round."""
    # Restore all .before_fix.svg backups
    restored = []
    try:
        for f in executor.list_dir("svg_output"):
            if f.endswith(".before_fix.svg"):
                idx_match = re.search(r'slide_(\d+)', f)
                if idx_match:
                    idx = int(idx_match.group(1))
                    old_svg = executor.read_file(f"svg_output/{f}")
                    executor.write_file(f"svg_output/slide_{idx:02d}.svg", old_svg)
                    restored.append(idx)
                    # Send updated slide to frontend
                    await ws.send_json(SlideFixedMessage(
                        data=SlideFixedPayload(index=idx, svg=old_svg, fix_round=0)
                    ).model_dump())
                    # Clean up backup
                    executor.delete_file(f"svg_output/{f}")
    except Exception as e:
        logger.error(f"Undo fix error: {e}")

    session_mgr.update_phase(session_id, "reviewing")

    if restored:
        await send_agent_message(ws, "reviewer", f"已回退 {len(restored)} 页到修复前版本（第 {restored} 页）。正在重新审查...")

        # Delete old review report to prevent stale data
        try:
            executor.delete_file("review_report.json")
        except Exception:
            pass

        # Re-run Reviewer on the reverted SVGs
        await send_agent_thinking(ws, "reviewer", "正在重新审查回退后的页面...")
        reviewer = ReviewerAgent(executor)
        # Rebuild summaries from current SVG files
        from agents.reviewer import build_slide_summaries
        current_slides = []
        for f in sorted(executor.list_dir("svg_output")):
            if f.endswith(".svg") and ".before_fix" not in f:
                try:
                    svg_content = executor.read_file(f"svg_output/{f}")
                    idx_match = re.search(r'slide_(\d+)', f)
                    idx = int(idx_match.group(1)) if idx_match else 0
                    current_slides.append({"index": idx, "svg": svg_content, "layout": "", "title": ""})
                except Exception:
                    pass

        summaries = build_slide_summaries(current_slides)
        try:
            review_response = await asyncio.to_thread(
                reviewer.run,
                f"Review these slide summaries and report content/hierarchy issues:\n\n"
                f"{json.dumps(summaries, ensure_ascii=False, indent=2)}"
            )
            new_review = reviewer.parse_review_report(review_response)
        except Exception as e:
            logger.error(f"Re-review after undo failed: {e}")
            new_review = {"issues": [], "summary": f"Re-review failed: {e}"}

        new_review["round"] = 0
        executor.write_file("review_report.json", json.dumps(new_review, ensure_ascii=False, indent=2))

        issues = [
            ReviewIssue(
                page=iss.get("page", 0),
                severity=iss.get("severity", "warning"),
                category=iss.get("category", "layout"),
                description=iss.get("description", ""),
                suggestion=iss.get("suggestion", ""),
                element_id=iss.get("element_id", ""),
            )
            for iss in new_review.get("issues", [])
        ]

        await ws.send_json(ReviewReportMessage(
            data=ReviewReportPayload(
                issues=issues,
                summary=new_review.get("summary", ""),
                current_round=0,
                max_rounds=999,
            )
        ).model_dump())

        issue_count = len(issues)
        if issue_count == 0:
            await send_agent_message(ws, "reviewer", "回退完成，重新审查通过，没有问题。可以直接导出。")
        else:
            await send_agent_message(ws, "reviewer", f"回退完成，重新审查发现 {issue_count} 个问题。请查看。")
    else:
        await send_agent_message(ws, "reviewer", "没有可回退的修复。")


async def handle_review_feedback(ws: WebSocket, raw: dict, executor: SandboxedExecutor, session_id: str):
    """During review phase, user sends text feedback. Reviewer interprets and acts."""
    msg = UserMessageMessage(**raw)
    text = msg.data.text.strip()
    if not text:
        return

    # Load current review data for context
    try:
        review_data = json.loads(executor.read_file("review_report.json"))
    except Exception:
        review_data = {"issues": []}
    issues = review_data.get("issues", [])

    # Load outline for page info
    try:
        outline_data = json.loads(executor.read_file("outline_confirmed.json"))
    except Exception:
        outline_data = {"pages": []}

    # Build context for the Reviewer to interpret user intent
    issues_summary = "\n".join(
        f"- Page {iss.get('page')} [{iss.get('severity')}] {iss.get('category')}: {iss.get('description')}"
        for iss in issues
    ) if issues else "No issues found."

    pages_summary = "\n".join(
        f"- Page {p.get('index')}: {p.get('title')} ({p.get('layout')})"
        for p in outline_data.get("pages", [])
    )

    await send_agent_thinking(ws, "reviewer", "正在理解您的意图...")

    # Use Reviewer to interpret user intent and produce a structured action
    reviewer = ReviewerAgent(executor)
    interpret_prompt = (
        f"A user is reviewing generated slides and has sent this message:\n\n"
        f"\"\"\"\n{text}\n\"\"\"\n\n"
        f"Current issues found:\n{issues_summary}\n\n"
        f"Pages:\n{pages_summary}\n\n"
        f"Interpret the user\'s intent and return a JSON action:\n"
        f'- If they want to fix specific pages: {{"action": "fix", "pages": [3, 5], "instructions": "what to change"}}\n'
        f'- If they want to fix all issues: {{"action": "fix_all", "instructions": "what to change"}}\n'
        f'- If they want to skip and export: {{"action": "export"}}\n'
        f'- If they have a question or comment: {{"action": "reply", "message": "your response to the user"}}\n'
        f'- If they want to undo recent fixes: {{"action": "undo"}}\n\n'
        f"Return ONLY the JSON object, nothing else."
    )

    try:
        response = await asyncio.to_thread(reviewer.run, interpret_prompt)
        action = reviewer.parse_review_report(response)  # reuse JSON parser
        # parse_review_report looks for "issues" key, but we need generic JSON
        # Try direct parse
        import json as _json
        try:
            # Try to find JSON in response
            for m in re.finditer(r'\{', response):
                depth = 1
                i = m.start() + 1
                while i < len(response) and depth > 0:
                    if response[i] == '{': depth += 1
                    elif response[i] == '}': depth -= 1
                    i += 1
                if depth == 0:
                    candidate = response[m.start():i]
                    try:
                        action = _json.loads(candidate)
                        break
                    except _json.JSONDecodeError:
                        continue
            else:
                action = {"action": "reply", "message": response[:300]}
        except Exception:
            action = {"action": "reply", "message": response[:300]}
    except Exception as e:
        logger.error(f"Reviewer interpretation error: {e}")
        action = {"action": "reply", "message": f"无法理解您的意图: {e}"}

    act = action.get("action", "reply")

    if act == "fix":
        pages = action.get("pages", [])
        instructions = action.get("instructions", text)
        if pages:
            await send_agent_message(ws, "reviewer", f"好的，正在修复第 {pages} 页...")
            # Delegate to fix flow
            fake_fix = FixDecisionsMessage(**{
                "type": "fix_decisions",
                "data": {"fix": pages, "ignore": [], "feedback": instructions}
            })
            await handle_fix_decisions(ws, fake_fix.model_dump(), executor, session_id)
        else:
            await send_agent_message(ws, "reviewer", "请指定需要修复的页面。")

    elif act == "fix_all":
        instructions = action.get("instructions", text)
        all_pages = list(set(iss.get("page", 0) for iss in issues))
        if all_pages:
            await send_agent_message(ws, "reviewer", f"好的，正在修复全部 {len(all_pages)} 个问题页面...")
            fake_fix = FixDecisionsMessage(**{
                "type": "fix_decisions",
                "data": {"fix": all_pages, "ignore": [], "feedback": instructions}
            })
            await handle_fix_decisions(ws, fake_fix.model_dump(), executor, session_id)
        else:
            await send_agent_message(ws, "reviewer", "没有需要修复的问题。")

    elif act == "export":
        await send_agent_message(ws, "reviewer", "好的，跳过修复，直接导出。")
        await _do_export(ws, executor, session_id)

    elif act == "undo":
        await handle_undo_fix(ws, executor, session_id)

    elif act == "reply":
        reply_msg = action.get("message", "我不太确定您的意思，能再说详细一些吗？")
        await send_agent_message(ws, "reviewer", reply_msg)

    else:
        await send_agent_message(ws, "reviewer", "我不太确定您的意思，能再说详细一些吗？")


async def handle_download(ws: WebSocket, executor: SandboxedExecutor, session_id: str):
    """Phase 4: Export to PPTX."""
    await _do_export(ws, executor, session_id)


async def _do_export(ws: WebSocket, executor: SandboxedExecutor, session_id: str):
    """Run finalize_svg + svg_to_pptx pipeline."""
    session_mgr.update_phase(session_id, "done")

    # Step 1: SVG post-processing
    try:
        result = await asyncio.to_thread(
            executor.run_script, "finalize_svg.py", ["."]
        )
        logger.info(f"finalize_svg output: {result[:200]}")
    except Exception as e:
        logger.error(f"finalize_svg failed: {e}")
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(message=f"SVG post-processing failed: {e}", phase="export")
        ).model_dump())
        return

    # Step 2: Export to PPTX
    try:
        result = await asyncio.to_thread(
            executor.run_script, "svg_to_pptx.py", [".", "-s", "final"]
        )
        logger.info(f"svg_to_pptx output: {result[:200]}")
    except Exception as e:
        logger.error(f"svg_to_pptx failed: {e}")
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(message=f"PPTX export failed: {e}", phase="export")
        ).model_dump())
        return

    # Find exported file
    exports_dir = executor._safe_path("exports")
    pptx_files = sorted(exports_dir.glob("*.pptx"), key=os.path.getmtime, reverse=True)
    if not pptx_files:
        # Try copying from outputs
        for f in sorted(OUTPUTS_DIR.glob("*.pptx"), key=os.path.getmtime, reverse=True):
            shutil.copy(f, exports_dir / f.name)
        pptx_files = sorted(exports_dir.glob("*.pptx"), key=os.path.getmtime, reverse=True)

    if pptx_files:
        filename = pptx_files[0].name
        session_mgr.set_export(session_id, filename)

        # Strategist closing message
        try:
            outline_data = json.loads(executor.read_file("outline_confirmed.json"))
            total = len(outline_data.get("pages", []))
            palette = outline_data.get("meta", {}).get("palette", "indigo")
        except Exception:
            total = "?"
            palette = "indigo"
        await send_agent_message(ws, "generator",
            f"PPT 已生成完毕！共 {total} 页，使用 {palette} 风格。\n"
            f"所有元素均为原生 PowerPoint 形状，可直接编辑。"
        )

        await ws.send_json(DoneMessage(
            data=DonePayload(
                download_url=f"/download/{session_id}",
                filename=filename,
                session_id=session_id,
            )
        ).model_dump())
    else:
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(message="PPTX file not found after export", phase="export")
        ).model_dump())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _convert_sources(executor: SandboxedExecutor):
    """Convert uploaded PDF/DOCX/ZIP files. ZIP files are extracted into sources/repo/."""
    sources_dir = executor._safe_path("sources")
    for f in sources_dir.iterdir():
        if f.suffix.lower() == ".pdf":
            try:
                await asyncio.to_thread(
                    executor.run_script, "pdf_to_md.py", [f"sources/{f.name}"]
                )
                logger.info(f"PDF converted: {f.name}")
            except Exception as e:
                logger.warning(f"PDF conversion failed ({f.name}): {e}")
        elif f.suffix.lower() in (".docx", ".doc"):
            try:
                await asyncio.to_thread(
                    executor.run_script, "doc_to_md.py", [f"sources/{f.name}"]
                )
                logger.info(f"DOCX converted: {f.name}")
            except Exception as e:
                logger.warning(f"DOCX conversion failed ({f.name}): {e}")
        elif f.suffix.lower() == ".zip":
            try:
                result = await asyncio.to_thread(executor.extract_zip, f"sources/{f.name}")
                logger.info(f"ZIP extracted: {f.name}\n{result[:200]}")
            except Exception as e:
                logger.warning(f"ZIP extraction failed ({f.name}): {e}")


def _detect_github_url(text: str) -> str | None:
    """Detect a GitHub/GitLab URL in user text."""
    import re
    m = re.search(r'(https?://(?:github\.com|gitlab\.com)/[\w.-]+/[\w.-]+)', text)
    return m.group(1) if m else None


def _extract_svg(response: str) -> str:
    """Extract SVG code from an LLM response (may contain markdown fences)."""
    # Try ```svg ... ``` fence
    m = re.search(r'```(?:svg|xml)?\s*\n?(<svg[\s\S]*?</svg>)\s*\n?```', response, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Try <svg>...</svg> directly
    m = re.search(r'(<svg[\s\S]*?</svg>)', response, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _parse_pages_from_spec(spec: str) -> list:
    """Fallback: try to extract pages from design_spec.md content outline section."""
    pages = []
    ix_section = re.search(r'(?:IX|9)\.?\s*Content Outline(.*?)(?:X\.|\Z)', spec, re.DOTALL | re.IGNORECASE)
    if not ix_section:
        return pages
    section_text = ix_section.group(1)
    # Look for page entries like "| 1 | Cover | L1 | ... |"
    for line in section_text.split("\n"):
        m = re.match(r'\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(L\d)\s*\|', line)
        if m:
            pages.append({
                "index": int(m.group(1)),
                "title": m.group(2).strip(),
                "layout": m.group(3).strip(),
                "bullets": [],
            })
    return pages


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    asyncio.create_task(_periodic_cleanup())


async def _periodic_cleanup():
    """Clean up expired sessions every 10 minutes."""
    while True:
        await asyncio.sleep(600)
        try:
            removed = await asyncio.to_thread(session_mgr.cleanup_expired)
            if removed:
                logger.info(f"Cleaned up {removed} expired sessions")
        except Exception as e:
            logger.warning(f"Session cleanup error: {e}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _validate_env():
    """Check required environment variables at startup."""
    missing = []
    if not os.getenv("DEEPSEEK_API_KEY"):
        missing.append("DEEPSEEK_API_KEY")
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.error("Create a .env file or set them in your shell.")
        logger.error("  cp .env.example .env &&  # then edit .env with your keys")
        sys.exit(1)
    logger.info("Environment validated ✓")

if __name__ == "__main__":
    _validate_env()
    import uvicorn
    port = int(os.getenv("SLIDEWISE_PORT", "8888"))
    logger.info(f"Starting SlideWise on http://127.0.0.1:{port}")
    uvicorn.run("main:app", host="127.0.0.1", port=port)
