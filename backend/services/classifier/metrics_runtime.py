import time
from typing import Dict


runtime_metrics = {
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "total_latency_seconds": 0.0,
    "crime_type_counts": {},
}


def start_timer() -> float:
    return time.time()


def record_classification(
    crime_type: str,
    latency_seconds: float,
    success: bool = True,
) -> None:
    runtime_metrics["total_requests"] += 1
    runtime_metrics["total_latency_seconds"] += latency_seconds

    if success:
        runtime_metrics["successful_requests"] += 1
    else:
        runtime_metrics["failed_requests"] += 1

    crime_counts = runtime_metrics["crime_type_counts"]
    crime_counts[crime_type] = crime_counts.get(crime_type, 0) + 1


def get_runtime_metrics() -> Dict:
    total_requests = runtime_metrics["total_requests"]
    total_latency = runtime_metrics["total_latency_seconds"]

    average_latency = (
        total_latency / total_requests
        if total_requests > 0
        else 0.0
    )

    return {
        **runtime_metrics,
        "average_latency_seconds": average_latency,
    }