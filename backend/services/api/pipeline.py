"""Pipeline Orchestration Logic"""
import httpx
from typing import List, Dict
import asyncio
import logging

logger = logging.getLogger("api.pipeline")


async def run_parallel_ocr(files: List, service_url: str) -> List[Dict]:
    """Run OCR on multiple files in parallel — returns structured OCR response"""

    async with httpx.AsyncClient() as client:
        tasks = []
        for file in files:
            file_bytes = await file.read()
            task = client.post(
                f"{service_url}/extract",
                files={"file": (file.filename, file_bytes, file.content_type)},
                timeout=60.0
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results = []
        for resp in responses:
            if isinstance(resp, Exception):
                logger.error(f"Parallel OCR failed: {resp}")
                results.append({
                    "error": str(resp),
                    "full_text": "",
                    "normalized_text": "",
                    "entities": {},
                    "avg_confidence": 0,
                    "evidence_blocks": [],
                    "processing_metadata": {"engine_used": "none", "fallback_triggered": False}
                })
            else:
                results.append(resp.json())

        return results


async def check_service_health(service_urls: Dict[str, str]) -> Dict[str, str]:
    """Check health of all services"""

    health = {}
    async with httpx.AsyncClient() as client:
        for name, url in service_urls.items():
            try:
                resp = await client.get(f"{url}/health", timeout=5.0)
                health[name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except:
                health[name] = "unreachable"

    return health
