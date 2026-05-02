FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for EasyOCR, PaddleOCR, and OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgtk-3-dev \
    libcanberra-gtk-module \
    libcanberra-gtk3-module \
    # PaddleOCR dependencies
    liblapack-dev \
    libopenblas-dev \
    # For Arabic text rendering
    fonts-dejavu-core \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for PaddleOCR
ENV FLAGS_call_stack_level=2
ENV PADDLE_DISABLE_PIR=true

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models to avoid runtime downloads
RUN python -c "import easyocr; easyocr.Reader(['ar', 'en'], gpu=False, verbose=False)" || true

COPY . .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
