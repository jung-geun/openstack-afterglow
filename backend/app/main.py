import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, images, flavors, libraries, instances, admin, volumes, volume_backups, shares, networks, keypairs, dashboard, routers as routers_api, loadbalancers, security_groups, metrics


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------
_STANDARD_LOG_KEYS = set(logging.LogRecord('', 0, '', 0, '', (), None).__dict__)


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in _STANDARD_LOG_KEYS and k != "message":
                entry[k] = v
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False, default=str)


def _setup_logging() -> None:
    formatter = _JSONFormatter()
    root = logging.getLogger()
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_path = "/app/logs/union-backend.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=50 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass  # 로그 디렉터리 없으면 파일 핸들러 없이 진행

    root.setLevel(logging.INFO)
    logging.getLogger("openstack").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("keystoneauth1").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


_setup_logging()
_logger = logging.getLogger(__name__)


app = FastAPI(
    title="Union",
    description="OpenStack VM 배포 + OverlayFS 마운트 웹 플랫폼",
    version="0.1.0",
)

# CORS: credentials 사용 시 allow_origins=["*"] 는 브라우저가 거부하므로
# 요청 Origin을 동적으로 허용 (개발 환경)
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    metrics.record_request(request.method, request.url.path, response.status_code, duration_ms)
    if not request.url.path.startswith("/api/health"):
        _logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
    return response


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    response = await call_next(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Auth-Token, X-Project-Id, Authorization"
        response.headers["Vary"] = "Origin"
    return response


@app.options("/{rest_of_path:path}")
async def options_handler(request: Request, rest_of_path: str):
    """OPTIONS preflight 전용 핸들러."""
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, X-Auth-Token, X-Project-Id, Authorization",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        },
    )


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(images.router, prefix="/api/images", tags=["images"])
app.include_router(flavors.router, prefix="/api/flavors", tags=["flavors"])
app.include_router(libraries.router, prefix="/api/libraries", tags=["libraries"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(volumes.router, prefix="/api/volumes", tags=["volumes"])
app.include_router(volume_backups.router, prefix="/api/volumes/backups", tags=["volume-backups"])
app.include_router(shares.router, prefix="/api/shares", tags=["shares"])
app.include_router(networks.router, prefix="/api/networks", tags=["networks"])
app.include_router(keypairs.router, prefix="/api/keypairs", tags=["keypairs"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(routers_api.router, prefix="/api/routers", tags=["routers"])
app.include_router(loadbalancers.router, prefix="/api/loadbalancers", tags=["loadbalancers"])
app.include_router(security_groups.router, prefix="/api/security-groups", tags=["security-groups"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
