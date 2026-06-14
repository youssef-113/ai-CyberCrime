FROM python:3.11-slim

WORKDIR /app

# ── System Dependencies ───────────────────────────────────────────────────────
# OCR, PDF generation, Arabic fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # PaddleOCR BLAS
    liblapack-dev \
    libopenblas-dev \
    # Arabic font rendering
    fonts-dejavu-core \
    fonts-noto-core \
    # PDF generation
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    shared-mime-info \
    # poppler for PDF processing
    poppler-utils \
    # Health check
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python Dependencies ───────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application Code ───────────────────────────────────────────────────────────
COPY . .

# ── Pre-download OCR Models (Optional - speeds up first request) ────────────────
RUN python -c "from chandra_ocr import ChandraOCR; ChandraOCR(langs=['ar','en'])" || true

# ── Expose Port ─────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Health Check ────────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -fs http://localhost:8000/health || exit 1

# ── Run Application ─────────────────────────────────────────────────────────────
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
