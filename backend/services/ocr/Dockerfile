FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# OpenCV, PaddleOCR, Arabic font rendering, PDF page extraction
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    # PaddleOCR BLAS
    liblapack-dev \
    libopenblas-dev \
    # Arabic font rendering
    fonts-dejavu-core \
    fonts-noto-core \
    # poppler: needed by pdf2image for PDF → PNG conversion
    poppler-utils \
    # Health check curl
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Pre-download Chandra OCR 2 model weights ──────────────────────────────────
# (Runs at build time so first request isn't slow)
RUN python -c "from chandra_ocr import ChandraOCR; ChandraOCR(langs=['ar','en'])" || true

# ── Pre-download PaddleOCR Arabic model ──────────────────────────────────────
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(use_angle_cls=True, lang='ar', show_log=False)" || true

# ── App source ────────────────────────────────────────────────────────────────
COPY . .

EXPOSE 8001

# Liveness/readiness probe
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fs http://localhost:8001/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
