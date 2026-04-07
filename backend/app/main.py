import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.compute import instances_router, keypairs_router, images_router, flavors_router
from app.api.storage import volumes_router, volume_backups_router, shares_router
from app.api.network import networks_router, routers_router, security_groups_router, loadbalancers_router
from app.api.identity import auth_router, admin_router
from app.api.container import clusters_router, containers_router
from app.api.common import dashboard_router, metrics_router, libraries_router, site_router
from app.api.common.metrics import record_request as _record_request


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
    from app.config import get_settings
    cfg = get_settings()

    formatter = _JSONFormatter()
    root = logging.getLogger()
    root.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_path = cfg.log_file_path
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        if cfg.log_rotation_type == "time":
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_path,
                when=cfg.log_rotation_when,
                interval=cfg.log_rotation_interval,
                backupCount=cfg.log_backup_count,
                encoding="utf-8",
            )
        else:
            file_handler = logging.handlers.RotatingFileHandler(
                log_path,
                maxBytes=cfg.log_max_bytes,
                backupCount=cfg.log_backup_count,
                encoding="utf-8",
            )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        pass  # 로그 디렉터리 없으면 파일 핸들러 없이 진행

    level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    root.setLevel(level)
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
    _record_request(request.method, request.url.path, response.status_code, duration_ms)
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


# Identity
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
# Compute
app.include_router(images_router, prefix="/api/images", tags=["images"])
app.include_router(flavors_router, prefix="/api/flavors", tags=["flavors"])
app.include_router(instances_router, prefix="/api/instances", tags=["instances"])
app.include_router(keypairs_router, prefix="/api/keypairs", tags=["keypairs"])
# Storage (backups 먼저 등록 — /api/volumes/{id} catch-all 보다 앞에)
app.include_router(volume_backups_router, prefix="/api/volumes/backups", tags=["volume-backups"])
app.include_router(volumes_router, prefix="/api/volumes", tags=["volumes"])
app.include_router(shares_router, prefix="/api/shares", tags=["shares"])
# Network
app.include_router(networks_router, prefix="/api/networks", tags=["networks"])
app.include_router(routers_router, prefix="/api/routers", tags=["routers"])
app.include_router(loadbalancers_router, prefix="/api/loadbalancers", tags=["loadbalancers"])
app.include_router(security_groups_router, prefix="/api/security-groups", tags=["security-groups"])
# Container
app.include_router(clusters_router, prefix="/api/clusters", tags=["clusters"])
app.include_router(containers_router, prefix="/api/containers", tags=["containers"])
# Common
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
app.include_router(libraries_router, prefix="/api/libraries", tags=["libraries"])
app.include_router(site_router, prefix="/api/site-config", tags=["site"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
