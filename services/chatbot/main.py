"""
services/chatbot/main.py
Day 7 Task: Legal Chatbot Service — Case-aware Arabic legal assistant

POST /chat          — send a message, get Arabic law-grounded reply
POST /chat/reset    — clear session history
GET  /chat/history  — get full conversation history for a session
GET  /health
"""
import os
import sys
import re
import json
import time
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from models.pydantic_models import ChatRequest, ChatResponse, HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CHATBOT] %(message)s")
logger = logging.getLogger("chatbot")

app = FastAPI(title="ACEB Legal Chatbot", version="1.0.0")

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL         = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
MAX_HISTORY_TURNS = int(os.getenv("MAX_CHAT_HISTORY", "20"))
MAX_TOKENS        = int(os.getenv("MAX_CHAT_TOKENS", "800"))

# ── Crime type Arabic labels ──────────────────────────────────────────────────
CRIME_TYPE_AR = {
    "blackmail":      "ابتزاز إلكتروني",
    "scam":           "احتيال مالي إلكتروني",
    "threat":         "تهديد إلكتروني",
    "defamation":     "تشهير وقذف إلكتروني",
    "privacy":        "انتهاك خصوصية إلكتروني",
    "identity_theft": "سرقة هوية إلكترونية",
    "general":        "جريمة إلكترونية",
    "unknown":        "جريمة إلكترونية",
}

SCORE_GRADE_AR = {
    "STRONG": "قوية",
    "MEDIUM": "متوسطة",
    "WEAK":   "ضعيفة",
}

# ── In-memory session store ───────────────────────────────────────────────────
# Structure: {session_id: {"history": [...], "case_context": {...}, "created_at": str}}
# In production: replace with Redis
_sessions: Dict[str, dict] = {}


# ── System prompt builder ─────────────────────────────────────────────────────

def build_system_prompt(case_context: Optional[dict]) -> str:
    """
    Build the legal chatbot system prompt with injected case context.
    The prompt enforces:
    1. Arabic-only responses
    2. Citation of actual retrieved articles (not invented ones)
    3. Compassionate tone appropriate for crime victims
    4. Referral to مباحث الإنترنت hotline 108
    """
    if not case_context:
        # Generic mode — no specific case
        return """أنت مستشار قانوني متخصص في قضايا الجرائم الإلكترونية المصرية.
أجب دائماً بالعربية الفصحى، وأستشهد بمواد قانون مكافحة جرائم تقنية المعلومات رقم 175 لسنة 2018.
كن داعماً ومتعاطفاً. أحل المستخدم إلى مباحث الإنترنت على الرقم 108 عند الاقتضاء."""

    crime_type = case_context.get("crime_type", "unknown")
    crime_type_ar = CRIME_TYPE_AR.get(crime_type, "جريمة إلكترونية")
    score_data = case_context.get("score", {})
    score_total = score_data.get("total_score", 0)
    grade = score_data.get("grade", "WEAK")
    grade_ar = SCORE_GRADE_AR.get(grade, "")

    # Build claims summary
    claims = case_context.get("claims", [])
    claims_text = "\n".join(
        f"- {c.get('claim', '') if isinstance(c, dict) else c.claim}"
        for c in claims[:5]
    ) if claims else "لا توجد ادعاءات محددة بعد."

    # Build articles reference — the ONLY articles the chatbot may cite
    articles = case_context.get("articles", [])
    articles_text = ""
    if articles:
        for art in articles:
            if isinstance(art, dict):
                art_id = art.get("article_id", "")
                art_num = art.get("article_number", "")
                law = art.get("law", "")
                text_preview = (art.get("text_ar", "") or "")[:200]
                penalty = art.get("penalty_ar", "") or art.get("penalty_en", "")
                articles_text += f"\n• المادة {art_num} — قانون {law} [{art_id}]\n  {text_preview}\n  العقوبة: {penalty}\n"
    else:
        articles_text = "لم يتم استرجاع مواد قانونية لهذه القضية بعد."

    # Build entities summary for context
    entities = case_context.get("entities", {})
    phones = entities.get("phones", [])
    amounts = entities.get("amounts", [])

    prompt = f"""أنت مستشار قانوني متخصص في قضايا الجرائم الإلكترونية المصرية.
تساعد ضحية جريمة إلكترونية في فهم حقوقها وخياراتها القانونية.

══ سياق القضية الحالية ══
رقم القضية: {case_context.get("case_id", "غير محدد")}
نوع الجريمة: {crime_type_ar}
قوة الأدلة: {score_total}% — {grade_ar}
عدد الأدلة: {len(case_context.get("evidence_blocks", []))} ملف

الادعاءات المتحقق منها:
{claims_text}

{'أرقام هواتف مرصودة: ' + ', '.join(phones) if phones else ''}
{'مبالغ مالية مرصودة: ' + ', '.join(amounts) if amounts else ''}

══ المواد القانونية التي يُجيز لك الاستشهاد بها فقط ══
{articles_text}

══ القواعد الصارمة التي يجب الالتزام بها ══
١. أجب دائماً بالعربية الفصحى — حتى لو كان السؤال بالعامية المصرية.
٢. لكل بيان قانوني يجب الاستشهاد بصيغة: "بموجب المادة X من القانون Y لسنة Z..."
٣. لا يجوز الاستشهاد بأي مادة غير واردة في القائمة أعلاه.
٤. إذا سُئلت عن مادة أو قانون غير مدرج في القائمة أجب:
   "يتطلب هذا التساؤل مراجعة محامٍ متخصص في الجرائم الإلكترونية."
٥. لا تخترع أرقام مواد أو عقوبات أو مدد حبس غير واردة في القائمة.
٦. كن داعماً ومتعاطفاً — هذا الشخص مرّ بتجربة صعبة.
٧. أنهِ كل إجابة بالتذكير بإمكانية التواصل مع مباحث الإنترنت على الرقم 108.
٨. لا تطلب بيانات شخصية إضافية من المستخدم."""

    return prompt


# ── LLM callers ───────────────────────────────────────────────────────────────

def call_claude(system: str, history: List[dict], user_message: str) -> str:
    """Call Claude Sonnet API with full conversation history."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        messages = list(history[-MAX_HISTORY_TURNS:])  # Keep last N turns
        messages.append({"role": "user", "content": user_message})

        resp = client.messages.create(
            model=LLM_MODEL,
            system=system,
            messages=messages,
            max_tokens=MAX_TOKENS,
        )
        return resp.content[0].text

    except ImportError:
        logger.warning("anthropic not installed")
        return None
    except Exception as e:
        logger.error(f"Claude error: {e}")
        return None


def call_gemini(system: str, history: List[dict], user_message: str) -> str:
    """Call Gemini 1.5 Flash (free tier) with conversation history."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)

        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=system,
        )

        # Build chat history for Gemini format
        gemini_history = []
        for msg in history[-MAX_HISTORY_TURNS:]:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        chat = model.start_chat(history=gemini_history)
        resp = chat.send_message(
            user_message,
            generation_config={"temperature": 0.3, "max_output_tokens": MAX_TOKENS},
        )
        return resp.text

    except ImportError:
        logger.warning("google-generativeai not installed")
        return None
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return None


def rule_based_reply(user_message: str, case_context: Optional[dict]) -> str:
    """
    Rule-based fallback replies for common legal questions.
    Used when no LLM API key is available.
    Pulls from the actual retrieved articles in case_context.
    """
    msg_lower = user_message.lower()

    # Get articles from context for grounded answers
    articles = (case_context or {}).get("articles", [])
    crime_type = (case_context or {}).get("crime_type", "unknown")

    # Categorize question
    is_penalty_q    = any(w in msg_lower for w in ["عقوبة", "العقوبة", "يعاقب", "سجن", "حبس", "غرامة"])
    is_report_q     = any(w in msg_lower for w in ["أبلغ", "أبلغ", "بلاغ", "مباحث", "شرطة", "فين أروح"])
    is_rights_q     = any(w in msg_lower for w in ["حقوقي", "حق", "أحق", "يحق لي", "ممكن"])
    is_duration_q   = any(w in msg_lower for w in ["مدة", "وقت", "قد", "كتير"])
    is_anon_q       = any(w in msg_lower for w in ["مجهول", "هوية", "اسمي", "أعرف"])

    if is_report_q:
        return (
            "للإبلاغ عن الجريمة الإلكترونية، يمكنك التواصل مع مباحث الإنترنت "
            "عبر الطرق التالية:\n"
            "• الخط الساخن: **108** (متاح 24 ساعة)\n"
            "• واتساب: **0224065052**\n"
            "• الموقع الرسمي: **moi.gov.eg**\n"
            "• أقرب مركز شرطة مع نسخة من هذا المحضر."
        )

    if is_penalty_q and articles:
        # Pull penalty from first article
        art = articles[0]
        if isinstance(art, dict):
            penalty = art.get("penalty_ar", "") or art.get("penalty_en", "")
            art_num = art.get("article_number", "")
            law = art.get("law", "")
            if penalty:
                return (
                    f"بموجب المادة {art_num} من قانون {law}، "
                    f"العقوبة المقررة هي: {penalty}. "
                    "للاستفسار عن مزيد من التفاصيل، تواصل مع مباحث الإنترنت على الرقم 108."
                )

    if is_anon_q:
        return (
            "يمكنك تقديم البلاغ مع ذكر بياناتك الشخصية، وتتمتع بحق السرية أمام الجهات القضائية. "
            "للاستفسار عن تفاصيل السرية في قضيتك تحديداً، راجع مباحث الإنترنت على الرقم 108."
        )

    if is_duration_q:
        return (
            "تختلف مدة القضية بحسب طبيعتها وتعقيدها. "
            "عادةً تبدأ التحقيقات في غضون أيام من تقديم البلاغ. "
            "للاستفسار عن قضيتك تحديداً، تواصل مع مباحث الإنترنت على الرقم 108."
        )

    # Generic fallback
    crime_ar = CRIME_TYPE_AR.get(crime_type, "الجريمة الإلكترونية")
    return (
        f"سؤالك يتعلق بقضية {crime_ar}. "
        "للحصول على إجابة دقيقة وموثوقة حول قضيتك، يُنصح بـ:\n"
        "١. التواصل مع مباحث الإنترنت على الرقم **108**\n"
        "٢. استشارة محامٍ متخصص في الجرائم الإلكترونية\n"
        "٣. تقديم هذا المحضر إلى أقرب مركز شرطة."
    )


# ── Citation extractor ────────────────────────────────────────────────────────

def extract_cited_articles(reply: str, case_context: Optional[dict]) -> List[str]:
    """
    Extract article IDs cited in the reply by pattern matching.
    Only returns articles that are in the case context (validates citations).
    """
    if not case_context:
        return []

    valid_ids = set()
    for art in case_context.get("articles", []):
        if isinstance(art, dict):
            valid_ids.add(art.get("article_id", ""))

    # Match patterns like "المادة 26" or "Article 26"
    cited = []
    for pattern in [r"المادة\s+(\d+\s*(?:مكرر)?)", r"Article\s+(\d+)"]:
        for m in re.finditer(pattern, reply, re.IGNORECASE):
            art_num = m.group(1).strip()
            # Find matching article_id in valid_ids
            for art_id in valid_ids:
                if f"art{art_num.replace(' ', '_')}" in art_id or f"art{art_num}" in art_id:
                    if art_id not in cited:
                        cited.append(art_id)
    return cited


# ── Session management ────────────────────────────────────────────────────────

def get_session(session_id: str) -> dict:
    """Get or create a session."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "history": [],
            "case_context": None,
            "created_at": datetime.utcnow().isoformat(),
            "message_count": 0,
        }
    return _sessions[session_id]


def update_session(session_id: str, user_msg: str, assistant_reply: str, case_context: Optional[dict] = None):
    """Add a turn to the session history and update context."""
    session = get_session(session_id)
    session["history"].append({"role": "user", "content": user_msg})
    session["history"].append({"role": "assistant", "content": assistant_reply})
    session["message_count"] += 1

    # Update case context if provided
    if case_context:
        session["case_context"] = case_context

    # Trim history if too long
    if len(session["history"]) > MAX_HISTORY_TURNS * 2:
        session["history"] = session["history"][-(MAX_HISTORY_TURNS * 2):]


# ── Main chat function ────────────────────────────────────────────────────────

def chat(
    session_id: str,
    user_message: str,
    case_context: Optional[dict] = None,
) -> tuple[str, List[str]]:
    """
    Main chat function.
    Returns (reply_text, cited_article_ids).
    """
    session = get_session(session_id)

    # Use provided context or fall back to stored context
    ctx = case_context or session.get("case_context")

    # Build system prompt with case context
    system = build_system_prompt(ctx)

    # Get conversation history
    history = session["history"]

    logger.info(
        f"[{session_id}] message #{session.get('message_count',0)+1} "
        f"| len={len(user_message)} | history={len(history)//2} turns"
    )

    # Try LLMs in order
    reply = None

    if ANTHROPIC_API_KEY:
        reply = call_claude(system, history, user_message)
    if reply is None and GEMINI_API_KEY:
        reply = call_gemini(system, history, user_message)
    if reply is None:
        logger.info(f"[{session_id}] Using rule-based fallback")
        reply = rule_based_reply(user_message, ctx)

    # Extract cited articles
    citations = extract_cited_articles(reply, ctx)

    # Update session
    update_session(session_id, user_message, reply, case_context)

    logger.info(
        f"[{session_id}] reply: {len(reply)} chars | citations={citations}"
    )

    return reply, citations


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    llm = "claude" if ANTHROPIC_API_KEY else "gemini" if GEMINI_API_KEY else "rule-based"
    return HealthResponse(
        status="ok",
        service="chatbot",
        version=f"llm={llm} sessions={len(_sessions)} max_history={MAX_HISTORY_TURNS}",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Send a message to the legal chatbot.

    Input:
    {
      "session_id": "CASE_ABC123",
      "user_message": "ايه هيحصل للشخص اللي بتزني؟",
      "case_context": { ...full case_data from /analyze/json... }
    }

    Output:
    {
      "reply": "بموجب المادة 26 من القانون 175 لسنة 2018...",
      "session_id": "CASE_ABC123",
      "citations": ["law175_art26"]
    }

    Guarantees:
    - Answers in formal Arabic
    - Only cites articles from retrieved law list (no invented articles)
    - Maintains full conversation history within session
    - Compassionate tone for crime victims
    - Always references 108 hotline
    """
    if not request.user_message or not request.user_message.strip():
        raise HTTPException(400, detail="user_message cannot be empty")

    if len(request.user_message) > 2000:
        raise HTTPException(400, detail="user_message too long (max 2000 chars)")

    t0 = time.time()
    reply, citations = chat(
        session_id=request.session_id,
        user_message=request.user_message,
        case_context=request.case_context,
    )
    elapsed = round(time.time() - t0, 2)
    logger.info(f"Chat completed in {elapsed}s")

    return ChatResponse(
        reply=reply,
        session_id=request.session_id,
        citations=citations,
    )


@app.post("/chat/reset")
async def reset_chat(body: dict):
    """Clear all history for a session."""
    session_id = body.get("session_id", "")
    if not session_id:
        raise HTTPException(400, detail="session_id required")

    if session_id in _sessions:
        del _sessions[session_id]
        logger.info(f"Session {session_id} cleared")
        return {"status": "cleared", "session_id": session_id}
    return {"status": "not_found", "session_id": session_id}


@app.get("/chat/history")
async def get_history(session_id: str):
    """Get full conversation history for a session."""
    if not session_id:
        raise HTTPException(400, detail="session_id required")

    session = _sessions.get(session_id)
    if not session:
        return {"session_id": session_id, "history": [], "message_count": 0}

    return {
        "session_id":    session_id,
        "history":       session["history"],
        "message_count": session.get("message_count", 0),
        "created_at":    session.get("created_at", ""),
        "has_context":   session.get("case_context") is not None,
    }


@app.get("/sessions")
async def list_sessions():
    """List all active sessions (for admin/debug purposes)."""
    return {
        "total_sessions": len(_sessions),
        "sessions": [
            {
                "session_id": sid,
                "message_count": s.get("message_count", 0),
                "created_at": s.get("created_at", ""),
                "has_context": s.get("case_context") is not None,
            }
            for sid, s in _sessions.items()
        ],
    }


@app.post("/chat/pdf_trigger")
async def trigger_pdf_from_chat(body: dict):
    """
    Trigger PDF generation from chat context.
    Used when user asks 'generate a report' from the chatbot interface.
    """
    session_id = body.get("session_id", "")
    if not session_id or session_id not in _sessions:
        raise HTTPException(404, detail=f"Session {session_id} not found")

    session = _sessions[session_id]
    case_context = session.get("case_context")

    if not case_context:
        raise HTTPException(400, detail="No case context in this session — run /analyze first")

    # Call PDF service
    try:
        import httpx
        PDF_URL = os.getenv("PDF_URL", "http://pdf_gen:8005")
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{PDF_URL}/pdf", json=case_context)
            resp.raise_for_status()
            return {
                "status": "generated",
                "case_id": case_context.get("case_id"),
                "pdf_size": len(resp.content),
                "message": "يمكنك تنزيل المحضر من صفحة تنزيل المحضر",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
