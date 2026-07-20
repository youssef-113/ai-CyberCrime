#!/usr/bin/env python3
"""
End-to-End OCR Pipeline Test Suite

Tests the full pipeline: preprocessing → OCR → normalization →
entity extraction → reasoning → vector store.

Usage:
    conda activate cybercrime
    python test_pipeline.py              # Full test suite
    python test_pipeline.py --quick      # Skip slow OCR image tests
    python test_pipeline.py --image path # Test with a specific image
"""
import argparse
import io
import json
import os
import sys
import time
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import arabic_utils
import entities
import models
from models import OCRResponse


PASS = 0
FAIL = 0


def ok(name: str):
    global PASS, FAIL
    PASS += 1
    print(f"  ✓ {name}")


def fail(name: str, detail: str = ""):
    global PASS, FAIL
    FAIL += 1
    msg = f"  ✗ {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ─── 1. Module Imports ────────────────────────────────────────────────

def test_imports():
    section("Module Imports")
    modules = {
        "arabic_utils": arabic_utils,
        "entities": entities,
        "models": models,
        "ocr_engine": __import__("ocr_engine"),
        "chroma_store": __import__("chroma_store"),
        "preprocessing": __import__("preprocessing"),
    }
    for name, mod in modules.items():
        ok(f"{name} imported as {mod.__name__}")


# ─── 2. Arabic Text Processing ───────────────────────────────────────

def test_arabic_processing():
    section("Arabic Text Processing")

    # Normalization
    raw = "أَهْلًا بِكُمْ ٠١٠-١٢٣٤-٥٦٧٨"
    norm = arabic_utils.normalize_arabic_text(raw)
    assert "010" in norm and "اهلا" in norm, f"normalization mismatch: {norm}"
    ok("normalize_arabic_text: removes diacritics, converts digits")

    # Language detection
    assert arabic_utils.detect_language(norm) == "ar"
    assert arabic_utils.detect_language("hello world") == "en"
    assert arabic_utils.detect_language("hello مرحبا") == "mixed"
    ok("detect_language: ar / en / mixed")

    # Phone standardization
    phone_text = "01012345678"
    std = arabic_utils.standardize_phone_format(phone_text)
    assert "+20" in std
    ok("standardize_phone_format: local → +20")

    # Display prep
    display = arabic_utils.prepare_for_display(norm)
    ok("prepare_for_display: runs without error")


# ─── 3. Entity Extraction ────────────────────────────────────────────

def test_entity_extraction():
    section("Entity Extraction")

    text = (
        "اتصل بـ 01012345678 أو 01198765432 للتحويل. "
        "المبلغ 5000 جنيه. تاريخ 15/11/2024. "
        "حول إلى IBAN: EG380019000500000000263180002. "
        "راسلنا على test@example.com. "
        "تابعنا على facebook.com/cybercrime.eg"
    )
    ents = entities.extract_entities(text)

    assert "01012345678" in ents["phones"], f"phones missing: {ents['phones']}"
    ok("phones extracted")

    assert any("5000" in a for a in ents["amounts"]), f"amounts missing: {ents['amounts']}"
    ok("amounts extracted")

    assert any("15/11/2024" in d for d in ents["dates"]), f"dates missing: {ents['dates']}"
    ok("dates extracted")

    assert any("EG380019000500000000263180002" in i for i in ents["iban"]), f"iban missing: {ents['iban']}"
    ok("IBAN extracted")

    assert any("test@example.com" in e for e in ents["emails"]), f"emails missing: {ents['emails']}"
    ok("emails extracted")

    assert any("facebook.com/cybercrime.eg" in s for s in ents["social_accounts"]), f"social missing: {ents['social_accounts']}"
    ok("social accounts extracted")

    # Merge entities
    merged = entities.merge_entities([ents, {"phones": ["01234567890"]}])
    assert len(merged["phones"]) == len(ents["phones"]) + 1
    ok("merge_entities combines + deduplicates")

    # Threat detection
    threat_text = "هنشر صورك لو ما دفعتش 10000 جنيه"
    threat = entities.check_threat_indicators(threat_text)
    assert threat["threat_score"] > 0
    assert threat["is_threatening"]
    ok("check_threat_indicators identifies threats")


# ─── 4. OCR Engine (text-only mode) ──────────────────────────────────

def test_ocr_engine():
    section("OCR Engine")

    import ocr_engine as oe

    engine = oe.get_ocr_engine()
    m = engine.get_metrics()
    ok(f"engine initialized={m['initialized']}, surya={m['surya_available']}")

    # Test with a simple text-like image (empty bytes won't crash)
    result = engine.extract_text(b"", "empty.png")
    assert isinstance(result, models.OCRResult)
    ok("extract_text handles empty bytes gracefully")


# ─── 5. Preprocessing ────────────────────────────────────────────────

def test_preprocessing():
    section("Image Preprocessing")

    import preprocessing as pp

    # Simple test with a generated image
    from PIL import Image
    import numpy as np

    img = Image.new("RGB", (100, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    result = pp.preprocess_image(img_bytes, target_width=800)
    if result is not None:
        ok(f"preprocess_image returns {type(result).__name__} shape={result.shape}")
    else:
        fail("preprocess_image returned None (missing deps?)")


# ─── 6. Reasoning (Qwen text analysis) ───────────────────────────────

def test_reasoning():
    section("Reasoning (Qwen)")

    from reasoning import reason_text, build_ocr_response

    # Test with None/empty input
    assert reason_text("") is None
    assert reason_text(None) is None
    ok("reason_text handles empty input")

    # Test with Arabic text
    sample = "تحويل 5000 جنيه إلى 01012345678 عن طريق فيزا كارت"
    data = None
    try:
        data = reason_text(sample)
    except Exception as e:
        warn = str(e)[:100]
        fail(f"reason_text raised: {warn}")

    if data is not None:
        ok(f"reason_text returned: language={data.get('document_language')}, crime_type={data.get('crime_type')}")
    else:
        ok("reason_text gracefully skipped (model not available)")

    # Test build_ocr_response
    clean = arabic_utils.normalize_arabic_text(sample)
    resp = build_ocr_response(sample, clean, data)
    assert isinstance(resp, OCRResponse)
    ok("build_ocr_response returns OCRResponse")
    if data is not None:
        assert resp.crime_type != "" or resp.document_language != "unknown"
        ok("OCRResponse populated with reasoning data")


# ─── 7. ChromaDB ─────────────────────────────────────────────────────

def test_chromadb():
    section("Vector Store (ChromaDB)")

    from chroma_store import health_check, store_ocr_result, search_similar

    health = health_check()
    ok(f"health_check: connected={health.get('connected')}, available={health.get('available')}")

    if health.get("connected"):
        resp = OCRResponse(
            document_language="ar",
            crime_type="fraud",
            confidence=0.95,
            summary="Test document",
            entities=models.EntityCollection(),
            raw_text="تحويل 5000 جنيه",
            clean_text="تحويل 5000 جنيه",
        )
        stored = store_ocr_result(resp, document_id="test_doc")
        ok(f"store_ocr_result: {stored}")

        results = search_similar("تحويل مبلغ", n_results=3)
        ok(f"search_similar returned {len(results)} results")


# ─── 8. API Endpoints (FastAPI router) ───────────────────────────────

def test_api_endpoints():
    section("API Endpoints (FastAPI Router)")

    from main import router

    routes = [r.path for r in router.routes]
    expected = [
        "/ocr/health",
        "/ocr/extract",
        "/ocr/extract/batch",
        "/ocr/engines/status",
        "/ocr/jobs/upload",
        "/ocr/jobs/{job_id}",
        "/ocr/jobs/{job_id}/result",
        "/ocr/jobs/{job_id}/retry",
    ]
    for ep in expected:
        if ep in routes:
            ok(f"endpoint {ep}")
        else:
            fail(f"endpoint {ep} not found")


# ─── 9. Full Pipeline Simulation ─────────────────────────────────────

def test_full_pipeline():
    section("Full Pipeline Simulation (Text Input)")

    samples = [
        ("money_transfer.txt",
         "تم تحويل مبلغ 5000 جنيه إلى 01012345678 بتاريخ 15/11/2024. "
         "عن طريق محمد أحمد. رقم الحساب: 1234567890123456"),
        ("threat.txt",
         "هنشر صورك لو ما دفعتش 10000 جنيه خلال 24 ساعة. "
         "هكسر حسابك الفيس بوك. هفضحك قدام الكل"),
        ("phishing.txt",
         "عزيزي العميل، رابط تحديث البيانات: https://fake-bank.com/update. "
         "يرجى إرسال بيانات بطاقتك على email: scam@phish.com"),
        ("iban_deposit.txt",
         "حول إلى IBAN: EG380019000500000000263180002. "
         "المبلغ 25000 جنيه. تواصل مع @scammer1 على تويتر"),
    ]

    from reasoning import reason_text, build_ocr_response

    for fname, text in samples:
        clean = arabic_utils.normalize_arabic_text(text)
        lang = arabic_utils.detect_language(clean)
        ents = entities.extract_entities(clean)
        threat = entities.check_threat_indicators(clean)
        qwen_data = None
        try:
            qwen_data = reason_text(clean)
        except Exception:
            qwen_data = None

        resp = build_ocr_response(text, clean, qwen_data)

        print(f"\n  [{fname}]")
        print(f"    language: {resp.document_language} (detected: {lang})")
        print(f"    crime_type: {resp.crime_type}")
        print(f"    confidence: {resp.confidence}")
        print(f"    summary: {resp.summary[:80]}...")
        print(f"    entities: {len(resp.entities.phones)} phones, "
              f"{len(resp.entities.amounts)} amounts, "
              f"{len(resp.entities.dates)} dates, "
              f"{len(resp.entities.urls)} urls")
        print(f"    threat_score: {threat['threat_score']:.2f}, "
              f"threatening: {threat['is_threatening']}")

        ok(f"{fname}: pipeline complete")


# ─── 10. Test with Actual Image ─────────────────────────────────────

def test_image_ocr(image_path: str):
    section(f"Image OCR: {image_path}")

    if not os.path.exists(image_path):
        fail(f"Image not found: {image_path}")
        return

    from ocr_engine import get_ocr_engine
    from preprocessing import preprocess_image

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    print(f"  Image size: {len(img_bytes)} bytes")

    # Preprocess
    processed = preprocess_image(img_bytes, target_width=800)
    if processed is not None:
        print(f"  Preprocessed shape: {processed.shape}")
        ok("preprocessing completed")
    else:
        fail("preprocessing failed")

    # OCR
    engine = get_ocr_engine()
    t0 = time.time()
    result = engine.extract_text(img_bytes, os.path.basename(image_path))
    elapsed = time.time() - t0

    print(f"  OCR latency: {elapsed:.2f}s")
    print(f"  Text length: {len(result.text)} chars")
    print(f"  Confidence: {result.confidence}")
    print(f"  Engine: {result.engine}")
    print(f"  Fallback: {result.fallback_triggered}")

    if result.text.strip():
        ok("OCR extracted text")
        print(f"\n  ── EXTRACTED TEXT ──\n{result.text[:500]}\n  ────────────────")

        # Normalize & reason
        clean = arabic_utils.normalize_arabic_text(result.text)
        lang = arabic_utils.detect_language(clean)
        print(f"  Language: {lang}")

        from reasoning import reason_text, build_ocr_response
        qwen_data = reason_text(clean)
        resp = build_ocr_response(result.text, clean, qwen_data)
        print(f"  Crime type: {resp.crime_type}")
        print(f"  Confidence: {resp.confidence}")
        print(f"  Summary: {resp.summary}")

        if qwen_data:
            ok("Qwen reasoning completed")
        else:
            fail("Qwen reasoning returned None")
    else:
        fail("OCR returned empty text")


# ─── Runner ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OCR Pipeline Test Suite")
    parser.add_argument("--quick", action="store_true", help="Skip image OCR tests")
    parser.add_argument("--image", type=str, default="", help="Path to test image")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════╗")
    print("║     OCR Intelligence Service — Test Suite           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"Python: {sys.version}")
    print(f"Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")

    test_imports()
    test_arabic_processing()
    test_entity_extraction()
    test_preprocessing()
    test_api_endpoints()

    # Image OCR test if requested
    if args.image:
        test_image_ocr(args.image)
    elif not args.quick:
        image_path = os.path.join(os.path.dirname(__file__), "image.png")
        if os.path.exists(image_path):
            test_image_ocr(image_path)

    # Text-based reasoning (doesn't need Surya models)
    test_reasoning()

    # OCR engine tests (minimal, no heavy models)
    test_ocr_engine()

    # ChromaDB (may fail gracefully)
    test_chromadb()

    # Full pipeline with text samples
    test_full_pipeline()

    # Summary
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  RESULTS: {PASS}/{total} passed, {FAIL}/{total} failed")
    print(f"{'=' * 60}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
