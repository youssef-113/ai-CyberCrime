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


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    user_message: str
    case_context: Optional[dict] = None
    language: str = "ar"  # "ar" for Arabic, "en" for English
    history: Optional[List[dict]] = None  # Recent conversation history for context


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    citations: List[dict]
    confidence_score: Optional[float] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

logging.basicConfig(level=logging.INFO, format="%(asctime)s [CHATBOT] %(message)s")
logger = logging.getLogger("chatbot")

app = FastAPI(title="ACEB Legal Chatbot", version="1.0.0")

# ── Config ────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL         = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
MAX_HISTORY_TURNS = int(os.getenv("MAX_CHAT_HISTORY", "20"))
MAX_TOKENS        = int(os.getenv("MAX_CHAT_TOKENS", "800"))

# Ollama Config (primary LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT  = int(os.getenv("OLLAMA_TIMEOUT", "60"))

# ── Crime type labels ───────────────────────────────────────────────────────
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

CRIME_TYPE_EN = {
    "blackmail":      "Electronic Blackmail",
    "scam":           "Electronic Financial Scam",
    "threat":         "Electronic Threat",
    "defamation":     "Electronic Defamation and Libel",
    "privacy":        "Electronic Privacy Violation",
    "identity_theft": "Electronic Identity Theft",
    "general":        "Cybercrime",
    "unknown":        "Cybercrime",
}

SCORE_GRADE_AR = {
    "STRONG": "قوية",
    "MEDIUM": "متوسطة",
    "WEAK":   "ضعيفة",
}

SCORE_GRADE_EN = {
    "STRONG": "Strong",
    "MEDIUM": "Medium",
    "WEAK":   "Weak",
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

    # Build user documents from RAG
    user_docs = case_context.get("user_documents", [])
    user_docs_text = ""
    if user_docs:
        user_docs_text = "\n".join([
            f"• {doc.get('source', 'ملف')} (صلة: {int(doc.get('relevance_score', 0) * 100)}%): {doc.get('text', '')[:150]}..."
            for doc in user_docs[:5]
        ])
    else:
        user_docs_text = "لا توجد وثائق مرفوعة من المستخدم."

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

══ وثائق المستخدم المرفوعة (استخدمها للإجابة على الأسئلة) ══
{user_docs_text}

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


def build_system_prompt_en(case_context: Optional[dict]) -> str:
    """
    Build the legal chatbot system prompt with injected case context (English version).
    The prompt enforces:
    1. English-only responses
    2. Citation of actual retrieved articles (not invented ones)
    3. Compassionate tone appropriate for crime victims
    4. Referral to Cybercrime Investigation hotline 108
    """
    if not case_context:
        # Generic mode — no specific case
        return """You are a legal advisor specializing in Egyptian cybercrime cases.
Always answer in English and cite articles from the Anti-Cybercrime Law No. 175 of 2018.
Be supportive and empathetic. Refer users to the Cybercrime Investigation hotline at 108 when appropriate."""

    crime_type = case_context.get("crime_type", "unknown")
    crime_type_en = CRIME_TYPE_EN.get(crime_type, "Cybercrime")
    score_data = case_context.get("score", {})
    score_total = score_data.get("total_score", 0)
    grade = score_data.get("grade", "WEAK")
    grade_en = SCORE_GRADE_EN.get(grade, "")

    # Build claims summary
    claims = case_context.get("claims", [])
    claims_text = "\n".join(
        f"- {c.get('claim', '') if isinstance(c, dict) else c.claim}"
        for c in claims[:5]
    ) if claims else "No specific claims verified yet."

    # Build articles reference — the ONLY articles the chatbot may cite
    articles = case_context.get("articles", [])
    articles_text = ""
    if articles:
        for art in articles:
            if isinstance(art, dict):
                art_id = art.get("article_id", "")
                art_num = art.get("article_number", "")
                law = art.get("law", "")
                text_preview = (art.get("text_en", "") or art.get("text_ar", "") or "")[:200]
                penalty = art.get("penalty_en", "") or art.get("penalty_ar", "")
                articles_text += f"\n• Article {art_num} — {law} Law [{art_id}]\n  {text_preview}\n  Penalty: {penalty}\n"
    else:
        articles_text = "No legal articles have been retrieved for this case yet."

    # Build user documents from RAG
    user_docs = case_context.get("user_documents", [])
    user_docs_text = ""
    if user_docs:
        user_docs_text = "\n".join([
            f"• {doc.get('source', 'file')} (relevance: {int(doc.get('relevance_score', 0) * 100)}%): {doc.get('text', '')[:150]}..."
            for doc in user_docs[:5]
        ])
    else:
        user_docs_text = "No user uploaded documents."

    # Build entities summary for context
    entities = case_context.get("entities", {})
    phones = entities.get("phones", [])
    amounts = entities.get("amounts", [])

    prompt = f"""You are a legal advisor specializing in Egyptian cybercrime cases.
You help a cybercrime victim understand their rights and legal options.

══ Current Case Context ══
Case ID: {case_context.get("case_id", "Not specified")}
Crime Type: {crime_type_en}
Evidence Strength: {score_total}% — {grade_en}
Number of Evidence Files: {len(case_context.get("evidence_blocks", []))}

Verified Claims:
{claims_text}

{'Phone numbers detected: ' + ', '.join(phones) if phones else ''}
{'Financial amounts detected: ' + ', '.join(amounts) if amounts else ''}

══ Legal Articles You May Cite ══
{articles_text}

══ User Uploaded Documents (use to answer questions) ══
{user_docs_text}

══ Strict Rules You Must Follow ══
1. Always answer in formal English — even if the question is in informal language.
2. For every legal statement, cite using the format: "Pursuant to Article X of Law Y of Year Z..."
3. Do not cite any article not listed above.
4. If asked about an article or law not listed above, answer:
   "This question requires consultation with a lawyer specializing in cybercrime."
5. Do not invent article numbers, penalties, or prison terms not listed above.
6. Be supportive and empathetic — this person has been through a difficult experience.
7. End every answer by reminding them they can contact the Cybercrime Investigation hotline at 108.
8. Do not request additional personal information from the user."""

    return prompt


# ── LLM callers ───────────────────────────────────────────────────────────────


def call_ollama(system: str, history: List[dict], user_message: str) -> Optional[str]:
    """Call Ollama for chat generation (primary LLM)."""
    import httpx

    try:
        # Build conversation prompt from history
        prompt_parts = []
        for msg in history[-MAX_HISTORY_TURNS:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt_parts.append(f"{role}: {msg['content']}")
        prompt_parts.append(f"User: {user_message}")
        prompt_parts.append("Assistant:")
        full_prompt = "\n".join(prompt_parts)

        base_url = OLLAMA_BASE_URL.rstrip("/")
        resp = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "system": system,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": MAX_TOKENS,
                },
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as e:
        logger.error(f"Ollama error: {e}")
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


def rule_based_reply_en(user_message: str, case_context: Optional[dict]) -> str:
    """
    Rule-based fallback replies for common legal questions (English version).
    Used when no LLM API key is available.
    Pulls from the actual retrieved articles in case_context.
    """
    msg_lower = user_message.lower()

    # Get articles from context for grounded answers
    articles = (case_context or {}).get("articles", [])
    crime_type = (case_context or {}).get("crime_type", "unknown")

    # Categorize question
    is_penalty_q    = any(w in msg_lower for w in ["penalty", "punishment", "jail", "prison", "fine", "sentence"])
    is_report_q     = any(w in msg_lower for w in ["report", "file", "complaint", "police", "where", "how"])
    is_rights_q     = any(w in msg_lower for w in ["rights", "right", "can i", "allowed", "possible"])
    is_duration_q   = any(w in msg_lower for w in ["duration", "time", "long", "how long"])
    is_anon_q       = any(w in msg_lower for w in ["anonymous", "identity", "name", "know"])

    if is_report_q:
        return (
            "To report the cybercrime, you can contact the Cybercrime Investigation "
            "Department through the following methods:\n"
            "• Hotline: **108** (available 24 hours)\n"
            "• WhatsApp: **0224065052**\n"
            "• Official website: **moi.gov.eg**\n"
            "• Nearest police station with a copy of this report."
        )

    if is_penalty_q and articles:
        # Pull penalty from first article
        art = articles[0]
        if isinstance(art, dict):
            penalty = art.get("penalty_en", "") or art.get("penalty_ar", "")
            art_num = art.get("article_number", "")
            law = art.get("law", "")
            if penalty:
                return (
                    f"Pursuant to Article {art_num} of {law} Law, "
                    f"the prescribed penalty is: {penalty}. "
                    "For more details, contact the Cybercrime Investigation hotline at 108."
                )

    if is_anon_q:
        return (
            "You can file the report with your personal information, and you have the right "
            "to confidentiality before judicial authorities. For specific details about "
            "confidentiality in your case, consult the Cybercrime Investigation hotline at 108."
        )

    if is_duration_q:
        return (
            "The duration of a case varies depending on its nature and complexity. "
            "Investigations typically begin within days of filing the report. "
            "For specific information about your case, contact the Cybercrime Investigation hotline at 108."
        )

    # Generic fallback
    crime_en = CRIME_TYPE_EN.get(crime_type, "cybercrime")
    return (
        f"Your question relates to a {crime_en} case. "
        "For an accurate and reliable answer about your case, it is recommended to:\n"
        "1. Contact the Cybercrime Investigation hotline at **108**\n"
        "2. Consult a lawyer specializing in cybercrime\n"
        "3. Submit this report to the nearest police station."
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
    language: str = "ar",
    external_history: Optional[List[dict]] = None,
) -> tuple[str, List[str]]:
    """
    Main chat function.
    Returns (reply_text, cited_article_ids).

    Args:
        session_id: Unique session identifier
        user_message: User's question
        case_context: Optional case data for context
        language: "ar" for Arabic, "en" for English
        external_history: Optional history from database (last N messages)
    """
    session = get_session(session_id)

    # Use provided context or fall back to stored context
    ctx = case_context or session.get("case_context")

    # Build system prompt with case context based on language
    if language == "en":
        system = build_system_prompt_en(ctx)
        rule_based_fn = rule_based_reply_en
    else:
        system = build_system_prompt(ctx)
        rule_based_fn = rule_based_reply

    history = session["history"]
    if external_history and len(history) == 0:
        for turn in external_history:
            history.append({"role": "user", "content": turn.get("user", "")})
            history.append({"role": "assistant", "content": turn.get("assistant", "")})

    logger.info(
        f"[{session_id}] message #{session.get('message_count',0)+1} "
        f"| len={len(user_message)} | history={len(history)//2} turns | lang={language}"
    )

    # Try LLMs in order: Ollama → Claude → Gemini → rule-based
    reply = None

    reply = call_ollama(system, history, user_message)
    if reply is None and ANTHROPIC_API_KEY:
        reply = call_claude(system, history, user_message)
    if reply is None and GEMINI_API_KEY:
        reply = call_gemini(system, history, user_message)
    if reply is None:
        logger.info(f"[{session_id}] Using rule-based fallback ({language})")
        reply = rule_based_fn(user_message, ctx)

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
    llm = "ollama" if OLLAMA_BASE_URL else "claude" if ANTHROPIC_API_KEY else "gemini" if GEMINI_API_KEY else "rule-based"
    return HealthResponse(
        status="ok",
        service="chatbot",
        version=f"llm={llm} model={OLLAMA_MODEL} sessions={len(_sessions)} max_history={MAX_HISTORY_TURNS}",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Send a message to the legal chatbot.

    Input:
    {
      "session_id": "CASE_ABC123",
      "user_message": "What happens to the person who blackmails?",
      "language": "en",
      "case_context": { ...full case_data from /analyze/json... }
    }

    Output:
    {
      "reply": "Pursuant to Article 26 of Law 175 of 2018...",
      "session_id": "CASE_ABC123",
      "citations": ["law175_art26"]
    }

    Guarantees:
    - Answers in formal Arabic or English (based on language parameter)
    - Only cites articles from retrieved law list (no invented articles)
    - Maintains full conversation history within session
    - Compassionate tone for crime victims
    - Always references 108 hotline
    """
    if not request.user_message or not request.user_message.strip():
        raise HTTPException(400, detail="user_message cannot be empty")

    if len(request.user_message) > 2000:
        raise HTTPException(400, detail="user_message too long (max 2000 chars)")

    if request.language not in ["ar", "en"]:
        raise HTTPException(400, detail="language must be 'ar' or 'en'")

    t0 = time.time()
    reply, citations = chat(
        session_id=request.session_id,
        user_message=request.user_message,
        case_context=request.case_context,
        language=request.language,
        external_history=request.history,
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
