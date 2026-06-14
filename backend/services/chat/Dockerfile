FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8006
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8006/health || exit 1
ENV MAX_CHAT_HISTORY=20
ENV MAX_CHAT_TOKENS=800
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8006"]
