"""간단한 인메모리 메트릭 엔드포인트 (재시작 시 초기화)."""
import time
from collections import defaultdict
from fastapi import APIRouter

router = APIRouter()

_request_counts: dict[str, int] = defaultdict(int)
_request_error_counts: dict[str, int] = defaultdict(int)
_request_durations_ms: dict[str, list[float]] = defaultdict(list)
_start_time = time.time()


def record_request(method: str, path: str, status: int, duration_ms: float) -> None:
    key = f"{method} {path}"
    _request_counts[key] += 1
    if status >= 500:
        _request_error_counts[key] += 1
    # Keep only last 100 durations per key to bound memory
    durations = _request_durations_ms[key]
    durations.append(duration_ms)
    if len(durations) > 100:
        durations.pop(0)


@router.get("")
async def get_metrics():
    summary = {}
    for key, count in _request_counts.items():
        durations = _request_durations_ms.get(key, [])
        avg_ms = sum(durations) / len(durations) if durations else 0
        summary[key] = {
            "count": count,
            "errors": _request_error_counts.get(key, 0),
            "avg_duration_ms": round(avg_ms, 2),
        }
    return {
        "uptime_seconds": round(time.time() - _start_time),
        "requests": summary,
    }
