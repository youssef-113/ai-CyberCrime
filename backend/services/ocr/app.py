from fastapi import FastAPI
from main import router
import uvicorn

app = FastAPI(title="OCR Intelligence Service", version="2.0.0")
app.include_router(router)

@app.get("/")
async def root():
    return {
        "message": "OCR Intelligence Service",
        "version": "2.0.0",
        "docs": "/docs",
        "endpoints": {
            "health": "/ocr/health",
            "extract": "/ocr/extract",
            "batch": "/ocr/extract/batch",
            "engines": "/ocr/engines/status",
        },
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
