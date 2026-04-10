"""관리자 Notion 연동 설정 엔드포인트."""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_os_conn, require_admin
from app.services import notion_sync

_logger = logging.getLogger(__name__)

router = APIRouter()


class NotionConfigRequest(BaseModel):
    api_key: str
    database_id: str
    enabled: bool = True
    interval_minutes: int = 5
    users_database_id: str = ""
    hypervisors_database_id: str = ""


@router.get("/notion/config", dependencies=[Depends(require_admin)])
async def get_notion_config():
    """현재 Notion 연동 설정 조회."""
    config = await notion_sync.get_notion_config()
    if not config:
        return {"configured": False}
    return {
        "configured": True,
        "api_key_masked": notion_sync.mask_api_key(config.get("api_key", "")),
        "database_id": config.get("database_id", ""),
        "enabled": config.get("enabled", False),
        "interval_minutes": config.get("interval_minutes", 5),
        "last_sync": config.get("last_sync"),
        "users_database_id": config.get("users_database_id", ""),
        "hypervisors_database_id": config.get("hypervisors_database_id", ""),
        "hypervisors_last_sync": config.get("hypervisors_last_sync"),
    }


@router.post("/notion/config", dependencies=[Depends(require_admin)])
async def save_notion_config(req: NotionConfigRequest):
    """Notion 연동 설정 저장. 연결 검증 + DB 속성 자동 생성."""
    if req.interval_minutes < 1 or req.interval_minutes > 1440:
        raise HTTPException(status_code=400, detail="동기화 간격은 1~1440분 사이여야 합니다")

    ok, message = await notion_sync.validate_notion_config(req.api_key, req.database_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    try:
        await notion_sync.ensure_db_properties(req.api_key, req.database_id)
    except Exception as e:
        _logger.warning("Notion DB 속성 생성 실패: %s", e)
        raise HTTPException(status_code=400, detail=f"DB 속성 생성 실패: {e}")

    # 선택 DB 검증
    if req.users_database_id:
        ok_u, msg_u = await notion_sync.validate_notion_config(req.api_key, req.users_database_id)
        if not ok_u:
            raise HTTPException(status_code=400, detail=f"사용자 DB 오류: {msg_u}")

    if req.hypervisors_database_id:
        ok_h, msg_h = await notion_sync.validate_notion_config(req.api_key, req.hypervisors_database_id)
        if not ok_h:
            raise HTTPException(status_code=400, detail=f"하이퍼바이저 DB 오류: {msg_h}")
        try:
            await notion_sync.ensure_hypervisor_db_properties(req.api_key, req.hypervisors_database_id)
        except Exception as e:
            _logger.warning("Notion 하이퍼바이저 DB 속성 생성 실패: %s", e)
            raise HTTPException(status_code=400, detail=f"하이퍼바이저 DB 속성 생성 실패: {e}")

    existing = await notion_sync.get_notion_config()
    last_sync = existing.get("last_sync") if existing else None
    hypervisors_last_sync = existing.get("hypervisors_last_sync") if existing else None

    await notion_sync.save_notion_config({
        "api_key": req.api_key,
        "database_id": req.database_id,
        "enabled": req.enabled,
        "interval_minutes": req.interval_minutes,
        "last_sync": last_sync,
        "users_database_id": req.users_database_id,
        "hypervisors_database_id": req.hypervisors_database_id,
        "hypervisors_last_sync": hypervisors_last_sync,
    })

    return {
        "status": "ok",
        "message": "설정이 저장되었습니다",
        "api_key_masked": notion_sync.mask_api_key(req.api_key),
    }


@router.delete("/notion/config", dependencies=[Depends(require_admin)])
async def delete_notion_config():
    """Notion 연동 설정 삭제."""
    await notion_sync.delete_notion_config()
    return {"status": "ok", "message": "Notion 연동이 비활성화되었습니다"}


@router.post("/notion/test", dependencies=[Depends(require_admin)])
async def test_notion_sync(conn=Depends(get_os_conn)):
    """수동 Notion 동기화 1회 실행."""
    from datetime import datetime, timezone

    config = await notion_sync.get_notion_config()
    if not config:
        raise HTTPException(status_code=400, detail="Notion 설정이 없습니다. 먼저 설정을 저장하세요.")

    api_key = config["api_key"]
    database_id = config["database_id"]
    users_db_id = config.get("users_database_id", "")
    hypervisors_db_id = config.get("hypervisors_database_id", "")

    # 1. 하이퍼바이저 동기화 먼저 실행 → page_id 맵 구축
    host_to_page_id: dict[str, str] = {}
    hypervisor_stats = None
    if hypervisors_db_id:
        try:
            hypervisors = await collect_hypervisor_data()
            hypervisor_stats = await notion_sync.sync_hypervisors_to_notion(api_key, hypervisors_db_id, hypervisors)
            config["hypervisors_last_sync"] = datetime.now(timezone.utc).isoformat()
            # 동기화 후 page_id 맵 구축 (인스턴스 relation 설정에 사용)
            host_to_page_id = await notion_sync.fetch_hypervisor_page_ids_by_name(api_key, hypervisors_db_id)
        except Exception:
            _logger.warning("Notion 테스트: 하이퍼바이저 동기화 실패", exc_info=True)

    # 2. People DB에서 이메일 → page_id 맵 구축
    email_to_page_id: dict[str, str] = {}
    if users_db_id:
        email_to_page_id = await notion_sync.fetch_user_page_ids_by_email(api_key, users_db_id)

    # 3. 인스턴스 데이터 수집 (relation page_id 포함)
    try:
        instances = await collect_instance_data(
            email_to_page_id=email_to_page_id,
            host_to_page_id=host_to_page_id,
        )
    except Exception:
        _logger.warning("Notion 테스트: 데이터 수집 실패", exc_info=True)
        raise HTTPException(status_code=500, detail="OpenStack 데이터 수집 실패")

    # 4. 인스턴스 동기화
    try:
        stats = await notion_sync.sync_to_notion(api_key, database_id, instances)
    except Exception as e:
        _logger.warning("Notion 테스트: 동기화 실패", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Notion 동기화 실패: {e}")

    config["last_sync"] = datetime.now(timezone.utc).isoformat()
    await notion_sync.save_notion_config(config)

    messages = [f"인스턴스: {stats['created']}개 생성, {stats['updated']}개 갱신, {stats['archived']}개 아카이브"]
    if hypervisor_stats:
        messages.append(f"하이퍼바이저: {hypervisor_stats['created']}개 생성, {hypervisor_stats['updated']}개 갱신")

    return {
        "status": "ok",
        "message": " / ".join(messages),
        "stats": stats,
        "hypervisor_stats": hypervisor_stats,
        "instance_count": len(instances),
    }


async def collect_instance_data(
    email_to_page_id: dict[str, str] | None = None,
    host_to_page_id: dict[str, str] | None = None,
) -> list[dict]:
    """OpenStack에서 전체 인스턴스 + 플레이버 + 사용자 + 프로젝트 정보를 수집한다.

    email_to_page_id: People DB의 {이메일 → page_id} 맵 (user relation 설정용)
    host_to_page_id: Hypervisor DB의 {호스트명 → page_id} 맵 (openstack resource relation 설정용)
    """
    from app.config import get_settings
    import openstack

    settings = get_settings()
    conn = openstack.connect(
        auth_url=settings.os_auth_url,
        username=settings.os_username,
        password=settings.os_password,
        project_name=settings.os_project_name,
        user_domain_name=settings.os_user_domain_name,
        project_domain_name=settings.os_project_domain_name,
    )

    try:
        def _collect():
            # 플레이버 맵
            flavors = {}
            for f in conn.compute.flavors(details=True):
                flavors[f.id] = f

            # 프로젝트 맵
            projects = {}
            try:
                for p in conn.identity.projects():
                    projects[p.id] = p.name
            except Exception:
                _logger.warning("프로젝트 목록 조회 실패", exc_info=True)

            # 사용자 맵 (id → name, id → email)
            users = {}
            user_emails: dict[str, str] = {}
            try:
                for u in conn.identity.users():
                    users[u.id] = u.name
                    if getattr(u, "email", None):
                        user_emails[u.id] = u.email
            except Exception:
                _logger.warning("사용자 목록 조회 실패", exc_info=True)

            # 인스턴스 수집
            result = []
            for s in conn.compute.servers(all_projects=True, details=True):
                # 플레이버 정보
                fl_id = ""
                fl_name = ""
                if isinstance(s.flavor, dict):
                    fl_id = s.flavor.get("id", "")
                    fl_name = s.flavor.get("original_name", "") or s.flavor.get("name", "")
                fl = flavors.get(fl_id)
                vcpus = fl.vcpus if fl else 0
                ram_mb = fl.ram if fl else 0
                extra_specs = fl.extra_specs if fl else {}

                # GPU
                gpu_name, gpu_count = notion_sync._gpu_info_from_flavor(
                    fl_name or (fl.name if fl else ""),
                    extra_specs or {},
                )

                # IP 주소
                fixed_ips = []
                floating_ips = []
                addresses = s.addresses or {}
                for net_name, addrs in addresses.items():
                    for addr in addrs:
                        if addr.get("OS-EXT-IPS:type") == "floating":
                            floating_ips.append(addr["addr"])
                        else:
                            fixed_ips.append(addr["addr"])

                # created_at → ISO 8601
                created_at_iso = ""
                if s.created_at:
                    created_at_iso = str(s.created_at).replace(" ", "T")
                    if not created_at_iso.endswith("Z") and "+" not in created_at_iso:
                        created_at_iso += "Z"

                # 호스트 정보 (openstack resource relation 연결용)
                compute_host = getattr(s, "compute_host", "") or ""

                # 사용자 page_id (People DB relation)
                user_email = user_emails.get(s.user_id, "")
                user_page_id = (email_to_page_id or {}).get(user_email.lower(), "")

                # 하이퍼바이저 page_id (openstack resource relation)
                status = (s.status or "").upper()
                hypervisor_page_id = ""
                if compute_host and status not in ("SHELVED_OFFLOADED", "SHELVED"):
                    hypervisor_page_id = (host_to_page_id or {}).get(compute_host, "")

                result.append({
                    "name": s.name or "",
                    "instance_id": s.id or "",
                    "status": status,
                    "project_name": projects.get(s.project_id, ""),
                    "flavor_name": fl_name or (fl.name if fl else ""),
                    "vcpus": vcpus,
                    "ram_gb": round(ram_mb / 1024) if ram_mb else 0,
                    "gpu_name": gpu_name,
                    "gpu_count": gpu_count,
                    "fixed_ip": ", ".join(fixed_ips),
                    "floating_ip": ", ".join(floating_ips),
                    "created_at": created_at_iso,
                    "compute_host": compute_host,
                    "user_page_id": user_page_id,
                    "hypervisor_page_id": hypervisor_page_id,
                })

            return result

        return await asyncio.to_thread(_collect)
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def collect_hypervisor_data() -> list[dict]:
    """OpenStack에서 하이퍼바이저 리소스 정보를 수집한다."""
    from app.config import get_settings
    from app.api.identity.admin import _fetch_hypervisors_raw
    import openstack

    settings = get_settings()
    conn = openstack.connect(
        auth_url=settings.os_auth_url,
        username=settings.os_username,
        password=settings.os_password,
        project_name=settings.os_project_name,
        user_domain_name=settings.os_user_domain_name,
        project_domain_name=settings.os_project_domain_name,
    )

    try:
        def _collect():
            raw = _fetch_hypervisors_raw(conn)
            result = []
            for h in raw:
                mem_mb = h.get("memory_mb", 0) or 0
                mem_used_mb = h.get("memory_mb_used", 0) or 0
                result.append({
                    "name": h.get("hypervisor_hostname", ""),
                    "status": f"{h.get('state', '')}/{h.get('status', '')}",
                    "running_vms": h.get("running_vms", 0) or 0,
                    "vcpus_used": h.get("vcpus_used", 0) or 0,
                    "vcpus": h.get("vcpus", 0) or 0,
                    "memory_used_gb": round(mem_used_mb / 1024),
                    "memory_size_gb": round(mem_mb / 1024),
                })
            return result

        return await asyncio.to_thread(_collect)
    finally:
        try:
            conn.close()
        except Exception:
            pass
