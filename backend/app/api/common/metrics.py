"""Prometheus exposition format 메트릭 엔드포인트."""
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.api.deps import get_token_info

# UUID, 숫자 ID 패턴을 {id}로 치환하여 카디널리티 폭발 방지
_UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
_INT_SEGMENT_RE = re.compile(r'(?<=/)\d+(?=/|$)')


def _normalize_path(path: str) -> str:
    path = _UUID_RE.sub('{id}', path)
    path = _INT_SEGMENT_RE.sub('{id}', path)
    return path

router = APIRouter()


def _require_admin(token_info: dict = Depends(get_token_info)):
    if "admin" not in token_info.get("roles", []):
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다")

REQUEST_COUNT = Counter(
    'afterglow_http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)
REQUEST_DURATION = Histogram(
    'afterglow_http_request_duration_ms',
    'HTTP request duration in milliseconds',
    ['method', 'path'],
    buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]
)


def record_request(method: str, path: str, status: int, duration_ms: float) -> None:
    normalized = _normalize_path(path)
    REQUEST_COUNT.labels(method=method, path=normalized, status=str(status)).inc()
    REQUEST_DURATION.labels(method=method, path=normalized).observe(duration_ms)


@router.get("", dependencies=[Depends(_require_admin)])
async def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
