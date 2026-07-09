"""
Quick tests for strategies.py and timeline.py
Run with:  python test_my_tasks.py
No API key or Docker needed.
"""
 
import sys
import traceback
 
PASS = "PASS"
FAIL = "FAIL"
results = []
 
def check(test_name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, test_name, detail))
    icon = "✓" if condition else "✗"
    print(f"  {icon} [{status}] {test_name}" + (f" — {detail}" if detail else ""))
 
def section(title: str):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print(f"{'─'*50}")
 
 
# ─────────────────────────────────────────────
# STRATEGIES.PY TESTS
# ─────────────────────────────────────────────
 
section("strategies.py — imports")
try:
    from strategies import (
        FinancialFraudAttacker,
        BlackmailAttacker,
        ForgeryAttacker,
        HarassmentAttacker,
        GenericAttacker,
        get_strategy,
        STRATEGY_MAP,
    )
    check("Import strategies.py", True)
except Exception as e:
    check("Import strategies.py", False, str(e))
    print("\n  Cannot continue — fix the import error first.")
    sys.exit(1)
 
 
section("strategies.py — get_strategy() registry")
 
check("financial_fraud returns FinancialFraudAttacker",
      isinstance(get_strategy("financial_fraud"), FinancialFraudAttacker))
 
check("blackmail returns BlackmailAttacker",
      isinstance(get_strategy("blackmail"), BlackmailAttacker))
 
check("extortion is alias for BlackmailAttacker",
      isinstance(get_strategy("extortion"), BlackmailAttacker))
 
check("forgery returns ForgeryAttacker",
      isinstance(get_strategy("forgery"), ForgeryAttacker))
 
check("harassment returns HarassmentAttacker",
      isinstance(get_strategy("harassment"), HarassmentAttacker))
 
check("unknown type returns GenericAttacker",
      isinstance(get_strategy("something_random"), GenericAttacker))
 
check("lookup is case-insensitive",
      isinstance(get_strategy("BLACKMAIL"), BlackmailAttacker))
 
 
section("strategies.py — FinancialFraudAttacker")
 
fraud = FinancialFraudAttacker()
 
# Should challenge when nothing is present
empty_challenges = fraud.generate_challenges([], [])
check("Returns challenges on empty input",
      len(empty_challenges) > 0,
      f"got {len(empty_challenges)} challenges")
 
# Should NOT challenge when receipt keyword is present
good_block = {
    "block_id": "b1",
    "file_name": "receipt.pdf",
    "normalized_text": "bank transfer receipt transaction id 12345 amount 5000",
    "entities": {
        "amounts": [{"value": "5000"}],
        "persons": [{"value": "Ahmed Ali"}],
        "account_numbers": []
    }
}
good_claim = [{"amount": "5000"}]
good_challenges = fraud.generate_challenges(good_claim, [good_block])
check("No receipt challenge when receipt keyword present",
      not any("receipt" in c.lower() for c in good_challenges))
 
# Amount mismatch should trigger challenge
mismatch_claim = [{"amount": "9999"}]
mismatch_challenges = fraud.generate_challenges(mismatch_claim, [good_block])
check("Amount mismatch triggers challenge",
      any("amount" in c.lower() or "inconsistent" in c.lower() for c in mismatch_challenges))
 
 
section("strategies.py — BlackmailAttacker")
 
blackmail = BlackmailAttacker()
 
# All missing — should have multiple challenges
no_evidence_challenges = blackmail.generate_challenges([], [])
check("Returns multiple challenges on empty evidence",
      len(no_evidence_challenges) >= 3,
      f"got {len(no_evidence_challenges)}")
 
# Good blackmail evidence
threat_block = {
    "block_id": "b2",
    "file_name": "whatsapp_chat.pdf",
    "doc_type": "whatsapp",
    "normalized_text": "i will expose your photos unless you pay 10000 egp transfer money now سأنشر الصور",
    "entities": {}
}
threat_challenges = blackmail.generate_challenges([], [threat_block])
check("No threat challenge when threat language present",
      not any("threat" in c.lower() for c in threat_challenges))
 
check("No demand challenge when demand present",
      not any("demand" in c.lower() for c in threat_challenges))
 
check("No content challenge when content reference present",
      not any("content" in c.lower() for c in threat_challenges))
 
 
section("strategies.py — Arabic keyword detection")
 
arabic_block = {
    "block_id": "b3",
    "file_name": "chat.pdf",
    "doc_type": "message",
    "normalized_text": "سأنشر الفيديو إلا إذا حولت المبلغ",
    "entities": {}
}
arabic_challenges = blackmail.generate_challenges([], [arabic_block])
check("Arabic threat keyword detected (سأنشر)",
      not any("threat" in c.lower() for c in arabic_challenges))
check("Arabic demand keyword detected (حول)",
      not any("demand" in c.lower() for c in arabic_challenges))
 
 
section("strategies.py — GenericAttacker")
 
generic = GenericAttacker()
no_claim_challenges = generic.generate_challenges([], [])
check("Flags missing claims", any("claim" in c.lower() for c in no_claim_challenges))
check("Flags missing evidence", any("evidence" in c.lower() for c in no_claim_challenges))
 
one_block = [{"block_id": "x", "file_name": "f.pdf", "normalized_text": "some text", "entities": {}}]
single_block_challenges = generic.generate_challenges([{"amount": "100"}], one_block)
check("Flags single evidence block",
      any("one" in c.lower() or "corroborat" in c.lower() for c in single_block_challenges))
 
 
# ─────────────────────────────────────────────
# TIMELINE.PY TESTS
# ─────────────────────────────────────────────
 
section("timeline.py — imports")
try:
    from timeline import (
        parse_date_flexible,
        build_validated_timeline,
        timeline_summary,
        extract_dates_from_text,
    )
    check("Import timeline.py", True)
except Exception as e:
    check("Import timeline.py", False, str(e))
    print("\n  Cannot continue — fix the import error first.")
    sys.exit(1)
 
 
section("timeline.py — parse_date_flexible()")
 
from datetime import datetime
 
cases = [
    ("2024-01-15",  datetime(2024, 1, 15), "ISO format"),
    ("15/01/2024",  datetime(2024, 1, 15), "DD/MM/YYYY"),
    ("15-01-2024",  datetime(2024, 1, 15), "DD-MM-YYYY"),
    ("2024/01/15",  datetime(2024, 1, 15), "YYYY/MM/DD"),
    ("١٥/٠١/٢٠٢٤", datetime(2024, 1, 15), "Arabic numerals"),
    ("15 January 2024", datetime(2024, 1, 15), "Verbose English"),
    ("Jan 15, 2024",    datetime(2024, 1, 15), "Short month name"),
]
 
for date_str, expected, label in cases:
    result = parse_date_flexible(date_str)
    check(f"Parse '{label}' ({date_str})",
          result == expected,
          f"got {result}")
 
check("Returns None for garbage input",
      parse_date_flexible("not a date at all") is None)
 
check("Returns None for empty string",
      parse_date_flexible("") is None)
 
 
section("timeline.py — extract_dates_from_text()")
 
text_with_dates = "The incident happened on 15/01/2024 and the transfer was on 2024-03-20."
found = extract_dates_from_text(text_with_dates)
check("Finds multiple dates in text",
      len(found) >= 2, f"found {len(found)}")
check("All found dates are parsed",
      all(parsed is not None for _, parsed in found))
 
 
section("timeline.py — build_validated_timeline()")
 
blocks = [
    {
        "block_id": "b1", "file_name": "complaint.pdf", "doc_type": "complaint",
        "normalized_text": "Filed on 2024-01-15. Suspect transferred funds.",
        "entities": {}, "confidence": 1.0
    },
    {
        "block_id": "b2", "file_name": "receipt.pdf", "doc_type": "receipt",
        "normalized_text": "Transaction confirmed on 2024-03-01. Amount 5000 EGP.",
        "entities": {}, "confidence": 1.0
    },
    {
        "block_id": "b3", "file_name": "report.pdf", "doc_type": "report",
        "normalized_text": "No date mentioned. General report.",
        "entities": {}, "confidence": 0.8
    },
]
 
timeline = build_validated_timeline("", {}, blocks)
 
check("Returns dict with required keys",
      all(k in timeline for k in ["events", "gaps", "has_chronology", "undated_count", "total_events", "date_coverage"]))
 
check("Total events = 3",
      timeline["total_events"] == 3)
 
check("Has chronology (2+ dated events)",
      timeline["has_chronology"] is True)
 
check("Undated count = 1 (report.pdf has no date)",
      timeline["undated_count"] == 1,
      f"got {timeline['undated_count']}")
 
check("Date coverage = 0.667 (2 of 3)",
      abs(timeline["date_coverage"] - 0.667) < 0.01,
      f"got {timeline['date_coverage']}")
 
check("Events sorted chronologically (b1 before b2)",
      timeline["events"][0]["block_id"] == "b1" and
      timeline["events"][1]["block_id"] == "b2")
 
check("Undated events at end",
      timeline["events"][-1]["block_id"] == "b3")
 
 
section("timeline.py — gap detection")
 
check("Gap detected between Jan and Mar (45 days > 7 day threshold)",
      len(timeline["gaps"]) >= 1,
      f"found {len(timeline['gaps'])} gaps")
 
if timeline["gaps"]:
    gap = timeline["gaps"][0]
    check("Gap has correct severity (45 days = medium)",
          gap["severity"] in ("medium", "high"),
          f"severity={gap['severity']}, days={gap['gap_days']}")
 
 
section("timeline.py — timeline_summary()")
 
summary = timeline_summary(timeline)
check("Summary is a non-empty string", isinstance(summary, str) and len(summary) > 0)
check("Summary mentions gap", "gap" in summary.lower() or "Gap" in summary)
check("Summary mentions chronology", "chronology" in summary.lower() or "Chronology" in summary)
 
 
# ─────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────
 
total  = len(results)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = total - passed
 
print(f"\n{'═'*50}")
print(f"  RESULTS:  {passed}/{total} passed")
if failed:
    print(f"\n  FAILED TESTS:")
    for status, name, detail in results:
        if status == FAIL:
            print(f"    ✗ {name}" + (f" — {detail}" if detail else ""))
print(f"{'═'*50}\n")
 
sys.exit(0 if failed == 0 else 1)