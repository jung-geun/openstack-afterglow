import asyncio
import json
import logging
import logging.handlers
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler as _default_http_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.rate_limit import limiter

from app.api.compute import instances_router, keypairs_router, images_router, flavors_router
from app.api.storage import volumes_router, volume_backups_router, volume_snapshots_router, file_storage_router, share_snapshots_router, share_networks_router, security_services_router
from app.api.network import networks_router, routers_router, security_groups_router, loadbalancers_router
from app.api.identity import auth_router, admin_router
from app.api.identity.admin_services import router as admin_services_router
from app.api.identity.admin_flavors import router as admin_flavors_router
from app.api.identity.admin_identity import router as admin_identity_router
from app.api.identity.admin_gpu import router as admin_gpu_router
from app.api.identity.admin_notion import router as admin_notion_router
from app.api.identity.admin_images import router as admin_images_router
from app.api.identity.profile import router as profile_router
from app.api.container import clusters_router, containers_router
from app.api.k3s import k3s_clusters_router, k3s_callback_router
from app.api.common import dashboard_router, metrics_router, libraries_router, site_router, user_dashboard_router
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

_is_production = os.environ.get("UNION_ENV", "development") == "production"
app = FastAPI(
    title="Union",
    description="OpenStack VM 배포 + OverlayFS 마운트 웹 플랫폼",
    version="0.1.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(HTTPException)
async def sanitized_http_exception_handler(request: Request, exc: HTTPException):
    """5xx 에러의 내부 상세 정보를 클라이언트에 노출하지 않고 로그에만 기록."""
    if exc.status_code >= 500:
        _logger.error(
            "HTTP %d: %s %s — %s",
            exc.status_code, request.method, request.url.path, exc.detail,
        )
        return JSONResponse(status_code=exc.status_code, content={"detail": "내부 서버 오류"})
    return await _default_http_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """처리되지 않은 예외를 로그에 기록하고 500을 반환."""
    _logger.exception("Unhandled exception: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "내부 서버 오류"})

# 보안 응답 헤더: API 서버이므로 제한적 CSP 적용
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


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


_CORS_ALLOW_HEADERS = "Content-Type, X-Auth-Token, X-Project-Id, Authorization"
_CORS_ALLOW_METHODS = "GET, POST, PUT, DELETE, OPTIONS, PATCH"


def _get_allowed_origins() -> set[str]:
    from app.config import get_settings
    return set(get_settings().cors_origin_list)


@app.middleware("http")
async def cors_middleware(request: Request, call_next):
    origin = request.headers.get("origin", "")
    response = await call_next(request)
    if origin and origin in _get_allowed_origins():
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = _CORS_ALLOW_METHODS
        response.headers["Access-Control-Allow-Headers"] = _CORS_ALLOW_HEADERS
        response.headers["Vary"] = "Origin"
    return response


@app.options("/{rest_of_path:path}")
async def options_handler(request: Request, rest_of_path: str):
    """OPTIONS preflight 전용 핸들러."""
    origin = request.headers.get("origin", "")
    allowed = _get_allowed_origins()
    if origin not in allowed:
        return JSONResponse(content="Forbidden", status_code=403)
    return JSONResponse(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": _CORS_ALLOW_METHODS,
            "Access-Control-Allow-Headers": _CORS_ALLOW_HEADERS,
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        },
    )


# Identity
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(admin_services_router, prefix="/api/admin", tags=["admin-services"])
app.include_router(admin_flavors_router, prefix="/api/admin", tags=["admin-flavors"])
app.include_router(admin_identity_router, prefix="/api/admin", tags=["admin-identity"])
app.include_router(admin_gpu_router, prefix="/api/admin", tags=["admin-gpu"])
app.include_router(admin_notion_router, prefix="/api/admin", tags=["admin-notion"])
app.include_router(admin_images_router, prefix="/api/admin", tags=["admin-images"])
app.include_router(profile_router, prefix="/api/profile", tags=["profile"])
# Compute
app.include_router(images_router, prefix="/api/images", tags=["images"])
app.include_router(flavors_router, prefix="/api/flavors", tags=["flavors"])
app.include_router(instances_router, prefix="/api/instances", tags=["instances"])
app.include_router(keypairs_router, prefix="/api/keypairs", tags=["keypairs"])
# Storage (backups 먼저 등록 — /api/volumes/{id} catch-all 보다 앞에)
app.include_router(volume_backups_router, prefix="/api/volumes/backups", tags=["volume-backups"])
app.include_router(volume_snapshots_router, prefix="/api/volume-snapshots", tags=["volume-snapshots"])
app.include_router(volumes_router, prefix="/api/volumes", tags=["volumes"])
# Network
app.include_router(networks_router, prefix="/api/networks", tags=["networks"])
app.include_router(routers_router, prefix="/api/routers", tags=["routers"])
app.include_router(loadbalancers_router, prefix="/api/loadbalancers", tags=["loadbalancers"])
app.include_router(security_groups_router, prefix="/api/security-groups", tags=["security-groups"])
# Optional services — config.toml [services] 섹션에서 활성화
from app.config import get_settings as _get_cfg
_svc_cfg = _get_cfg()
if _svc_cfg.service_manila_enabled:
    app.include_router(file_storage_router, prefix="/api/file-storage", tags=["file-storage"])
    app.include_router(share_snapshots_router, prefix="/api/share-snapshots", tags=["share-snapshots"])
    app.include_router(share_networks_router, prefix="/api/share-networks", tags=["share-networks"])
    app.include_router(security_services_router, prefix="/api/security-services", tags=["security-services"])
if _svc_cfg.service_magnum_enabled:
    app.include_router(clusters_router, prefix="/api/clusters", tags=["clusters"])
if _svc_cfg.service_zun_enabled:
    app.include_router(containers_router, prefix="/api/containers", tags=["containers"])
if _svc_cfg.service_k3s_enabled:
    app.include_router(k3s_clusters_router, prefix="/api/k3s/clusters", tags=["k3s"])
    app.include_router(k3s_callback_router, prefix="/api/k3s", tags=["k3s-callback"])
# Common
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["metrics"])
app.include_router(libraries_router, prefix="/api/libraries", tags=["libraries"])
app.include_router(site_router, prefix="/api/site-config", tags=["site"])
app.include_router(user_dashboard_router, prefix="/api/user-dashboard", tags=["user-dashboard"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 시계열 스냅샷 백그라운드 워커
# ---------------------------------------------------------------------------

async def _collect_snapshot() -> None:
    """관리자 자격으로 리소스 현황을 수집하여 Redis 시계열에 저장."""
    from app.services import timeseries
    from app.config import get_settings
    from app.services import keystone

    settings = get_settings()
    try:
        import openstack
        conn = openstack.connect(
            auth_url=settings.os_auth_url,
            username=settings.os_username,
            password=settings.os_password,
            project_name=settings.os_project_name,
            user_domain_name=settings.os_user_domain_name,
            project_domain_name=settings.os_project_domain_name,
            verify=settings.ssl_verify,
        )
    except Exception:
        _logger.warning("시계열 스냅샷: OpenStack 연결 실패", exc_info=True)
        return

    try:
        # 인스턴스 상태별 집계
        def _count_instances():
            counts: dict[str, int] = {"total": 0, "active": 0, "shutoff": 0, "error": 0, "shelved": 0, "other": 0}
            for s in conn.compute.servers(all_projects=True, details=True):
                counts["total"] += 1
                st = (s.status or "").upper()
                if st == "ACTIVE":
                    counts["active"] += 1
                elif st == "SHUTOFF":
                    counts["shutoff"] += 1
                elif st == "ERROR":
                    counts["error"] += 1
                elif st in ("SHELVED", "SHELVED_OFFLOADED"):
                    counts["shelved"] += 1
                else:
                    counts["other"] += 1
            return counts

        def _count_volumes():
            counts: dict[str, int] = {"total": 0, "in_use": 0, "available": 0, "other": 0}
            for v in conn.block_storage.volumes(all_projects=True):
                counts["total"] += 1
                st = (v.status or "").lower()
                if st == "in-use":
                    counts["in_use"] += 1
                elif st == "available":
                    counts["available"] += 1
                else:
                    counts["other"] += 1
            return counts

        def _count_file_storages():
            total = 0
            try:
                from app.services import manila
                file_storages = manila.list_file_storages(conn, all_tenants=True)
                total = len(file_storages)
            except Exception:
                pass
            return {"total": total}

        def _count_networks():
            nets = sum(1 for _ in conn.network.networks())
            routers = sum(1 for _ in conn.network.routers())
            fips_total = sum(1 for _ in conn.network.ips())
            fips_used = sum(1 for f in conn.network.ips() if f.port_id)
            return {"total": nets, "routers": routers, "floating_ips_total": fips_total, "floating_ips_used": fips_used}

        inst_data = await asyncio.to_thread(_count_instances)
        vol_data = await asyncio.to_thread(_count_volumes)
        if settings.service_manila_enabled:
            file_storage_data = await asyncio.to_thread(_count_file_storages)
        else:
            file_storage_data = {"total": 0}
        net_data = await asyncio.to_thread(_count_networks)

        await timeseries.record_snapshot("instances", inst_data)
        await timeseries.record_snapshot("volumes", vol_data)
        await timeseries.record_snapshot("file_storage", file_storage_data)
        await timeseries.record_snapshot("networks", net_data)

        _logger.info("시계열 스냅샷 수집 완료: instances=%d volumes=%d file_storage=%d networks=%d",
                     inst_data["total"], vol_data["total"], file_storage_data["total"], net_data["total"])
    except Exception:
        _logger.warning("시계열 스냅샷 수집 오류", exc_info=True)
    finally:
        try:
            await asyncio.to_thread(conn.close)
        except Exception:
            pass


async def _snapshot_loop() -> None:
    """1시간 간격으로 시계열 스냅샷 수집."""
    # 시작 직후 첫 번째 수집
    await asyncio.sleep(30)
    while True:
        await _collect_snapshot()
        await asyncio.sleep(3600)


async def _notion_sync_loop() -> None:
    """Notion 연동이 활성화되어 있으면 주기적으로 동기화."""
    from app.services import notion_sync
    from app.api.identity.admin_notion import collect_instance_data, collect_hypervisor_data
    from app.api.identity.admin_gpu import get_gpu_spec_list, build_alias_to_device_name_map
    from datetime import datetime, timezone

    await asyncio.sleep(60)  # 시작 후 1분 대기
    while True:
        try:
            config = await notion_sync.get_notion_config()
            if config and config.get("enabled"):
                api_key = config["api_key"]
                users_db_id = config.get("users_database_id", "")
                hypervisors_db_id = config.get("hypervisors_database_id", "")
                gpu_spec_db_id = config.get("gpu_spec_database_id", "")

                # 0. GPU spec 동기화 (정적 데이터, 페이지 생성/갱신)
                gpu_name_to_page_id: dict[str, str] = {}
                if gpu_spec_db_id:
                    try:
                        gpu_specs = get_gpu_spec_list()
                        await notion_sync.sync_gpu_specs_to_notion(api_key, gpu_spec_db_id, gpu_specs)
                        config["gpu_spec_last_sync"] = datetime.now(timezone.utc).isoformat()
                        # 동기화 후 page_id 맵 구축 (인스턴스 relation 설정에 사용)
                        gpu_name_to_page_id = await notion_sync.fetch_gpu_spec_page_ids_by_name(api_key, gpu_spec_db_id)
                    except Exception:
                        _logger.warning("Notion GPU spec 동기화 오류", exc_info=True)

                # 1. 하이퍼바이저 데이터 수집 (GPU 정보 포함) → 동기화 → page_id 맵 구축
                host_to_page_id: dict[str, str] = {}
                hypervisors: list[dict] = []
                if hypervisors_db_id:
                    try:
                        hypervisors = await collect_hypervisor_data(gpu_name_to_page_id=gpu_name_to_page_id)
                        await notion_sync.sync_hypervisors_to_notion(api_key, hypervisors_db_id, hypervisors)
                        config["hypervisors_last_sync"] = datetime.now(timezone.utc).isoformat()
                        host_to_page_id = await notion_sync.fetch_hypervisor_page_ids_by_name(api_key, hypervisors_db_id)
                    except Exception:
                        _logger.warning("Notion 하이퍼바이저 동기화 오류", exc_info=True)

                # 2. People DB에서 이메일 → page_id 맵 구축
                email_to_page_id: dict[str, str] = {}
                if users_db_id:
                    email_to_page_id = await notion_sync.fetch_user_page_ids_by_email(api_key, users_db_id)

                # 3. 인스턴스 수집 (GPU spec relation page_id 포함)
                instances = await collect_instance_data(
                    email_to_page_id=email_to_page_id,
                    host_to_page_id=host_to_page_id,
                    gpu_name_to_page_id=gpu_name_to_page_id,
                )

                # 4. GPU 사용량 집계 (하이퍼바이저 가용량 + 인스턴스 사용량)
                alias_to_device_name = build_alias_to_device_name_map()
                usage_by_gpu: dict[str, dict] = {}

                # 4a. 하이퍼바이저별 GPU 가용량 집계
                for h in hypervisors:
                    for g in h.get("gpu_groups", []):
                        device_name = g.get("device_name", "")
                        total = g.get("total", 0)
                        if not device_name:
                            continue
                        if device_name not in usage_by_gpu:
                            usage_by_gpu[device_name] = {
                                "total_cpu_used": 0, "total_ram_used": 0,
                                "total_gpu_used": 0, "instance_count": 0,
                                "gpu_available": 0, "gpu_used": 0, "gpu_remaining": 0,
                            }
                        usage_by_gpu[device_name]["gpu_available"] += total

                # 4b. 인스턴스별 GPU 사용량 집계
                for inst in instances:
                    gpu_display = inst.get("gpu_name", "")
                    if not gpu_display or not inst.get("gpu_count"):
                        continue
                    canonical = alias_to_device_name.get(gpu_display, gpu_display)
                    if canonical not in usage_by_gpu:
                        usage_by_gpu[canonical] = {
                            "total_cpu_used": 0, "total_ram_used": 0,
                            "total_gpu_used": 0, "instance_count": 0,
                            "gpu_available": 0, "gpu_used": 0, "gpu_remaining": 0,
                        }
                    usage_by_gpu[canonical]["total_cpu_used"] += inst.get("vcpus", 0)
                    usage_by_gpu[canonical]["total_ram_used"] += inst.get("ram_gb", 0)
                    usage_by_gpu[canonical]["total_gpu_used"] += inst.get("gpu_count", 0)
                    usage_by_gpu[canonical]["instance_count"] += 1
                    usage_by_gpu[canonical]["gpu_used"] += inst.get("gpu_count", 0)

                # 4c. 남은 GPU 계산
                for u in usage_by_gpu.values():
                    u["gpu_remaining"] = u["gpu_available"] - u["gpu_used"]

                # 5. GPU spec DB 집계 데이터 업데이트
                if gpu_spec_db_id:
                    try:
                        gpu_specs = get_gpu_spec_list()
                        await notion_sync.sync_gpu_specs_to_notion(
                            api_key, gpu_spec_db_id, gpu_specs, usage_by_gpu=usage_by_gpu
                        )
                        config["gpu_spec_last_sync"] = datetime.now(timezone.utc).isoformat()
                    except Exception:
                        _logger.warning("Notion GPU spec 집계 업데이트 오류", exc_info=True)

                # 6. 인스턴스 동기화
                await notion_sync.sync_to_notion(api_key, config["database_id"], instances)
                config["last_sync"] = datetime.now(timezone.utc).isoformat()

                await notion_sync.save_notion_config(config)

                # 7. 한국어 마이그레이션 (Redis 플래그로 1회만 실행)
                try:
                    await notion_sync.migrate_instance_db_to_korean(api_key, config["database_id"])
                except Exception:
                    _logger.warning("Notion DB 한국어 마이그레이션 오류", exc_info=True)

                interval = config.get("interval_minutes", 5) * 60
            else:
                interval = 60  # 비활성 시 1분마다 설정 체크
        except Exception:
            _logger.warning("Notion 동기화 오류", exc_info=True)
            interval = 300  # 오류 시 5분 후 재시도
        await asyncio.sleep(interval)


async def _k3s_cleanup_loop() -> None:
    """5분 간격으로 stale CREATING 클러스터를 ERROR로 변경."""
    await asyncio.sleep(120)
    while True:
        try:
            from app.services import k3s_cluster as _k3s
            await _k3s.check_stale_clusters(timeout_minutes=30)
        except Exception:
            _logger.warning("k3s stale cluster check failed", exc_info=True)
        await asyncio.sleep(300)


@app.on_event("startup")
async def start_background_workers():
    asyncio.create_task(_snapshot_loop())
    asyncio.create_task(_notion_sync_loop())
    if _svc_cfg.service_k3s_enabled:
        asyncio.create_task(_k3s_cleanup_loop())
