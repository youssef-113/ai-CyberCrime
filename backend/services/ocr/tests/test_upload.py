#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/F/projects/ocr/ocr')

import arabic_utils
import entities
import models
from typing import Dict, Any


def simulate_pipeline(file_name: str, raw_text: str) -> Dict[str, Any]:
    print(f"\n{'='*60}")
    print(f"Processing: {file_name}")
    print(f"{'='*60}")

    clean = arabic_utils.normalize_arabic_text(raw_text)
    lang = arabic_utils.detect_language(clean)
    ents = entities.extract_entities(clean)
    threat = entities.check_threat_indicators(clean)

    print(f"Language: {lang}")
    print(f"Clean text: {clean[:100]}...")
    print(f"Entities: phones={len(ents['phones'])} amounts={len(ents['amounts'])} dates={len(ents['dates'])}")

    return {
        "document_language": lang,
        "crime_type": "",
        "confidence": 0.0,
        "summary": "",
        "entities": ents,
        "timeline": [],
        "raw_text": raw_text,
        "clean_text": clean,
        "threat": threat,
    }


def run_tests():
    tests = [
        ("screenshot_ar.png", "اتصل بـ 01012345678 المبلغ 5000 جنيه تاريخ 15/11/2024"),
        ("mixed.png", "Contact via facebook.com/user123 or +201012345678"),
        ("threat.png", "هنشر صورك لو ما دفعتش 10000 جنيه"),
        ("iban.png", "حول إلى IBAN: EG380019000500000000263180002"),
    ]

    for name, text in tests:
        simulate_pipeline(name, text)

    print("\nAll pipeline tests completed")


if __name__ == "__main__":
    run_tests()
