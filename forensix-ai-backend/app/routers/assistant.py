"""
app/routers/assistant.py

Forensic AI chat assistant with persistent case context.

Endpoints:
  POST /assistant/chat          → Single-turn chat with case context injected
  POST /assistant/chat/stream   → Streaming chat (SSE)
  POST /assistant/session       → Create / update a named session
  GET  /assistant/session/{id}  → Retrieve session history
  DELETE /assistant/session/{id}→ Clear session
"""

import uuid
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import json
from app.services.llm_service import get_llm_response, get_llm_stream

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["Forensic Assistant"])

# ---------------------------------------------------------------------------
# In-memory session store  (replace with Redis / DB in production)
# ---------------------------------------------------------------------------
# Structure: { session_id: { "context": dict, "history": list[dict] } }
_sessions: dict[str, dict] = {}

SYSTEM_PROMPT = """
You are ForensiX AI — an expert forensic analysis assistant.
You help investigators by answering questions about case evidence, autopsy reports,
witness statements, timelines, risk scores, and investigative leads.

Rules:
- Always ground your answers in the provided case context.
- If the context does not contain enough information, say so clearly.
- Never speculate beyond the available evidence without marking it as speculation.
- Use precise forensic terminology.
- Be concise but thorough.
- When asked for recommendations, explain your reasoning step-by-step.
"""


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CaseContext(BaseModel):
    """Snapshot of known case data attached to the session."""
    case_id: str = Field("", description="Optional case identifier")
    victim: str = Field("", description="Victim name / description")
    location: str = Field("", description="Crime scene location")
    date: str = Field("", description="Incident date")
    report_summary: str = Field("", description="Key autopsy / forensic findings")
    evidence_summary: str = Field("", description="Summary of physical evidence")
    risk_score: dict = Field(default_factory=dict, description="Risk score result dict")
    anomalies: list[dict] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)
    leads: list[dict] = Field(default_factory=list)
    extra: dict = Field(default_factory=dict, description="Any additional key-value context")


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="User's question or instruction")
    session_id: str = Field("", description="Session ID (leave blank to start new session)")
    case_context: CaseContext | None = Field(None, description="Case context (merged into session)")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description="Optional explicit history (overrides stored history when provided)"
    )

    model_config = {"json_schema_extra": {"example": {
        "message": "What are the top investigative leads for this case?",
        "session_id": "",
        "case_context": {
            "case_id": "CASE-001",
            "victim": "John Doe",
            "location": "123 Main St",
            "date": "2024-01-15",
            "report_summary": "Blunt force trauma to the head. ToD: 00:00–02:00.",
            "evidence_summary": "Fingerprints on door handle, CCTV gap 23:45–01:00.",
            "risk_score": {"overall_risk": 74.5, "verdict": "HIGH"},
            "leads": []
        }
    }}}


class SessionCreateRequest(BaseModel):
    case_context: CaseContext
    session_id: str = Field("", description="Provide to update existing session")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    timestamp: str


class SessionResponse(BaseModel):
    session_id: str
    case_context: dict
    history: list[dict]
    created_at: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_context_block(ctx: dict) -> str:
    """Render the case context dict as a readable block for the LLM prompt."""
    lines = ["=== CASE CONTEXT ==="]
    simple_keys = ["case_id", "victim", "location", "date", "report_summary", "evidence_summary"]
    for key in simple_keys:
        val = ctx.get(key)
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    if ctx.get("risk_score"):
        rs = ctx["risk_score"]
        lines.append(
            f"Risk Score: {rs.get('overall_risk', 'N/A')} / 100  "
            f"[{rs.get('verdict', 'N/A')}]"
        )

    if ctx.get("anomalies"):
        lines.append(f"Anomalies Detected: {len(ctx['anomalies'])}")
        for a in ctx["anomalies"][:3]:          # show first 3 only to save tokens
            lines.append(f"  • [{a.get('severity','?')}] {a.get('description','')}")

    if ctx.get("contradictions"):
        lines.append(f"Contradictions Found: {len(ctx['contradictions'])}")
        for c in ctx["contradictions"][:3]:
            lines.append(f"  • [{c.get('severity','?')}] {c.get('description','')}")

    if ctx.get("leads"):
        lines.append(f"Investigative Leads: {len(ctx['leads'])}")
        for lead in ctx["leads"][:3]:
            lines.append(
                f"  • [{lead.get('priority','?')}] {lead.get('title','')} — "
                f"{lead.get('category','')}"
            )

    for k, v in ctx.get("extra", {}).items():
        lines.append(f"{k}: {v}")

    lines.append("===================")
    return "\n".join(lines)


def _build_prompt(system: str, context_block: str, history: list[dict], user_msg: str) -> str:
    """Assemble the full prompt string sent to the LLM."""
    parts = [system, "", context_block, ""]
    for turn in history[-10:]:      # keep last 10 turns to manage context length
        role_label = "Investigator" if turn["role"] == "user" else "ForensiX AI"
        parts.append(f"{role_label}: {turn['content']}")
    parts.append(f"Investigator: {user_msg}")
    parts.append("ForensiX AI:")
    return "\n".join(parts)


def _get_or_create_session(session_id: str) -> tuple[str, dict]:
    """Return (session_id, session_dict), creating a new one if needed."""
    if not session_id or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = {
            "context": {},
            "history": [],
            "created_at": datetime.utcnow().isoformat(),
        }
    return session_id, _sessions[session_id]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with the forensic AI assistant",
)
async def chat(request: ChatRequest):
    """
    Send a message to the ForensiX AI assistant with optional case context.

    - If `session_id` is empty a new session is created and returned.
    - `case_context` is merged into the session on every call; you only need
      to send it once (or when it changes).
    - Conversation history is stored server-side and automatically injected.
    """
    try:
        session_id, session = _get_or_create_session(request.session_id)

        # Merge incoming case context into session
        if request.case_context:
            session["context"].update(
                {k: v for k, v in request.case_context.model_dump().items() if v}
            )

        # Use explicit history if provided, otherwise use stored history
        history = (
            [m.model_dump() for m in request.history]
            if request.history
            else session["history"]
        )

        context_block = _build_context_block(session["context"])
        prompt = _build_prompt(SYSTEM_PROMPT, context_block, history, request.message)

        response_data = await get_llm_response(prompt)
        reply = response_data["response"]

        # Persist to session history
        session["history"].append({"role": "user", "content": request.message})
        session["history"].append({"role": "assistant", "content": reply})

        return ChatResponse(
            session_id=session_id,
            reply=reply.strip(),
            timestamp=datetime.utcnow().isoformat(),
        )

    except Exception as exc:
        logger.exception("Chat endpoint failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assistant error: {str(exc)}"
        )


@router.post(
    "/chat/stream",
    summary="Streaming chat with the forensic AI assistant (SSE)",
)
async def chat_stream(request: ChatRequest):
    """
    Streaming version of the chat endpoint using Server-Sent Events.

    The response is a text/event-stream where each chunk is prefixed with
    `data: ` and terminated with a blank line. The final event is
    `data: [DONE]`.

    Note: session history is NOT persisted for streamed responses by default.
    Call the regular /chat endpoint after streaming if you want to persist.
    """
    session_id, session = _get_or_create_session(request.session_id)

    if request.case_context:
        session["context"].update(
            {k: v for k, v in request.case_context.model_dump().items() if v}
        )

    history = (
        [m.model_dump() for m in request.history]
        if request.history
        else session["history"]
    )

    context_block = _build_context_block(session["context"])
    prompt = _build_prompt(SYSTEM_PROMPT, context_block, history, request.message)

    async def event_generator():
        try:
            async for chunk in get_llm_stream(prompt):
                yield f"data: {json.dumps({'token': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield f"data: [ERROR] {str(exc)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Session-Id": session_id,
        },
    )


@router.post(
    "/session",
    response_model=SessionResponse,
    summary="Create or update an assistant session with case context",
)
async def create_or_update_session(request: SessionCreateRequest):
    """
    Create a new session or update an existing one with fresh case context.
    Returns the session ID to use in subsequent /chat calls.
    """
    session_id, session = _get_or_create_session(request.session_id)
    session["context"].update(
        {k: v for k, v in request.case_context.model_dump().items() if v}
    )
    return SessionResponse(
        session_id=session_id,
        case_context=session["context"],
        history=session["history"],
        created_at=session["created_at"],
    )


@router.get(
    "/session/{session_id}",
    response_model=SessionResponse,
    summary="Retrieve session context and history",
)
async def get_session(session_id: str):
    """Retrieve the stored context and conversation history for a session."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )
    session = _sessions[session_id]
    return SessionResponse(
        session_id=session_id,
        case_context=session["context"],
        history=session["history"],
        created_at=session["created_at"],
    )


@router.delete(
    "/session/{session_id}",
    summary="Clear a session",
)
async def delete_session(session_id: str):
    """Delete a session and its stored history."""
    if session_id not in _sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found."
        )
    del _sessions[session_id]
    return {"status": "success", "message": f"Session '{session_id}' deleted."}
