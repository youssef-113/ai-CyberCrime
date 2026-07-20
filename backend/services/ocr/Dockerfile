FROM python:3.11-slim

WORKDIR /app

# ── System dependencies ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    liblapack-dev \
    libopenblas-dev \
    fonts-dejavu-core \
    fonts-noto-core \
    fonts-noto-color-emoji \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Pre-download Surya OCR model ──
RUN python -c "from surya.model.recognition.model import load_model as lm; from surya.model.recognition.processor import load_processor as lp; lm(); lp()" || true

# ── Pre-download Qwen2.5-1B-Instruct ──
RUN python -c "from transformers import AutoModelForCausalLM, AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-1B-Instruct'); AutoModelForCausalLM.from_pretrained('Qwen/Qwen2.5-1B-Instruct', torch_dtype='auto', device_map='auto')" || true

# ── Pre-download sentence-transformers ──
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" || true

COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -fs http://localhost:8001/ocr/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
