#!/usr/bin/env python3
import sys
sys.path.insert(0, '/mnt/F/projects/ocr/ocr')
import os

print("=== OCR Intelligence Service — Model Verification ===\n")

# ── Surya OCR ──
try:
    from surya import ocr as surya_ocr
    print("✓ surya-ocr package available")
except ImportError:
    print("✗ surya-ocr not installed")

# ── PyTorch ──
try:
    import torch
    print(f"✓ PyTorch {torch.__version__} available")
    print(f"  CUDA: {torch.cuda.is_available()}")
except ImportError:
    print("✗ PyTorch not installed")

# ── Transformers / Qwen ──
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    print("✓ transformers available")
except ImportError:
    print("✗ transformers not installed")

# ── ChromaDB ──
try:
    import chromadb
    print("✓ chromadb available")
except ImportError:
    print("✗ chromadb not installed")

# ── Sentence Transformers ──
try:
    from sentence_transformers import SentenceTransformer
    print("✓ sentence-transformers available")
except ImportError:
    print("✗ sentence-transformers not installed")

# ── Arabic processing ──
try:
    import arabic_reshaper
    print("✓ arabic-reshaper available")
except ImportError:
    print("✗ arabic-reshaper not installed")

# ── OpenCV ──
try:
    import cv2
    print(f"✓ OpenCV available")
except ImportError:
    print("✗ OpenCV not installed")

print("\n=== Verification Complete ===")
print("\nTo process an image:")
print("  python -c \"from ocr_engine import get_ocr_engine; e = get_ocr_engine(); r = e.extract_text(open('image.png','rb').read(), 'image.png'); print(r.text)\"")
print("\nTo test reasoning:")
print("  python -c \"from reasoning import reason_text; print(reason_text('تحويل 5000 جنيه إلى 01012345678'))\"")
