"""Pipeline Orchestration Logic"""
import httpx
from typing import List, Dict
import asyncio

async def run_parallel_ocr(files: List, service_url: str) -> List[Dict]:
    """Run OCR on multiple files in parallel"""
    
    async with httpx.AsyncClient() as client:
        tasks = []
        for file in files:
            task = client.post(
                f"{service_url}/extract",
                files={"file": (file.filename, await file.read(), file.content_type)},
                timeout=60.0
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        results = []
        for resp in responses:
            if isinstance(resp, Exception):
                results.append({"error": str(resp), "text": "", "entities": {}})
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
