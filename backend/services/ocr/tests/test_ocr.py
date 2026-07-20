#!/usr/bin/env python3
"""
Simple test script for OCR engine without relative imports
"""
import sys
sys.path.insert(0, '/mnt/F/projects/ocr/ocr')

# Import modules directly
import arabic_utils
import entities
import models
import ocr_engine

def test_basic_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    print(f"arabic_utils: {arabic_utils.__name__}")
    print(f"entities: {entities.__name__}")
    print(f"models: {models.__name__}")
    print(f"ocr_engine: {ocr_engine.__name__}")
    print("All imports OK!")

def test_arabic_normalization():
    """Test Arabic text normalization"""
    print("\nTesting Arabic normalization...")
    text = "أَهْلًا بِكُمْ ٠١٠-١٢٣٤-٥٦٧٨"
    normalized = arabic_utils.normalize_arabic_text(text)
    print(f"Original: {text}")
    print(f"Normalized: {normalized}")
    lang = arabic_utils.detect_language(normalized)
    print(f"Language: {lang}")

def test_entity_extraction():
    """Test entity extraction"""
    print("\nTesting entity extraction...")
    text = "اتصل بـ 01012345678 أو 01198765432، المبلغ 5000 جنيه"
    entity_collection = entities.extract_entities(text, "E001")
    # Handle both dict and object return types
    if isinstance(entity_collection, dict):
        phones = entity_collection.get('phones', [])
        amounts = entity_collection.get('amounts', [])
        print(f"Phones: {[p.get('value', p) if isinstance(p, dict) else p for p in phones]}")
        print(f"Amounts: {[a.get('value', a) if isinstance(a, dict) else a for a in amounts]}")
    else:
        print(f"Phones: {[e.value for e in entity_collection.phones]}")
        print(f"Amounts: {[e.value for e in entity_collection.amounts]}")

if __name__ == "__main__":
    test_basic_imports()
    test_arabic_normalization()
    test_entity_extraction()
    print("\nAll tests completed!")
