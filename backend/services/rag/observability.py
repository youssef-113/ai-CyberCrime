
"""Observability - Faithfulness Metrics and Retrieval Quality Tracking.

RAG systems can fail silently in production. Retrieval quality may degrade
without obvious application errors, so metrics should be monitored and alerts
should be rate-limited.

Important:
    The faithfulness score in this module is heuristic and must not be treated
    as proof that a legal answer is factually supported. For production-grade
    evaluation, use claim-level entailment checks or frameworks such as Ragas
    or TruLens with a suitable evaluation model.
"""

import json
import logging
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import config


logger = logging.getLogger("rag.observability")


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------

# These stores are per Python process. Multiple FastAPI/Gunicorn workers will
# each have their own buffers. Export to Prometheus/OpenTelemetry in production.
_retrieval_metrics_buffer = deque(maxlen=10_000)
_faithfulness_metrics_buffer = deque(maxlen=10_000)
_alerts_buffer = deque(maxlen=2_000)

_alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []

# Protect shared state when the application uses multiple threads.
_state_lock = threading.RLock()

# alert_key -> {
#     "last_sent": float,
#     "suppressed_count": int,
# }
_alert_state: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Temporary heuristic weights
# ---------------------------------------------------------------------------

# These values are placeholders, not empirically calibrated weights.
# They should eventually be replaced with weights selected using a labelled
# evaluation dataset or with a real claim-grounding evaluator.
DEFAULT_FAITHFULNESS_WEIGHTS = {
    "has_citations": 0.30,
    "multiple_citations": 0.15,
    "citation_coverage": 0.35,
    "citation_evidence_available": 0.20,
}

DEFAULT_LOW_RETRIEVAL_SCORE_THRESHOLD = 0.30
DEFAULT_HIGH_LATENCY_THRESHOLD_MS = 2_000.0
DEFAULT_FAITHFULNESS_THRESHOLD = 0.40
DEFAULT_ALERT_COOLDOWN_SECONDS = 300.0


# ---------------------------------------------------------------------------
# Uncertainty indicators
# ---------------------------------------------------------------------------

UNCERTAINTY_PHRASES = (
    # English
    "i think",
    "maybe",
    "perhaps",
    "i'm not sure",
    "i am not sure",
    "it could be",
    "possibly",
    "might be",
    "may be",
    "appears to be",
    "seems to be",

    # Arabic
    "أعتقد",
    "اعتقد",
    "ربما",
    "لعل",
    "قد يكون",
    "قد تكون",
    "من الممكن",
    "من المحتمل",
    "يحتمل",
    "لست متأكدًا",
    "لست متأكدا",
    "غير متأكد",
    "يبدو أن",
    "يبدو ان",
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RetrievalMetric:
    """Metrics for one retrieval operation."""

    timestamp: float
    query: str
    tenant_id: str
    strategy: str
    num_results: int
    top_score: float
    avg_score: float
    cache_hit: bool = False
    cache_source: Optional[str] = None
    latency_ms: float = 0.0
    reranker_applied: bool = False
    query_transformed: bool = False
    request_id: Optional[str] = None
    score_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": float(self.timestamp),
            "query": _truncate_text(self.query, 100),
            "tenant_id": self.tenant_id or "default",
            "strategy": self.strategy or "unknown",
            "num_results": max(0, int(self.num_results)),
            "top_score": round(_safe_float(self.top_score), 4),
            "avg_score": round(_safe_float(self.avg_score), 4),
            "cache_hit": bool(self.cache_hit),
            "cache_source": self.cache_source,
            "latency_ms": round(
                max(0.0, _safe_float(self.latency_ms)),
                2,
            ),
            "reranker_applied": bool(self.reranker_applied),
            "query_transformed": bool(self.query_transformed),
            "request_id": self.request_id,
            "score_type": self.score_type,
        }


@dataclass
class FaithfulnessCheck:
    """Result of a heuristic answer-grounding check."""

    timestamp: float
    query: str
    answer: str
    faithfulness_score: Optional[float]
    has_citations: bool
    num_citations: int
    hallucination_risk: str
    tenant_id: str = "default"
    request_id: Optional[str] = None
    evaluated: bool = True
    citation_coverage: float = 0.0
    uncertainty_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        score = self.faithfulness_score

        return {
            "timestamp": float(self.timestamp),
            "query": _truncate_text(self.query, 100),
            "faithfulness_score": (
                round(score, 3)
                if score is not None
                else None
            ),
            "has_citations": bool(self.has_citations),
            "num_citations": max(0, int(self.num_citations)),
            "hallucination_risk": self.hallucination_risk,
            "tenant_id": self.tenant_id or "default",
            "request_id": self.request_id,
            "evaluated": bool(self.evaluated),
            "citation_coverage": round(
                max(0.0, min(1.0, self.citation_coverage)),
                3,
            ),
            "uncertainty_detected": bool(self.uncertainty_detected),
        }


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _observability_enabled() -> bool:
    """Return whether observability is globally enabled."""
    observability = getattr(config, "observability", None)

    return bool(
        observability
        and getattr(observability, "enabled", False)
    )


def _get_observability_setting(name: str, default: Any) -> Any:
    """Read an observability setting safely with a fallback."""
    observability = getattr(config, "observability", None)

    if observability is None:
        return default

    return getattr(observability, name, default)


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float."""
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return default

    # Avoid importing math for two simple finite checks.
    if converted != converted:  # NaN
        return default

    if converted in (float("inf"), float("-inf")):
        return default

    return converted


def _truncate_text(value: Any, limit: int) -> str:
    """Convert a value to text and truncate it safely."""
    if value is None:
        return ""

    return str(value)[:limit]


def _normalize_for_phrase_matching(text: str) -> str:
    """Normalize whitespace and case for phrase detection."""
    normalized = (text or "").casefold()
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _detect_uncertainty(answer: str) -> bool:
    """Detect Arabic or English uncertainty language."""
    normalized_answer = _normalize_for_phrase_matching(answer)

    return any(
        phrase.casefold() in normalized_answer
        for phrase in UNCERTAINTY_PHRASES
    )


def _citation_has_evidence(citation: Dict[str, Any]) -> bool:
    """Return whether a citation contains usable source evidence."""
    if not isinstance(citation, dict):
        return False

    evidence = (
        citation.get("text")
        or citation.get("content")
        or citation.get("chunk_text")
        or citation.get("parent_text")
        or citation.get("markdown")
        or ""
    )

    return bool(str(evidence).strip())


# ---------------------------------------------------------------------------
# Legal citation matching
# ---------------------------------------------------------------------------

def _normalize_article_number(article_number: Any) -> str:
    """Normalize an article number before building a regex."""
    if article_number is None:
        return ""

    normalized = str(article_number).strip()
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized


def _article_reference_patterns(article_number: str) -> Tuple[re.Pattern, ...]:
    """Build strict Arabic and English legal-reference patterns.

    Context terms such as 'Article' or 'المادة' are required. This avoids
    treating a year like 2025 as a reference to Article 25.
    """
    article_number = _normalize_article_number(article_number)

    if not article_number:
        return tuple()

    escaped_number = re.escape(article_number)

    # Allow flexible whitespace in compound references such as "25 مكرر".
    escaped_number = escaped_number.replace(r"\ ", r"\s+")

    return (
        re.compile(
            rf"""
            (?<![\w\u0600-\u06FF])
            (?:المادة|مادة)
            \s*
            (?:رقم\s*)?
            [\(\[]?
            {escaped_number}
            [\)\]]?
            (?!\d)
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
        re.compile(
            rf"""
            (?<!\w)
            Article
            \s*
            (?:No\.?\s*)?
            [\(\[]?
            {escaped_number}
            [\)\]]?
            (?!\d)
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    )


def _answer_references_article(
    answer: str,
    article_number: Any,
) -> bool:
    """Check for an explicit legal reference to an article number."""
    for pattern in _article_reference_patterns(
        _normalize_article_number(article_number)
    ):
        if pattern.search(answer or ""):
            return True

    return False


def _calculate_citation_coverage(
    answer: str,
    citations: List[Dict[str, Any]],
) -> float:
    """Calculate the share of cited article numbers explicitly referenced."""
    article_numbers: List[str] = []
    seen = set()

    for citation in citations:
        if not isinstance(citation, dict):
            continue

        article_number = _normalize_article_number(
            citation.get("article_number")
        )

        if not article_number or article_number in seen:
            continue

        seen.add(article_number)
        article_numbers.append(article_number)

    if not article_numbers:
        return 0.0

    matched_count = sum(
        1
        for article_number in article_numbers
        if _answer_references_article(answer, article_number)
    )

    return matched_count / len(article_numbers)


# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------

def record_retrieval(metric: RetrievalMetric) -> None:
    """Record one retrieval operation and evaluate alert conditions."""
    if not _observability_enabled():
        return

    metric_data = metric.to_dict()

    with _state_lock:
        _retrieval_metrics_buffer.append(metric_data)

    low_score_threshold = _safe_float(
        _get_observability_setting(
            "low_retrieval_score_threshold",
            DEFAULT_LOW_RETRIEVAL_SCORE_THRESHOLD,
        ),
        DEFAULT_LOW_RETRIEVAL_SCORE_THRESHOLD,
    )

    high_latency_threshold_ms = _safe_float(
        _get_observability_setting(
            "high_latency_threshold_ms",
            DEFAULT_HIGH_LATENCY_THRESHOLD_MS,
        ),
        DEFAULT_HIGH_LATENCY_THRESHOLD_MS,
    )

    if metric_data["num_results"] == 0:
        _fire_alert(
            "empty_retrieval",
            {
                "query": metric_data["query"],
                "tenant_id": metric_data["tenant_id"],
                "strategy": metric_data["strategy"],
                "request_id": metric_data["request_id"],
            },
        )

    elif metric_data["top_score"] < low_score_threshold:
        _fire_alert(
            "low_retrieval_score",
            {
                "query": metric_data["query"],
                "top_score": metric_data["top_score"],
                "threshold": low_score_threshold,
                "tenant_id": metric_data["tenant_id"],
                "strategy": metric_data["strategy"],
                "request_id": metric_data["request_id"],
            },
        )

    if metric_data["latency_ms"] > high_latency_threshold_ms:
        _fire_alert(
            "high_latency",
            {
                "query": metric_data["query"],
                "latency_ms": metric_data["latency_ms"],
                "threshold_ms": high_latency_threshold_ms,
                "tenant_id": metric_data["tenant_id"],
                "strategy": metric_data["strategy"],
                "request_id": metric_data["request_id"],
            },
        )


# ---------------------------------------------------------------------------
# Faithfulness heuristics
# ---------------------------------------------------------------------------

def check_faithfulness(
    query: str,
    answer: str,
    citations: List[Dict[str, Any]],
    tenant_id: str = "default",
    request_id: Optional[str] = None,
) -> FaithfulnessCheck:
    """Run a lightweight heuristic answer-grounding check.

    This function does not prove entailment between the answer and its cited
    sources. It only records citation-related quality signals.

    When observability is disabled, no evaluation, metric recording, or alert
    delivery is performed.
    """
    now = time.time()

    if not _observability_enabled():
        return FaithfulnessCheck(
            timestamp=now,
            query=query,
            answer="",
            faithfulness_score=None,
            has_citations=False,
            num_citations=0,
            hallucination_risk="not_evaluated",
            tenant_id=tenant_id or "default",
            request_id=request_id,
            evaluated=False,
            citation_coverage=0.0,
            uncertainty_detected=False,
        )

    safe_citations = [
        citation
        for citation in (citations or [])
        if isinstance(citation, dict)
    ]

    has_citations = bool(safe_citations)
    num_citations = len(safe_citations)

    citation_coverage = _calculate_citation_coverage(
        answer,
        safe_citations,
    )

    evidence_count = sum(
        1
        for citation in safe_citations
        if _citation_has_evidence(citation)
    )

    evidence_ratio = (
        evidence_count / num_citations
        if num_citations
        else 0.0
    )

    uncertainty_detected = _detect_uncertainty(answer)

    # Placeholder heuristic weights. These are not calibrated and should not
    # be interpreted as a statistically validated faithfulness probability.
    weights = DEFAULT_FAITHFULNESS_WEIGHTS

    score = 0.0

    if has_citations:
        score += weights["has_citations"]

    if num_citations >= 2:
        score += weights["multiple_citations"]

    score += (
        weights["citation_coverage"]
        * citation_coverage
    )

    score += (
        weights["citation_evidence_available"]
        * evidence_ratio
    )

    score = max(0.0, min(1.0, score))

    if score >= 0.70:
        risk = "low"
    elif score >= 0.40:
        risk = "medium"
    else:
        risk = "high"

    check = FaithfulnessCheck(
        timestamp=now,
        query=query,
        answer=_truncate_text(answer, 500),
        faithfulness_score=score,
        has_citations=has_citations,
        num_citations=num_citations,
        hallucination_risk=risk,
        tenant_id=tenant_id or "default",
        request_id=request_id,
        evaluated=True,
        citation_coverage=citation_coverage,
        uncertainty_detected=uncertainty_detected,
    )

    with _state_lock:
        _faithfulness_metrics_buffer.append(check.to_dict())

    faithfulness_threshold = _safe_float(
        _get_observability_setting(
            "faithfulness_threshold",
            DEFAULT_FAITHFULNESS_THRESHOLD,
        ),
        DEFAULT_FAITHFULNESS_THRESHOLD,
    )

    if score < faithfulness_threshold:
        alert_data = check.to_dict()
        alert_data["threshold"] = faithfulness_threshold

        _fire_alert(
            "low_faithfulness",
            alert_data,
        )

    return check


# ---------------------------------------------------------------------------
# Alert handling
# ---------------------------------------------------------------------------

def register_alert_callback(
    callback: Callable[[Dict[str, Any]], None],
) -> None:
    """Register an alert callback without adding duplicates."""
    if not callable(callback):
        raise TypeError("callback must be callable")

    with _state_lock:
        if callback not in _alert_callbacks:
            _alert_callbacks.append(callback)


def unregister_alert_callback(
    callback: Callable[[Dict[str, Any]], None],
) -> bool:
    """Remove an alert callback.

    Returns:
        True if the callback existed and was removed.
    """
    with _state_lock:
        if callback not in _alert_callbacks:
            return False

        _alert_callbacks.remove(callback)
        return True


def _build_alert_key(
    alert_type: str,
    data: Dict[str, Any],
) -> str:
    """Build an aggregation key for alert deduplication.

    Alerts are grouped by type, tenant, and strategy rather than query text,
    preventing a new alert for every individual low-quality question.
    """
    tenant_id = str(data.get("tenant_id") or "default")
    strategy = str(data.get("strategy") or "unknown")

    return f"{alert_type}:{tenant_id}:{strategy}"


def _prepare_alert_delivery(
    alert_type: str,
    data: Dict[str, Any],
) -> Tuple[bool, int]:
    """Apply alert cooldown and return suppressed-alert count."""
    cooldown_seconds = max(
        0.0,
        _safe_float(
            _get_observability_setting(
                "alert_cooldown_seconds",
                DEFAULT_ALERT_COOLDOWN_SECONDS,
            ),
            DEFAULT_ALERT_COOLDOWN_SECONDS,
        ),
    )

    alert_key = _build_alert_key(alert_type, data)
    now = time.time()

    with _state_lock:
        state = _alert_state.get(alert_key)

        if state is None:
            _alert_state[alert_key] = {
                "last_sent": now,
                "suppressed_count": 0,
            }
            return True, 0

        elapsed = now - float(state["last_sent"])

        if elapsed < cooldown_seconds:
            state["suppressed_count"] += 1
            return False, int(state["suppressed_count"])

        suppressed_count = int(state["suppressed_count"])

        state["last_sent"] = now
        state["suppressed_count"] = 0

        return True, suppressed_count


def _fire_alert(
    alert_type: str,
    data: Dict[str, Any],
) -> None:
    """Deliver a rate-limited alert to registered callbacks."""
    if not _observability_enabled():
        return

    should_deliver, suppressed_count = _prepare_alert_delivery(
        alert_type,
        data,
    )

    if not should_deliver:
        logger.debug(
            "Suppressed repeated RAG alert: type=%s count=%s",
            alert_type,
            suppressed_count,
        )
        return

    alert_data = dict(data)

    if suppressed_count:
        alert_data["suppressed_similar_alerts"] = suppressed_count

    alert = {
        "alert_type": alert_type,
        "timestamp": time.time(),
        "data": alert_data,
    }

    with _state_lock:
        _alerts_buffer.append(alert)
        callbacks = list(_alert_callbacks)

    logger.warning(
        "RAG Alert: %s - %s",
        alert_type,
        json.dumps(
            alert_data,
            ensure_ascii=False,
            default=str,
        )[:500],
    )

    # These callbacks remain synchronous. Production integrations should put
    # the alert onto a queue rather than perform slow network I/O here.
    for callback in callbacks:
        try:
            callback(alert)
        except Exception:
            logger.exception(
                "Alert callback failed for alert type %s",
                alert_type,
            )


# ---------------------------------------------------------------------------
# Summary functions
# ---------------------------------------------------------------------------

def _recent_items(
    buffer: deque,
    cutoff_timestamp: float,
) -> List[Dict[str, Any]]:
    """Read recent deque items efficiently from newest to oldest.

    Because deque records are appended chronologically, scanning can stop as
    soon as an item older than the requested window is encountered.
    """
    recent_reversed: List[Dict[str, Any]] = []

    with _state_lock:
        for item in reversed(buffer):
            if item.get("timestamp", 0.0) < cutoff_timestamp:
                break

            recent_reversed.append(item)

    recent_reversed.reverse()

    return recent_reversed


def get_metrics_summary(
    window_seconds: int = 3_600,
) -> Dict[str, Any]:
    """Return a summary of metrics within the requested time window."""
    window_seconds = max(1, int(window_seconds))
    cutoff = time.time() - window_seconds

    recent_retrieval = _recent_items(
        _retrieval_metrics_buffer,
        cutoff,
    )
    recent_faithfulness = _recent_items(
        _faithfulness_metrics_buffer,
        cutoff,
    )

    with _state_lock:
        total_retrieval = len(_retrieval_metrics_buffer)
        total_faithfulness = len(_faithfulness_metrics_buffer)
        total_alerts = len(_alerts_buffer)

    summary: Dict[str, Any] = {
        # Kept for backward compatibility.
        "total_queries": total_retrieval,
        "recent_hour": len(recent_retrieval),

        "window_seconds": window_seconds,
        "retrieval_queries_in_window": len(recent_retrieval),
        "faithfulness_checks_in_window": len(recent_faithfulness),
        "total_faithfulness_checks": total_faithfulness,
        "total_alerts_buffered": total_alerts,
    }

    if recent_retrieval:
        avg_latency = sum(
            metric["latency_ms"]
            for metric in recent_retrieval
        ) / len(recent_retrieval)

        avg_top_score = sum(
            metric["top_score"]
            for metric in recent_retrieval
        ) / len(recent_retrieval)

        cache_hits = sum(
            1
            for metric in recent_retrieval
            if metric.get("cache_hit")
        )

        empty_retrievals = sum(
            1
            for metric in recent_retrieval
            if metric.get("num_results", 0) == 0
        )

        summary.update({
            "avg_latency_ms": round(avg_latency, 2),
            "avg_top_score": round(avg_top_score, 4),
            "cache_hit_rate": round(
                cache_hits / len(recent_retrieval) * 100,
                1,
            ),
            "cache_hits": cache_hits,
            "empty_retrievals": empty_retrievals,
            "empty_retrieval_rate": round(
                empty_retrievals
                / len(recent_retrieval)
                * 100,
                1,
            ),
        })

    if recent_faithfulness:
        evaluated_checks = [
            check
            for check in recent_faithfulness
            if (
                check.get("evaluated")
                and check.get("faithfulness_score") is not None
            )
        ]

        if evaluated_checks:
            avg_faithfulness = sum(
                check["faithfulness_score"]
                for check in evaluated_checks
            ) / len(evaluated_checks)

            high_risk_count = sum(
                1
                for check in evaluated_checks
                if check.get("hallucination_risk") == "high"
            )

            no_citation_count = sum(
                1
                for check in evaluated_checks
                if not check.get("has_citations")
            )

            avg_citation_coverage = sum(
                check.get("citation_coverage", 0.0)
                for check in evaluated_checks
            ) / len(evaluated_checks)

            summary.update({
                "avg_faithfulness_score": round(
                    avg_faithfulness,
                    3,
                ),
                "high_risk_answers": high_risk_count,
                "no_citation_answers": no_citation_count,
                "avg_citation_coverage": round(
                    avg_citation_coverage,
                    3,
                ),
            })

    return summary #end

