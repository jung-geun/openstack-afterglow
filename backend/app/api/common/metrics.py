"""Prometheus exposition format 메트릭 엔드포인트."""
from fastapi import APIRouter
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

router = APIRouter()

REQUEST_COUNT = Counter(
    'union_http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)
REQUEST_DURATION = Histogram(
    'union_http_request_duration_ms',
    'HTTP request duration in milliseconds',
    ['method', 'path'],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)


def record_request(method: str, path: str, status: int, duration_ms: float) -> None:
    REQUEST_COUNT.labels(method=method, path=path, status=str(status)).inc()
    REQUEST_DURATION.labels(method=method, path=path).observe(duration_ms)


@router.get("")
async def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
