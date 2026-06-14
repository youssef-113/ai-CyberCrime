# Base image with all Python dependencies pre-installed
FROM python:3.11-slim

WORKDIR /app

# Install all service dependencies combined
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    httpx==0.25.0 \
    python-multipart==0.0.6 \
    easyocr==1.7.0 \
    Pillow==10.1.0 \
    numpy==1.26.2 \
    chromadb==0.4.18 \
    sentence-transformers==2.2.2 \
    weasyprint==60.2 \
    jinja2==3.1.2

# System deps for OCR and PDF
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*
