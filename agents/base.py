"""
Agent infrastructure: sandboxed executor + DeepSeek API wrapper.

SandboxedExecutor — all file paths are agent-returned relative paths;
  the executor prepends PROJECT_ROOT and validates realpath containment.

BaseAgent — OpenAI-compatible tool-use loop. Subclasses define
  system_prompt + tools; the base handles the API conversation cycle.
"""

import os
import sys
import json
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger("slidewise.agent")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = PROJECT_ROOT / "engine"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
CONSTRAINTS_DIR = PROJECT_ROOT / "constraints"
SESSIONS_DIR = PROJECT_ROOT / "sessions"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Scripts that the agent is allowed to execute
ALLOWED_SCRIPTS = {
    "finalize_svg.py": ENGINE_DIR / "finalize_svg.py",
    "total_md_split.py": ENGINE_DIR / "total_md_split.py",
    "svg_to_pptx.py": ENGINE_DIR / "svg_to_pptx.py",
    "pdf_to_md.py": ENGINE_DIR / "source_to_md" / "pdf_to_md.py",
    "doc_to_md.py": ENGINE_DIR / "source_to_md" / "doc_to_md.py",
}

# Python interpreter to use for script execution
PYTHON_BIN = sys.executable  # works on both Windows (python) and Unix (python3)


# ---------------------------------------------------------------------------
# Sandboxed Executor
# ---------------------------------------------------------------------------

class SandboxError(Exception):
    """Raised when an operation violates sandbox boundaries."""


class SandboxedExecutor:
    """
    Constrained file I/O and script execution.

    Rules:
      - Agent returns RELATIVE paths only (e.g. "svg_output/slide_01.svg")
      - All paths are resolved under the session's work_dir
      - realpath is validated to be inside work_dir
      - Script execution requires the script name to be in ALLOWED_SCRIPTS
    """

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir.resolve()
        self.work_dir.mkdir(parents=True, exist_ok=True)

    # -- path safety -------------------------------------------------

    def _safe_path(self, relative_path: str, must_exist: bool = False) -> Path:
        """Resolve relative_path under work_dir; raise if it escapes."""
        # Strip leading slashes / drive letters
        cleaned = relative_path.lstrip("/").lstrip("\\")
        if cleaned.startswith("..") or os.path.isabs(cleaned):
            raise SandboxError(f"Path must be relative: {relative_path}")

        full = (self.work_dir / cleaned).resolve()
        if not str(full).startswith(str(self.work_dir)):
            raise SandboxError(f"Path escapes work dir: {relative_path} → {full}")

        if must_exist and not full.exists():
            raise SandboxError(f"File not found: {relative_path}")
        return full

    # -- file operations ---------------------------------------------

    def read_file(self, relative_path: str) -> str:
        """Read a file within the session workspace."""
        path = self._safe_path(relative_path, must_exist=True)
        logger.info(f"[sandbox] READ {relative_path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def write_file(self, relative_path: str, content: str) -> str:
        """Write content to a file within the session workspace."""
        path = self._safe_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        logger.info(f"[sandbox] WRITE {relative_path} ({len(content)} chars)")
        return f"Written {len(content)} chars to {relative_path}"

    def list_dir(self, relative_path: str = ".") -> List[str]:
        """List files and directories relative to workspace."""
        path = self._safe_path(relative_path, must_exist=True)
        entries = []
        for p in sorted(path.iterdir()):
            suffix = "/" if p.is_dir() else ""
            entries.append(p.name + suffix)
        return entries

    def delete_file(self, relative_path: str) -> str:
        """Delete a file or directory within the session workspace."""
        path = self._safe_path(relative_path, must_exist=True)
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        logger.info(f"[sandbox] DELETE {relative_path}")
        return f"Deleted {relative_path}"

    # -- script execution --------------------------------------------

    def run_script(self, script_name: str, args: List[str]) -> str:
        """
        Execute an allowed Python script.

        script_name must be in ALLOWED_SCRIPTS.
        args are appended to the command line.
        Working directory is set to the session work_dir.
        Timeout: 120 seconds.
        """
        if script_name not in ALLOWED_SCRIPTS:
            raise SandboxError(
                f"Script '{script_name}' not in allowlist. "
                f"Allowed: {list(ALLOWED_SCRIPTS.keys())}"
            )

        script_path = ALLOWED_SCRIPTS[script_name]
        cmd = [PYTHON_BIN, str(script_path)] + args
        logger.info(f"[sandbox] EXEC {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output
        except subprocess.TimeoutExpired:
            return "[ERROR] Script timed out (120s)"

    # -- reference file reading (for Agent tools) --------------------

    def read_reference(self, relative_path: str) -> str:
        """
        Read a reference/constraint file from the project codebase.
        Path is relative to PROJECT_ROOT.
        """
        cleaned = relative_path.lstrip("/").lstrip("\\")
        full = (PROJECT_ROOT / cleaned).resolve()
        if not str(full).startswith(str(PROJECT_ROOT)):
            raise SandboxError(f"Reference path escapes project: {relative_path}")
        if not full.exists():
            return f"[NOT FOUND] {relative_path}"
        return full.read_text(encoding="utf-8", errors="replace")

    def search_icon(self, keyword: str) -> str:
        """Search for icons in the built-in icon library."""
        icon_dir = TEMPLATES_DIR / "icons" / "chunk"
        if not icon_dir.exists():
            return "[NOT FOUND] Icon library not available"
        matches = []
        for f in icon_dir.glob("*.svg"):
            if keyword.lower() in f.stem.lower():
                matches.append(f"chunk/{f.stem}")
        if not matches:
            return f"No icons matching '{keyword}'"
        return "\n".join(matches[:20])


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

ToolDefinition = Dict[str, Any]   # OpenAI tool JSON schema


class BaseAgent:
    """
    DeepSeek API wrapper with native OpenAI-compatible function calling.

    Subclass and override:
      - system_prompt: str
      - chat_tools: List[ToolDefinition]
      - _execute_tool(name, args, executor) → str
    """

    system_prompt: str = ""
    chat_tools: List[ToolDefinition] = []
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    max_tool_rounds: int = 8
    temperature: float = 0.3
    use_json_mode: bool = False  # Force JSON output via response_format

    def __init__(self, executor: SandboxedExecutor):
        self.executor = executor
        self._client: Optional[OpenAI] = None
        self._history: List[Dict[str, Any]] = []

    # -- API client --------------------------------------------------

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            key = self.api_key or os.getenv("DEEPSEEK_API_KEY", "")
            url = self.base_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            model = os.getenv("DEEPSEEK_MODEL", self.model)
            self.model = model
            self._client = OpenAI(api_key=key, base_url=url)
        return self._client

    # -- Subclass override -------------------------------------------

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """
        Override in subclass to dispatch tool calls to the executor.
        Default: pass through to executor method of same name (if exists).
        """
        method = getattr(self.executor, name, None)
        if method:
            return method(**args)
        return f"[UNKNOWN TOOL] {name}"

    # -- Core call ---------------------------------------------------

    def _chat(self, messages: List[Dict]) -> str:
        """Single API call with optional tool definitions and json mode."""
        kwargs: Dict[str, Any] = dict(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )
        if self.chat_tools:
            kwargs["tools"] = self.chat_tools
            kwargs["tool_choice"] = "auto"
        if self.use_json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = self.client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        # Tool calls take priority (JSON mode may return whitespace as content)
        if msg.tool_calls:
            return json.dumps([
                {"id": tc.id, "name": tc.function.name, "args": tc.function.arguments}
                for tc in msg.tool_calls
            ])

        # Plain text response (only if non-empty and non-whitespace)
        if msg.content and msg.content.strip():
            return msg.content

        return ""

    # -- Tool-use loop -----------------------------------------------

    def run(
        self,
        user_message: str,
        extra_context: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Execute the full tool-use loop for a user message.

        1. Send system + user message
        2. If agent calls tools → execute → append results → loop
        3. If agent returns text → finish
        """
        messages: List[Dict[str, Any]] = []

        # System prompt
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # Extra context (e.g., design_spec, previous pages, review report)
        if extra_context:
            messages.extend(extra_context)

        # User message
        messages.append({"role": "user", "content": user_message})

        for _round in range(self.max_tool_rounds):
            response_text = self._chat(messages)

            # Check if it's tool calls (JSON array)
            tool_calls = self._parse_tool_calls(response_text)

            if tool_calls:
                # Append assistant message
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["args"],
                            }
                        }
                        for tc in tool_calls
                    ]
                })

                # Execute each tool
                for tc in tool_calls:
                    try:
                        args = json.loads(tc["args"]) if isinstance(tc["args"], str) else tc["args"]
                    except json.JSONDecodeError:
                        args = {}
                    result = self._execute_tool(tc["name"], args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
                    logger.info(f"[agent] tool {tc['name']} → {len(result)} chars")

                continue  # loop for next assistant response

            # Plain text — done
            self._history = messages
            return response_text

        return "[ERROR] Max tool rounds exceeded"

    def _parse_tool_calls(self, response_text: str) -> List[Dict[str, Any]]:
        """Try to parse the response as tool call JSON."""
        text = response_text.strip()
        if text.startswith("[") and "tool_calls" not in text.lower():
            # It might be the assistant returning an array in text form
            pass

        # Check for tool_calls in the native format
        # The DeepSeek API returns content or tool_calls.
        # We might get a JSON array if the model outputs tool calls as text.
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                # Verify it looks like tool calls
                if all("name" in item and "args" in item for item in parsed):
                    return parsed
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    def reset_history(self):
        """Clear conversation history."""
        self._history = []


# ---------------------------------------------------------------------------
# Tool schema helpers
# ---------------------------------------------------------------------------

def make_tool(name: str, description: str, properties: Dict, required: List[str]) -> ToolDefinition:
    """Build an OpenAI-compatible tool definition dict."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
