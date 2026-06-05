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
from agents.reviewer import ReviewerAgent
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
    phase = session_mgr.get_phase(session_id)
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

    # Run Strategist Agent
    agent = StrategistAgent(executor)
    try:
        response = await asyncio.to_thread(
            agent.run,
            f"Analyze the source documents and create a design_spec.md + Outline JSON.\n\n"
            f"User request: {text}",
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

    for i, page in enumerate(pages):
        try:
            idx = page.get("index", i + 1)
            svg_content = ""

            for retry in range(2):  # max 2 attempts
                user_prompt = gen_agent.build_prompt(
                    mode="full_generation",
                    design_spec=design_spec if retry == 0 else "",
                    page_outline=page,
                    previous_slides=previous_slides,
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

    # Auto-trigger Reviewer
    session_mgr.update_phase(session_id, "reviewing")
    session_mgr.update_review(session_id, 1)

    reviewer = ReviewerAgent(executor)
    try:
        review_response = await asyncio.to_thread(
            reviewer.run,
            "Review all SVG files in svg_output/ and produce a structured issue report."
        )
        review_data = reviewer.parse_review_report(review_response)
    except Exception as e:
        logger.error(f"Reviewer error: {e}")
        review_data = {"issues": [], "summary": f"Review failed: {e}"}

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
    max_rounds = 3
    if current_round > max_rounds:
        await ws.send_json(ErrorMessage(
            data=ErrorPayload(
                message=f"Max review rounds ({max_rounds}) reached. Remaining issues marked for manual fix.",
                phase="reviewing", recoverable=False,
            )
        ).model_dump())
        # Proceed to export anyway
        await _do_export(ws, executor, session_id)
        return

    session_mgr.update_phase(session_id, "generating")
    session_mgr.update_review(session_id, current_round)

    # Build per-page review context
    issues_by_page: dict = {}
    for iss in review_data.get("issues", []):
        pg = iss.get("page", 0)
        if pg in fix_pages:
            issues_by_page.setdefault(pg, []).append(iss)

    # Load existing SVGs for style context
    previous_slides = []
    for f in sorted(executor.list_dir("svg_output")):
        if f.endswith(".svg"):
            try:
                content = executor.read_file(f"svg_output/{f}")
                idx_match = re.search(r'slide_(\d+)', f)
                idx = int(idx_match.group(1)) if idx_match else 0
                if idx not in fix_pages:
                    previous_slides.append({"index": idx, "svg": content, "layout": ""})
            except Exception:
                pass

    gen_agent = GeneratorAgent(executor)
    design_spec = ""
    try:
        design_spec = executor.read_file("design_spec.md")
    except Exception:
        pass

    for pg in fix_pages:
        page_feedback = "\n".join(
            f"[{iss.get('severity')}] {iss.get('category')}: {iss.get('description')}\n"
            f"  Suggested fix: {iss.get('suggestion', 'N/A')}"
            for iss in issues_by_page.get(pg, [])
        )
        if feedback:
            page_feedback = f"User feedback: {feedback}\n\n{page_feedback}"

        try:
            user_prompt = gen_agent.build_prompt(
                mode="fix_specific_pages",
                design_spec=design_spec,
                page_outline={"index": pg, "title": f"Fixed slide {pg}", "layout": "L3"},
                previous_slides=previous_slides[-3:],
                review_feedback=page_feedback,
            )
            svg_response = await asyncio.to_thread(gen_agent.run, user_prompt)
            svg_content = _extract_svg(svg_response)
            if not svg_content:
                svg_content = svg_response

            executor.write_file(f"svg_output/slide_{pg:02d}.svg", svg_content)

            await ws.send_json(SlideFixedMessage(
                data=SlideFixedPayload(index=pg, svg=svg_content, fix_round=current_round)
            ).model_dump())

        except Exception as e:
            logger.error(f"Fix error on slide {pg}: {e}")

    # Re-run Reviewer
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
            current_round=current_round,
            max_rounds=max_rounds,
        )
    ).model_dump())


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
    """Convert uploaded PDF/DOCX files to Markdown."""
    sources_dir = executor._safe_path("sources")
    for f in sources_dir.iterdir():
        if f.suffix.lower() == ".pdf":
            try:
                output = await asyncio.to_thread(
                    executor.run_script, "pdf_to_md.py", [f"sources/{f.name}"]
                )
                logger.info(f"PDF converted: {f.name}")
            except Exception as e:
                logger.warning(f"PDF conversion failed ({f.name}): {e}")
        elif f.suffix.lower() in (".docx", ".doc"):
            try:
                output = await asyncio.to_thread(
                    executor.run_script, "doc_to_md.py", [f"sources/{f.name}"]
                )
                logger.info(f"DOCX converted: {f.name}")
            except Exception as e:
                logger.warning(f"DOCX conversion failed ({f.name}): {e}")


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
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True)
