"""
WebSocket message protocol definitions.

Shared between backend (FastAPI) and frontend (single-page HTML).
All message types are typed with Pydantic for runtime validation.
"""

from enum import StrEnum
from typing import List, Optional, Any
from pydantic import BaseModel, Field


# ============================================================
# Message Types
# ============================================================

class MessageType(StrEnum):
    # Server → Client
    OUTLINE = "outline"
    SLIDE_GENERATED = "slide_generated"
    REVIEW_REPORT = "review_report"
    SLIDE_FIXED = "slide_fixed"
    DONE = "done"
    ERROR = "error"
    STATE_SYNC = "state_sync"

    # Client → Server
    USER_MESSAGE = "user_message"
    CONFIRM_OUTLINE = "confirm_outline"
    FIX_DECISIONS = "fix_decisions"
    RETRY_SLIDE = "retry_slide"
    DOWNLOAD = "download"
    RESUME_SESSION = "resume_session"
    LIST_SESSIONS = "list_sessions"


# ============================================================
# Server → Client Messages
# ============================================================

class OutlinePage(BaseModel):
    index: int
    title: str
    layout: str  # L1-L7
    bullets: List[str] = Field(default_factory=list)
    notes: str = ""

class OutlinePayload(BaseModel):
    pages: List[OutlinePage]
    design_spec: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)

class OutlineMessage(BaseModel):
    type: str = MessageType.OUTLINE
    data: OutlinePayload

class SlideGeneratedPayload(BaseModel):
    index: int
    svg: str  # raw SVG content
    layout: str = ""

class SlideGeneratedMessage(BaseModel):
    type: str = MessageType.SLIDE_GENERATED
    data: SlideGeneratedPayload

class ReviewIssue(BaseModel):
    page: int
    severity: str  # "error" | "warning" | "suggestion"
    category: str  # "style" | "layout" | "content" | "hierarchy" | "svg_compat"
    description: str
    suggestion: str = ""
    element_id: str = ""

class ReviewReportPayload(BaseModel):
    issues: List[ReviewIssue]
    summary: str
    current_round: int = 1
    max_rounds: int = 3

class ReviewReportMessage(BaseModel):
    type: str = MessageType.REVIEW_REPORT
    data: ReviewReportPayload

class SlideFixedPayload(BaseModel):
    index: int
    svg: str
    fix_round: int = 1

class SlideFixedMessage(BaseModel):
    type: str = MessageType.SLIDE_FIXED
    data: SlideFixedPayload

class DonePayload(BaseModel):
    download_url: str
    filename: str
    session_id: str

class DoneMessage(BaseModel):
    type: str = MessageType.DONE
    data: DonePayload

class ErrorPayload(BaseModel):
    message: str
    phase: str = ""  # which pipeline phase failed
    recoverable: bool = True

class ErrorMessage(BaseModel):
    type: str = MessageType.ERROR
    data: ErrorPayload

class StateSyncPayload(BaseModel):
    session_id: str
    phase: str  # "planning" | "generating" | "reviewing" | "done"
    outline: Optional[OutlinePayload] = None
    slides: dict = Field(default_factory=dict)  # {index: svg_content}
    review: Optional[ReviewReportPayload] = None

class StateSyncMessage(BaseModel):
    type: str = MessageType.STATE_SYNC
    data: StateSyncPayload


# ============================================================
# Client → Server Messages
# ============================================================

class UserMessagePayload(BaseModel):
    text: str
    files: List[dict] = Field(default_factory=list)  # [{name, content_base64, type}]
    style: str = ""  # user-specified style hint

class UserMessageMessage(BaseModel):
    type: str = MessageType.USER_MESSAGE
    data: UserMessagePayload

class ConfirmOutlinePayload(BaseModel):
    approved: bool
    modified_outline: Optional[List[OutlinePage]] = None
    feedback: str = ""

class ConfirmOutlineMessage(BaseModel):
    type: str = MessageType.CONFIRM_OUTLINE
    data: ConfirmOutlinePayload

class FixDecisionsPayload(BaseModel):
    fix: List[int] = Field(default_factory=list)       # page indices to fix
    ignore: List[int] = Field(default_factory=list)     # page indices to skip
    feedback: str = ""                                   # additional instructions

class FixDecisionsMessage(BaseModel):
    type: str = MessageType.FIX_DECISIONS
    data: FixDecisionsPayload

class RetrySlidePayload(BaseModel):
    index: int
    feedback: str

class RetrySlideMessage(BaseModel):
    type: str = MessageType.RETRY_SLIDE
    data: RetrySlidePayload

class DownloadMessage(BaseModel):
    type: str = MessageType.DOWNLOAD
    data: dict = Field(default_factory=dict)


# ============================================================
# Protocol helpers
# ============================================================

ServerMessage = (
    OutlineMessage | SlideGeneratedMessage | ReviewReportMessage |
    SlideFixedMessage | DoneMessage | ErrorMessage | StateSyncMessage
)

ClientMessage = (
    UserMessageMessage | ConfirmOutlineMessage | FixDecisionsMessage |
    RetrySlideMessage | DownloadMessage
)


class WSProtocol:
    """Encode / decode helpers for WebSocket JSON messages."""

    SERVER_HANDLERS = {
        MessageType.OUTLINE: OutlineMessage,
        MessageType.SLIDE_GENERATED: SlideGeneratedMessage,
        MessageType.REVIEW_REPORT: ReviewReportMessage,
        MessageType.SLIDE_FIXED: SlideFixedMessage,
        MessageType.DONE: DoneMessage,
        MessageType.ERROR: ErrorMessage,
        MessageType.STATE_SYNC: StateSyncMessage,
    }

    CLIENT_HANDLERS = {
        MessageType.USER_MESSAGE: UserMessageMessage,
        MessageType.CONFIRM_OUTLINE: ConfirmOutlineMessage,
        MessageType.FIX_DECISIONS: FixDecisionsMessage,
        MessageType.RETRY_SLIDE: RetrySlideMessage,
        MessageType.DOWNLOAD: DownloadMessage,
    }

    @classmethod
    def parse_client_message(cls, raw: dict) -> ClientMessage:
        msg_type = raw.get("type", "")
        handler = cls.CLIENT_HANDLERS.get(msg_type)
        if handler is None:
            raise ValueError(f"Unknown client message type: {msg_type}")
        return handler(**raw)

    @classmethod
    def encode_message(cls, msg: BaseModel) -> dict:
        return msg.model_dump()
