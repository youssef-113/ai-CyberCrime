from datetime import datetime
from typing import List, Dict, Optional, Tuple
import re
 
 
# ─────────────────────────────────────────────
# Arabic numeral normalisation
# ─────────────────────────────────────────────
 
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
 
def _normalize_arabic_numerals(text: str) -> str:
    """Convert Eastern Arabic digits (٠-٩) to Western Arabic (0-9)."""
    return text.translate(_ARABIC_DIGITS)
 
 
# ─────────────────────────────────────────────
# Date Parsing
# ─────────────────────────────────────────────
 
_DATE_FORMATS = [
    "%Y-%m-%d",      # 2024-01-15
    "%d/%m/%Y",      # 15/01/2024
    "%d-%m-%Y",      # 15-01-2024
    "%Y/%m/%d",      # 2024/01/15
    "%d %B %Y",      # 15 January 2024
    "%d %b %Y",      # 15 Jan 2024
    "%B %d, %Y",     # January 15, 2024
    "%b %d, %Y",     # Jan 15, 2024
    "%d/%m/%y",      # 15/01/24
]
 
# Regex to extract raw date strings from free text (covers most Egyptian formats)
_DATE_PATTERN = re.compile(
    r"""
    (?:
        \d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}   # DD/MM/YYYY or DD-MM-YY
        | \d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}         # YYYY-MM-DD
        | \d{1,2}\s+\w+\s+\d{4}                   # 15 January 2024
        | [٠-٩]{1,2}[\/\-][٠-٩]{1,2}[\/\-][٠-٩]{2,4}  # Arabic numeral dates
    )
    """,
    re.VERBOSE,
)
 
 
def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """
    Parse Egyptian date formats robustly.
 
    Supports:
        - ISO:          2024-01-15
        - Day-first:    15/01/2024  |  15-01-2024
        - Arabic nums:  ١٥/٠١/٢٠٢٤
        - Verbose:      15 January 2024  |  Jan 15, 2024
    Returns None if no format matches.
    """
    normalized = _normalize_arabic_numerals(date_str.strip())
    # Replace dots used as separators (e.g. 15.01.2024)
    normalized = normalized.replace(".", "/")
 
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
 
    return None
 
 
def extract_dates_from_text(text: str) -> List[Tuple[str, Optional[datetime]]]:
    """
    Scan free text and return (raw_string, parsed_datetime) pairs.
    Pairs where parsing failed have None as the second element.
    """
    raw_dates = _DATE_PATTERN.findall(text)
    results = []
    for raw in raw_dates:
        parsed = parse_date_flexible(raw)
        results.append((raw, parsed))
    return results
 
 
# ─────────────────────────────────────────────
# Gap Analysis
# ─────────────────────────────────────────────
 
GAP_THRESHOLDS = {
    "low":    7,   # days
    "medium": 30,
    "high":   90,
}
 
 
def _gap_severity(days: int) -> str:
    if days > GAP_THRESHOLDS["high"]:
        return "critical"
    if days > GAP_THRESHOLDS["medium"]:
        return "high"
    if days > GAP_THRESHOLDS["low"]:
        return "medium"
    return "low"
 
 
def _detect_gaps(events: List[dict]) -> List[dict]:
    """
    Compare consecutive dated events and flag gaps > 7 days.
    Only compares events that both have a parsed date.
    """
    dated = [(i, e) for i, e in enumerate(events) if e.get("date")]
    gaps: List[dict] = []
 
    for idx in range(len(dated) - 1):
        pos_a, event_a = dated[idx]
        pos_b, event_b = dated[idx + 1]
 
        delta_days = (event_b["date"] - event_a["date"]).days
 
        if delta_days > GAP_THRESHOLDS["low"]:
            gaps.append(
                {
                    "between_positions": [pos_a, pos_b],
                    "between_block_ids": [event_a["block_id"], event_b["block_id"]],
                    "from_date": event_a["date"].isoformat(),
                    "to_date": event_b["date"].isoformat(),
                    "gap_days": delta_days,
                    "severity": _gap_severity(delta_days),
                    "description": (
                        f"Gap of {delta_days} days between "
                        f"'{event_a['file_name']}' and '{event_b['file_name']}'"
                    ),
                }
            )
 
    return gaps
 
 
# ─────────────────────────────────────────────
# Timeline Builder
# ─────────────────────────────────────────────
 
def _resolve_block_date(
    block: dict,
    entities: dict,
    evidence_text: str = "",
) -> Optional[datetime]:
    """
    Find the date for a block using:
    1. A date entity whose source_block matches this block's ID.
    2. Dates embedded directly in the block's normalised text.
    3. A 'date' field on the block itself.
    4. Fallback: scan evidence_text for dates near this block's content.
    """
    block_id = block.get("block_id")

    # 1. Named entity dates from the extraction layer
    for date_entity in entities.get("dates", []):
        if date_entity.get("source_block") == block_id:
            parsed = parse_date_flexible(date_entity.get("value", ""))
            if parsed:
                return parsed

    # 2. Inline text scan
    inline_dates = extract_dates_from_text(block.get("normalized_text", ""))
    for _raw, parsed in inline_dates:
        if parsed:
            return parsed

    # 3. Direct field on block
    raw_field = block.get("date") or block.get("timestamp")
    if raw_field:
        return parse_date_flexible(str(raw_field))

    # 4. Fallback: try to match date entities without source_block to this block
    #    by checking if the entity value appears in the evidence_text near block content
    if evidence_text and block.get("normalized_text"):
        snippet = block["normalized_text"][:50].lower()
        for date_entity in entities.get("dates", []):
            if date_entity.get("source_block"):  # already checked above
                continue
            date_val = date_entity.get("value", "")
            parsed = parse_date_flexible(date_val)
            if parsed and date_val in evidence_text:
                return parsed

    return None
 
 
def build_validated_timeline(
    evidence_text: str,
    entities: dict,
    evidence_blocks: List[dict],
) -> dict:
    """
    Build a validated, sorted timeline from evidence blocks with gap analysis.
 
    Args:
        evidence_text:   Raw concatenated evidence text (used for global date scanning).
        entities:        Extracted entity dict, expected to contain a 'dates' list.
        evidence_blocks: List of evidence block dicts, each with at minimum:
                         { block_id, file_name, normalized_text }.
 
    Returns:
        {
            "events":          List[dict],  # sorted chronologically
            "gaps":            List[dict],  # gaps > 7 days between consecutive events
            "has_chronology":  bool,        # True if ≥ 2 events have a confirmed date
            "undated_count":   int,
            "total_events":    int,
            "date_coverage":   float,       # fraction of events with a date (0.0–1.0)
        }
    """
    events: List[dict] = []
 
    for block in evidence_blocks:
        resolved_date = _resolve_block_date(block, entities, evidence_text)
 
        events.append(
            {
                "date": resolved_date,
                "date_raw": resolved_date.isoformat() if resolved_date else None,
                "block_id": block.get("block_id"),
                "file_name": block.get("file_name", "unknown"),
                "doc_type": block.get("doc_type", "unknown"),
                "event_summary": block.get("normalized_text", "")[:200],
                "has_date": resolved_date is not None,
                "confidence": block.get("confidence", 1.0),
            }
        )
 
    # ── Sort: dated events first (chronological), undated appended at end ──
    dated_events   = sorted([e for e in events if e["has_date"]],  key=lambda x: x["date"])
    undated_events = [e for e in events if not e["has_date"]]
    sorted_events  = dated_events + undated_events
 
    # ── Gap analysis ───────────────────────────────────────────────────────
    gaps = _detect_gaps(sorted_events)
 
    # ── Summary stats ──────────────────────────────────────────────────────
    total         = len(sorted_events)
    dated_count   = len(dated_events)
    undated_count = len(undated_events)
    coverage      = dated_count / total if total else 0.0
 
    return {
        "events":         sorted_events,
        "gaps":           gaps,
        "has_chronology": dated_count >= 2,
        "undated_count":  undated_count,
        "total_events":   total,
        "date_coverage":  round(coverage, 3),
    }
 
 
# ─────────────────────────────────────────────
# Convenience: Timeline Summary Report
# ─────────────────────────────────────────────
 
def timeline_summary(timeline: dict) -> str:
    """Return a human-readable summary string for logging / agent prompts."""
    lines = [
        f"Timeline: {timeline['total_events']} events  |  "
        f"{timeline['total_events'] - timeline['undated_count']} dated  |  "
        f"{timeline['undated_count']} undated  |  "
        f"Coverage: {timeline['date_coverage']*100:.0f}%",
        f"Chronology established: {'Yes' if timeline['has_chronology'] else 'No'}",
    ]
 
    if timeline["gaps"]:
        lines.append(f"Gaps detected ({len(timeline['gaps'])}):")
        for g in timeline["gaps"]:
            lines.append(
                f"  [{g['severity'].upper()}] {g['gap_days']} days — {g['description']}"
            )
    else:
        lines.append("No significant gaps detected.")
 
    return "\n".join(lines)