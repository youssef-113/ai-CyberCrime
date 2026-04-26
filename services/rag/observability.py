"""Observability - Faithfulness Metrics, Retrieval Quality Tracking

RAG systems often fail silently in production.
Retrieval quality can degrade without obvious signs.
Use metrics and set alerts when faithfulness drops.
"""
import time
import logging
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque

from config import config

logger = logging.getLogger("rag.observability")

# In-memory metrics store (for production, export to Prometheus/Grafana)
_metrics_buffer = deque(maxlen=10000)
_alert_callbacks = []


@dataclass
class RetrievalMetric:
    """Metric for a single retrieval operation."""
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

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "query": self.query[:100],
            "tenant_id": self.tenant_id,
            "strategy": self.strategy,
            "num_results": self.num_results,
            "top_score": round(self.top_score, 4),
            "avg_score": round(self.avg_score, 4),
            "cache_hit": self.cache_hit,
            "cache_source": self.cache_source,
            "latency_ms": round(self.latency_ms, 2),
            "reranker_applied": self.reranker_applied,
            "query_transformed": self.query_transformed,
        }


@dataclass
class FaithfulnessCheck:
    """Result of a faithfulness/groundedness check on generated output."""
    timestamp: float
    query: str
    answer: str
    faithfulness_score: float  # 0-1
    has_citations: bool
    num_citations: int
    hallucination_risk: str  # "low" | "medium" | "high"

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "query": self.query[:100],
            "faithfulness_score": round(self.faithfulness_score, 3),
            "has_citations": self.has_citations,
            "num_citations": self.num_citations,
            "hallucination_risk": self.hallucination_risk,
        }


def record_retrieval(metric: RetrievalMetric):
    """Record a retrieval metric."""
    if not config.observability.enabled:
        return

    _metrics_buffer.append(metric.to_dict())

    # Check for alerts
    if metric.top_score < 0.3:
        _fire_alert("low_retrieval_score", {
            "query": metric.query[:100],
            "top_score": metric.top_score,
            "tenant_id": metric.tenant_id,
        })

    if metric.latency_ms > 2000:
        _fire_alert("high_latency", {
            "query": metric.query[:100],
            "latency_ms": metric.latency_ms,
        })


def check_faithfulness(query: str, answer: str, citations: List[Dict]) -> FaithfulnessCheck:
    """Check faithfulness of generated answer against citations.

    Simple heuristic-based faithfulness check.
    For production, integrate with Ragas or TruLens.
    """
    now = time.time()
    has_citations = len(citations) > 0
    num_citations = len(citations)

    # Heuristic faithfulness score
    score = 0.0

    # Citations present
    if has_citations:
        score += 0.3
        if num_citations >= 2:
            score += 0.2

    # Answer length vs query complexity
    query_words = len(query.split())
    answer_words = len(answer.split())
    if answer_words > query_words * 2:
        score += 0.2

    # Citation coverage: check if answer references cited articles
    cited_articles = set()
    for c in citations:
        article_num = c.get("article_number", "")
        if article_num:
            cited_articles.add(article_num)

    if cited_articles:
        # Check if any article numbers appear in the answer
        for art in cited_articles:
            if str(art) in answer:
                score += 0.15
                break

    # No hallucination indicators
    hallucination_phrases = [
        "i think", "maybe", "perhaps", "i'm not sure",
        "it could be", "possibly", "might be"
    ]
    answer_lower = answer.lower()
    hallucination_count = sum(1 for p in hallucination_phrases if p in answer_lower)
    if hallucination_count == 0:
        score += 0.15

    score = min(1.0, score)

    # Risk level
    if score >= 0.7:
        risk = "low"
    elif score >= 0.4:
        risk = "medium"
    else:
        risk = "high"

    check = FaithfulnessCheck(
        timestamp=now,
        query=query,
        answer=answer[:500],
        faithfulness_score=score,
        has_citations=has_citations,
        num_citations=num_citations,
        hallucination_risk=risk,
    )

    # Alert if faithfulness drops below threshold
    if score < config.observability.faithfulness_threshold:
        _fire_alert("low_faithfulness", check.to_dict())

    return check


def register_alert_callback(callback):
    """Register a callback for alerts (e.g., send to Slack/PagerDuty)."""
    _alert_callbacks.append(callback)


def _fire_alert(alert_type: str, data: Dict):
    """Fire an alert to registered callbacks."""
    alert = {
        "alert_type": alert_type,
        "timestamp": time.time(),
        "data": data,
    }
    logger.warning(f"RAG Alert: {alert_type} - {json.dumps(data)[:200]}")
    for callback in _alert_callbacks:
        try:
            callback(alert)
        except Exception as e:
            logger.error(f"Alert callback error: {e}")


def get_metrics_summary() -> Dict[str, Any]:
    """Get summary of recent metrics."""
    if not _metrics_buffer:
        return {"total_queries": 0}

    metrics = list(_metrics_buffer)
    recent = [m for m in metrics if time.time() - m["timestamp"] < 3600]  # last hour

    if not recent:
        return {"total_queries": len(metrics), "recent_hour": 0}

    avg_latency = sum(m["latency_ms"] for m in recent) / len(recent)
    avg_score = sum(m["top_score"] for m in recent) / len(recent)
    cache_hits = sum(1 for m in recent if m.get("cache_hit"))
    cache_rate = cache_hits / len(recent) * 100 if recent else 0

    return {
        "total_queries": len(metrics),
        "recent_hour": len(recent),
        "avg_latency_ms": round(avg_latency, 2),
        "avg_top_score": round(avg_score, 4),
        "cache_hit_rate": round(cache_rate, 1),
        "cache_hits": cache_hits,
    }
