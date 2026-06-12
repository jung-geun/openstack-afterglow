"""Admin 라이브러리 관리 API.

§3.1 — 전용 admin library 엔드포인트 (GET 목록/상세, 빌드 트리거, 빌드 취소).
기존 /api/admin/file-storage/build 는 하위 호환 유지, 이 라우터는 /api/admin/libraries 접두어.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.common.activity_recorder import rec
from app.api.deps import get_os_conn, get_token_info, require_admin
from app.database import get_session
from app.services import libraries as lib_svc
from app.services import library_builder, manila, neutron, nova
from app.services.keystone import get_service_project_connection

_logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# 라이브러리 목록 / 상세
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(require_admin)])
async def list_admin_libraries(
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> list[dict]:
    """전체 라이브러리 카탈로그 (의존성, 가용 prebuilt 포함). 관리자 전용."""
    all_libs = lib_svc.get_all()

    try:
        prebuilt_storages = manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt"})
        prebuilt_map = {s.library_name: s for s in prebuilt_storages if s.library_name}
    except Exception:
        prebuilt_map = {}

    result = []
    for lib in all_libs:
        storage = prebuilt_map.get(lib.id)
        result.append(
            {
                "id": lib.id,
                "name": lib.name,
                "version": lib.version,
                "packages": lib.packages,
                "depends_on": lib.depends_on,
                "visibility": lib.visibility,
                "share_proto": lib.share_proto,
                "ubuntu_versions": lib.ubuntu_versions,
                "file_storage_id": storage.id if storage else None,
                "available_prebuilt": storage is not None,
                "build_status": (storage.metadata.get("union_status") if storage else None),
                "built_at": (storage.built_at if storage else None),
                "dependency_tree": lib_svc.get_dependency_tree(lib.id),
            }
        )
    return result


@router.get("/builds", dependencies=[Depends(require_admin)])
async def list_library_builds(
    library_id: str | None = Query(default=None),
) -> list[dict]:
    """라이브러리 빌드 이력 목록. 관리자 전용."""
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        # DB 미초기화 시 인메모리 캐시 반환
        builds = list(library_builder.get_active_builds().values())
        if library_id:
            builds = [b for b in builds if b.get("library_id") == library_id]
        return builds

    async with factory() as session:
        stmt = select(LibraryBuild).order_by(LibraryBuild.started_at.desc()).limit(50)
        if library_id:
            stmt = stmt.where(LibraryBuild.library_id == library_id)
        rows = (await session.execute(stmt)).scalars().all()

    return [
        {
            "id": row.id,
            "library_id": row.library_id,
            "file_storage_id": row.file_storage_id,
            "server_id": row.server_id,
            "status": row.status,
            "cloud_init_status": row.cloud_init_status,
            "progress_step": row.progress_step,
            "progress_pct": row.progress_pct,
            "error_message": row.error_message,
            "console_log_excerpt": (row.console_log_excerpt or "")[-500:] if row.console_log_excerpt else None,
            "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
            "completed_at": row.completed_at.isoformat() + "Z" if row.completed_at else None,
            "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        }
        for row in rows
    ]


@router.get("/builds/{build_id}", dependencies=[Depends(require_admin)])
async def get_library_build(build_id: int) -> dict:
    """빌드 상세 조회 — VM 실시간 상태·콘솔 로그 포함. 관리자 전용."""
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models.db import LibraryBuild

    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="DB가 초기화되지 않았습니다")

    async with factory() as session:
        row = (await session.execute(select(LibraryBuild).where(LibraryBuild.id == build_id))).scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail=f"빌드 {build_id}를 찾을 수 없습니다")

    _TERMINAL = {"complete", "error", "timeout", "cancelled"}
    is_active = row.status not in _TERMINAL

    vm_status: str | None = None
    vm_ip: str | None = None
    live_console: str | None = None
    console_note: str | None = None  # 콘솔 조회 불가 사유

    if row.server_id:
        try:
            svc_conn = await asyncio.to_thread(get_service_project_connection)
            server = await asyncio.to_thread(nova.get_server, svc_conn, row.server_id)
            vm_status = server.status
            # fixed IP 우선, 없으면 floating
            ips = [a.addr for a in (server.ip_addresses or []) if a.type == "fixed"]
            if not ips:
                ips = [a.addr for a in (server.ip_addresses or [])]
            vm_ip = ips[0] if ips else None

            if is_active:
                live_console = await asyncio.to_thread(nova.get_console_output, svc_conn, row.server_id, 300)
            else:
                # 비활성(SHUTOFF/ERROR 등) VM — 하이퍼바이저에 따라 console이 남아 있을 수 있음
                try:
                    live_console = await asyncio.to_thread(nova.get_console_output, svc_conn, row.server_id, 300)
                except Exception:
                    # console 없음 — DB excerpt 또는 안내 메시지 사용
                    status_upper = (vm_status or "").upper()
                    if status_upper in ("SHUTOFF", "ERROR"):
                        console_note = f"VM이 {vm_status} 상태로 실시간 콘솔을 사용할 수 없습니다. 마지막 저장 로그를 확인하세요."
                    else:
                        console_note = "콘솔 로그를 가져올 수 없습니다."
        except Exception:
            _logger.warning("[admin_libraries] VM 정보 조회 실패: server_id=%s", row.server_id, exc_info=True)
            console_note = "VM 정보를 가져올 수 없습니다."
    elif row.server_id is None and not is_active:
        console_note = "빌드 VM 정보가 없습니다."

    return {
        "id": row.id,
        "library_id": row.library_id,
        "file_storage_id": row.file_storage_id,
        "server_id": row.server_id,
        "port_id": row.port_id,
        "status": row.status,
        "cloud_init_status": row.cloud_init_status,
        "progress_step": row.progress_step,
        "progress_pct": row.progress_pct,
        "error_message": row.error_message,
        "console_log_excerpt": row.console_log_excerpt,
        "started_at": row.started_at.isoformat() + "Z" if row.started_at else None,
        "completed_at": row.completed_at.isoformat() + "Z" if row.completed_at else None,
        "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        # 실시간 VM 정보
        "vm_status": vm_status,
        "vm_ip": vm_ip,
        "live_console": live_console,
        "console_note": console_note,
    }


@router.get("/{library_id}", dependencies=[Depends(require_admin)])
async def get_admin_library(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> dict:
    """라이브러리 상세 (의존성 트리 + prebuilt 상태 포함). 관리자 전용."""
    try:
        lib = lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}를 찾을 수 없습니다")

    try:
        storages = manila.list_file_storages(
            conn, metadata_filter={"union_type": "prebuilt", "union_library": library_id}
        )
        storage = storages[0] if storages else None
    except Exception:
        storage = None

    return {
        "id": lib.id,
        "name": lib.name,
        "version": lib.version,
        "packages": lib.packages,
        "depends_on": lib.depends_on,
        "visibility": lib.visibility,
        "share_proto": lib.share_proto,
        "ubuntu_versions": lib.ubuntu_versions,
        "file_storage_id": storage.id if storage else None,
        "available_prebuilt": storage is not None,
        "build_status": (storage.metadata.get("union_status") if storage else None),
        "built_at": (storage.built_at if storage else None),
        "dependency_tree": lib_svc.get_dependency_tree(library_id),
        "active_builds": library_builder.get_active_builds().get(library_id),
    }


# ---------------------------------------------------------------------------
# 빌드 트리거
# ---------------------------------------------------------------------------


class TriggerBuildRequest(BaseModel):
    library_id: str
    auto_install: bool = True
    file_storage_id: str | None = None
    """사전 생성한 file storage ID. 지정하면 빌더가 새 share를 생성하지 않고 이 share를 사용한다.
    service 프로젝트에 소속되어 있거나 service conn으로 조회 가능해야 한다."""


@router.post("/build", status_code=202, dependencies=[Depends(require_admin)])
async def trigger_library_build(
    req: TriggerBuildRequest,
    token_info: dict = Depends(get_token_info),
) -> dict:
    """라이브러리 prebuilt 빌드 트리거. auto_install=True 시 Builder VM 자동 생성.

    Manila share와 빌더 VM은 service 프로젝트에 생성된다.
    """
    try:
        lib_svc.get_by_id(req.library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {req.library_id}를 찾을 수 없습니다")

    if req.auto_install:
        try:
            if req.file_storage_id:
                # 사전 생성 share 경로: 큐를 거치지 않고 즉시 빌드 시작.
                # queue_build는 _build_worker 기동에 의존하지만, ASGITransport 테스트 환경에서는
                # lifespan 이벤트가 발동하지 않아 워커가 시작되지 않는다.
                # start_ephemeral_build는 asyncio.create_task로 백그라운드 태스크를 직접 등록하므로
                # 워커 없이도 동작하며 build_id를 즉시 반환한다.
                result = await library_builder.start_ephemeral_build(
                    req.library_id, existing_share_id=req.file_storage_id
                )
            else:
                result = await library_builder.queue_build(req.library_id)
            await rec(token_info, None, resource_type="library", action="build", resource_id=req.library_id)
            return result
        except RuntimeError as e:
            await rec(
                token_info,
                None,
                resource_type="library",
                action="build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
            status_code = 409 if "이미" in str(e) else 400
            raise HTTPException(status_code=status_code, detail=str(e))
    else:
        # auto_install=False: 빈 share 생성만 수행 (수동 설치용) — service 프로젝트에 생성
        import asyncio

        from app.config import get_settings
        from app.services.keystone import get_service_project_connection

        settings = get_settings()
        lib = lib_svc.get_by_id(req.library_id)
        try:
            svc_conn = await asyncio.to_thread(get_service_project_connection)
            storage = await asyncio.to_thread(
                manila.create_file_storage,
                svc_conn,
                name=f"union-prebuilt-{req.library_id}",
                size_gb=20,
                share_network_id=settings.os_manila_share_network_id,
                share_type=settings.os_manila_share_type,
                metadata={
                    "union_type": "prebuilt",
                    "union_library": req.library_id,
                    "union_version": lib.version,
                    "union_status": "pending",
                },
            )
            await rec(token_info, None, resource_type="library", action="prebuilt_build", resource_id=req.library_id)
            return {
                "file_storage_id": storage.id,
                "status": "pending",
                "library": req.library_id,
                "message": "빈 share 생성 완료. 수동으로 패키지를 설치하세요.",
            }
        except RuntimeError as e:
            await rec(
                token_info,
                None,
                resource_type="library",
                action="prebuilt_build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            _logger.warning("Share 생성 실패: %s", e)
            await rec(
                token_info,
                None,
                resource_type="library",
                action="prebuilt_build",
                status="failed",
                resource_id=req.library_id,
                error_message=str(e)[:500],
            )
            raise HTTPException(status_code=502, detail="Share 생성 실패")


# ---------------------------------------------------------------------------
# 빌드 취소
# ---------------------------------------------------------------------------


@router.post("/builds/{build_id}/cancel", dependencies=[Depends(require_admin)])
async def cancel_library_build(
    build_id: int,
) -> dict:
    """진행 중인 라이브러리 빌드를 취소하고 VM 리소스를 정리한다. 관리자 전용."""
    try:
        return await library_builder.cancel_build(build_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Ephemeral Builder VM 스모크 테스트
# ---------------------------------------------------------------------------


@router.post("/builder-vm/_smoke", status_code=200, dependencies=[Depends(require_admin)])
async def smoke_test_ephemeral_vm() -> dict:
    """임시 Builder VM 생성 → SSH 연결 확인 → 삭제. 관리자 전용 연결 검증 엔드포인트."""
    from app.services import builder_vm as bvm
    from app.services.ssh_executor import run_command

    svc_conn = await asyncio.to_thread(get_service_project_connection)
    vm: bvm.EphemeralBuilderVM | None = None
    try:
        vm = await bvm.create_ephemeral_vm(svc_conn)

        rc, stdout, stderr = await run_command(
            vm.host,
            vm.key_path,
            "echo ok && hostname && uname -r",
            username=vm.username,
        )
        if rc != 0:
            raise HTTPException(
                status_code=500,
                detail=f"SSH 명령 실패 (exit={rc}): {stderr}",
            )

        return {
            "status": "ok",
            "server_id": vm.server_id,
            "fip": vm.host,
            "internal_ip": vm.internal_ip,
            "ssh_output": stdout.strip(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if vm is not None:
            cleanup_conn = await asyncio.to_thread(get_service_project_connection)
            await bvm.delete_ephemeral_vm(cleanup_conn, vm.server_id, vm.fip_id)


# ---------------------------------------------------------------------------
# Ephemeral Builder VM + Manila 마운트 검증 스모크 테스트
# ---------------------------------------------------------------------------


class SmokeMountRequest(BaseModel):
    share_proto: str = "NFS"  # "NFS" | "CEPHFS"
    size_gb: int = 1


@router.post("/builder-vm/_smoke-mount", status_code=200, dependencies=[Depends(require_admin)])
async def smoke_test_ephemeral_mount(req: SmokeMountRequest) -> dict:
    """임시 Builder VM 생성 → Manila share 생성 → 마운트 검증 → 전체 정리.

    share_proto=NFS (기본) 또는 CEPHFS를 선택해 실제 마운트까지 검증한다.
    """
    import uuid

    from app.services import builder_vm as bvm
    from app.services import ephemeral_mount as emount

    proto = req.share_proto.upper()
    if proto not in ("NFS", "CEPHFS"):
        raise HTTPException(status_code=400, detail="share_proto는 NFS 또는 CEPHFS여야 합니다")

    svc_conn = await asyncio.to_thread(get_service_project_connection)
    vm: bvm.EphemeralBuilderVM | None = None
    share_id: str | None = None
    access_rule: dict | None = None

    try:
        vm = await bvm.create_ephemeral_vm(svc_conn)

        share_name = f"smoke-mount-{uuid.uuid4().hex[:8]}"
        share_id = await emount.create_builder_share(svc_conn, share_name, req.size_gb, proto)

        access_rule = await emount.add_vm_access_rule(svc_conn, share_id, vm.internal_ip, proto)

        mount_cmd = await emount.build_mount_command(svc_conn, share_id, proto, access_rule)

        result = await emount.verify_mount_via_ssh(vm, mount_cmd)

        if not result["mounted"]:
            raise HTTPException(
                status_code=500,
                detail=f"마운트 검증 실패: {result.get('error')}",
            )

        return {
            "status": "ok",
            "share_proto": proto,
            "share_id": share_id,
            "server_id": vm.server_id,
            "internal_ip": vm.internal_ip,
            "df_output": result["df_output"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        cleanup_conn = await asyncio.to_thread(get_service_project_connection)
        if share_id and access_rule:
            try:
                await asyncio.to_thread(
                    manila.revoke_access_rule,
                    cleanup_conn,
                    share_id,
                    access_rule["access_id"],
                )
            except Exception:
                _logger.warning("[smoke-mount] access rule revoke 실패", exc_info=True)
        if share_id:
            try:
                await asyncio.to_thread(manila.delete_file_storage, cleanup_conn, share_id)
            except Exception:
                _logger.warning("[smoke-mount] share 삭제 실패", exc_info=True)
        if vm is not None:
            await bvm.delete_ephemeral_vm(cleanup_conn, vm.server_id, vm.fip_id)


# ---------------------------------------------------------------------------
# Heat stack 기반 smoke-mount (Phase 1 PoC)
# ---------------------------------------------------------------------------


@router.post("/builder-vm/_smoke-mount-heat", status_code=200, dependencies=[Depends(require_admin)])
async def smoke_test_mount_heat(req: SmokeMountRequest) -> dict:
    """Heat HOT stack 으로 VM + FIP 선언 → Manila share/access rule Python 처리 → 마운트 검증."""
    import uuid

    from app.config import get_settings
    from app.services import builder_vm as bvm
    from app.services import ephemeral_mount as emount
    from app.services import heat as heat_svc

    proto = req.share_proto.upper()
    if proto not in ("NFS", "CEPHFS"):
        raise HTTPException(status_code=400, detail="share_proto는 NFS 또는 CEPHFS여야 합니다")

    settings = get_settings()
    svc_conn = await asyncio.to_thread(get_service_project_connection)
    stack_id: str | None = None
    share_id: str | None = None
    access_rule: dict | None = None

    try:
        keypair_name = await bvm._ensure_ephemeral_keypair(svc_conn, settings.builder_ssh_key_path)

        share_name = f"smoke-heat-{uuid.uuid4().hex[:8]}"
        share_id = await emount.create_builder_share(svc_conn, share_name, req.size_gb, proto)

        vm_name = f"afterglow-builder-{uuid.uuid4().hex[:8]}"
        template_str = await asyncio.to_thread(heat_svc.render_template, "builder_smoke.yaml.j2", {})
        parameters = {
            "image_id": settings.builder_image_id,
            "flavor_id": settings.builder_flavor_id,
            "network_id": settings.builder_network_id or settings.default_network_id,
            "keypair_name": keypair_name,
            "user_data": bvm._EPHEMERAL_CLOUD_INIT,
            "vm_name": vm_name,
            "floating_network_id": settings.builder_floating_network_id or "",
        }
        stack_name = f"afterglow-smoke-{uuid.uuid4().hex[:8]}"
        stack_id = await asyncio.to_thread(heat_svc.create_stack, svc_conn, stack_name, template_str, parameters)

        outputs = await asyncio.to_thread(heat_svc.wait_for_stack_complete, svc_conn, stack_id)
        internal_ip = outputs.get("internal_ip", "")
        ssh_host = outputs.get("ssh_host", internal_ip)
        server_id = outputs.get("server_id", "")

        if not internal_ip:
            raise RuntimeError("Heat stack outputs 에서 internal_ip 를 찾을 수 없습니다")

        await bvm._wait_for_ssh(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)
        await bvm._wait_for_cloud_init(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)

        access_rule = await emount.add_vm_access_rule(svc_conn, share_id, internal_ip, proto)

        vm = bvm.EphemeralBuilderVM(
            server_id=server_id,
            host=ssh_host,
            username=settings.builder_ssh_user,
            key_path=settings.builder_ssh_key_path,
            internal_ip=internal_ip,
            fip_id=outputs.get("fip_id") or None,
        )
        mount_cmd = await emount.build_mount_command(svc_conn, share_id, proto, access_rule)
        result = await emount.verify_mount_via_ssh(vm, mount_cmd)

        if not result["mounted"]:
            raise HTTPException(status_code=500, detail=f"마운트 검증 실패: {result.get('error')}")

        return {
            "status": "ok",
            "tool": "heat",
            "share_proto": proto,
            "share_id": share_id,
            "server_id": server_id,
            "internal_ip": internal_ip,
            "df_output": result["df_output"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        cleanup_conn = await asyncio.to_thread(get_service_project_connection)
        if share_id and access_rule:
            try:
                await asyncio.to_thread(manila.revoke_access_rule, cleanup_conn, share_id, access_rule["access_id"])
            except Exception:
                _logger.warning("[smoke-mount-heat] access rule revoke 실패", exc_info=True)
        if share_id:
            try:
                await asyncio.to_thread(manila.delete_file_storage, cleanup_conn, share_id)
            except Exception:
                _logger.warning("[smoke-mount-heat] share 삭제 실패", exc_info=True)
        if stack_id:
            await asyncio.to_thread(heat_svc.delete_stack, cleanup_conn, stack_id)


# ---------------------------------------------------------------------------
# OpenTofu 기반 smoke-mount (Phase 1 PoC)
# ---------------------------------------------------------------------------


@router.post("/builder-vm/_smoke-mount-tofu", status_code=200, dependencies=[Depends(require_admin)])
async def smoke_test_mount_tofu(req: SmokeMountRequest) -> dict:
    """OpenTofu 로 VM + FIP + Manila share + access rule 선언 → SSH 마운트 검증."""
    import base64
    import uuid

    from app.config import get_settings
    from app.services import builder_vm as bvm
    from app.services import ephemeral_mount as emount
    from app.services import tofu_runner

    proto = req.share_proto.upper()
    if proto not in ("NFS", "CEPHFS"):
        raise HTTPException(status_code=400, detail="share_proto는 NFS 또는 CEPHFS여야 합니다")

    settings = get_settings()
    svc_conn = await asyncio.to_thread(get_service_project_connection)
    workdir = None

    try:
        keypair_name = await bvm._ensure_ephemeral_keypair(svc_conn, settings.builder_ssh_key_path)

        vm_name = f"afterglow-builder-{uuid.uuid4().hex[:8]}"
        share_name = f"smoke-tofu-{uuid.uuid4().hex[:8]}"
        userdata_b64 = base64.b64encode(bvm._EPHEMERAL_CLOUD_INIT.encode()).decode()

        variables = {
            "vm_name": vm_name,
            "image_id": settings.builder_image_id,
            "flavor_id": settings.builder_flavor_id,
            "network_id": settings.builder_network_id or settings.default_network_id,
            "keypair_name": keypair_name,
            "user_data_b64": userdata_b64,
            "floating_network_id": settings.builder_floating_network_id or "",
            "share_name": share_name,
            "share_proto": proto,
            "size_gb": req.size_gb,
            "share_type": (settings.os_manila_nfs_share_type if proto == "NFS" else settings.os_manila_share_type),
            "share_network_id": settings.os_manila_share_network_id if proto == "NFS" else "",
        }

        workdir, outputs = await tofu_runner.apply("builder_smoke", variables, svc_conn)

        internal_ip = outputs.get("internal_ip", "")
        ssh_host = outputs.get("ssh_host", internal_ip)
        share_id = outputs.get("share_id", "")
        access_key = outputs.get("access_key", "")
        server_id = outputs.get("server_id", "")

        if not internal_ip or not share_id:
            raise RuntimeError("tofu outputs 에서 internal_ip 또는 share_id 를 찾을 수 없습니다")

        vm = bvm.EphemeralBuilderVM(
            server_id=server_id,
            host=ssh_host,
            username=settings.builder_ssh_user,
            key_path=settings.builder_ssh_key_path,
            internal_ip=internal_ip,
            fip_id=outputs.get("fip_id") or None,
        )

        await bvm._wait_for_ssh(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)
        await bvm._wait_for_cloud_init(ssh_host, settings.builder_ssh_key_path, settings.builder_ssh_user)

        access_rule_info = {"access_to": f"builder-{vm_name}", "access_key": access_key}
        mount_cmd = await emount.build_mount_command(svc_conn, share_id, proto, access_rule_info)
        result = await emount.verify_mount_via_ssh(vm, mount_cmd)

        if not result["mounted"]:
            raise HTTPException(status_code=500, detail=f"마운트 검증 실패: {result.get('error')}")

        return {
            "status": "ok",
            "tool": "tofu",
            "share_proto": proto,
            "share_id": share_id,
            "server_id": server_id,
            "internal_ip": internal_ip,
            "df_output": result["df_output"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if workdir is not None:
            cleanup_conn = await asyncio.to_thread(get_service_project_connection)
            try:
                await tofu_runner.destroy(workdir, cleanup_conn)
            except Exception:
                _logger.warning("[smoke-mount-tofu] tofu destroy 실패", exc_info=True)


# ---------------------------------------------------------------------------
# NFS 크로스 프로젝트 access rule 관리 (§3.3)
# ---------------------------------------------------------------------------


class GrantProjectAccessRequest(BaseModel):
    project_id: str
    network_id: str


def _get_nfs_share_for_library(conn, library_id: str):
    """라이브러리 ID로 prebuilt NFS share를 조회. NFS가 아니거나 없으면 예외."""
    try:
        lib_svc.get_by_id(library_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}를 찾을 수 없습니다")

    storages = manila.list_file_storages(conn, metadata_filter={"union_type": "prebuilt", "union_library": library_id})
    if not storages:
        raise HTTPException(status_code=404, detail=f"라이브러리 {library_id}의 prebuilt share가 없습니다")
    storage = storages[0]
    if storage.share_proto != "NFS":
        raise HTTPException(
            status_code=400,
            detail=f"라이브러리 {library_id}는 NFS가 아닙니다 (proto={storage.share_proto}). IP access rule이 필요하지 않습니다.",
        )
    return storage


@router.post("/{library_id}/project-access", dependencies=[Depends(require_admin)])
async def grant_library_project_access(
    library_id: str,
    req: GrantProjectAccessRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """NFS prebuilt 라이브러리에 특정 프로젝트의 subnet CIDR access rule을 추가한다.

    이미 rule이 있으면 idempotent하게 처리한다 (중복 생성 없음).
    """
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        net_detail = await asyncio.to_thread(neutron.get_network_detail, conn, req.network_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"네트워크 CIDR 조회 실패: {e}")

    cidrs = [s.cidr for s in (net_detail.subnet_details or []) if s.cidr]
    if not cidrs:
        raise HTTPException(status_code=400, detail="해당 네트워크에 subnet CIDR이 없습니다")

    granted = []
    for cidr in cidrs:
        try:
            rule = await asyncio.to_thread(
                manila.ensure_nfs_access_rule,
                svc_conn,
                storage.id,
                cidr,
                "ro",
                True,
                "sys",
                {"union_grant_project": req.project_id},
            )
            granted.append({"cidr": cidr, "rule_id": rule["access_id"]})
        except Exception as e:
            _logger.error("NFS access rule 추가 실패 (cidr=%s): %s", cidr, e)
            raise HTTPException(status_code=502, detail=f"NFS access rule 추가 실패 (cidr={cidr}): {e}")

    await rec(
        token_info,
        conn,
        resource_type="library",
        action="link",
        resource_id=library_id,
        extra={"project_id": req.project_id},
    )
    return {
        "library_id": library_id,
        "share_id": storage.id,
        "project_id": req.project_id,
        "granted_cidrs": [g["cidr"] for g in granted],
        "rules": granted,
    }


@router.delete("/{library_id}/project-access/{project_id}", dependencies=[Depends(require_admin)])
async def revoke_library_project_access(
    library_id: str,
    project_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
) -> dict:
    """NFS prebuilt 라이브러리에서 특정 프로젝트의 CIDR access rule을 revoke한다.

    union_grant_project metadata로 해당 프로젝트의 rule을 식별한다.
    """
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        access_rules = await asyncio.to_thread(manila.list_access_rules, svc_conn, storage.id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"access rule 목록 조회 실패: {e}")

    target_rules = [
        r
        for r in access_rules
        if r.get("access_type") == "ip" and r.get("metadata", {}).get("union_grant_project") == project_id
    ]

    revoked_ids = []
    for rule in target_rules:
        try:
            await asyncio.to_thread(manila.revoke_access_rule, svc_conn, storage.id, rule["id"])
            revoked_ids.append(rule["id"])
        except Exception as e:
            _logger.error("NFS access rule revoke 실패 (rule=%s): %s", rule["id"], e)
            raise HTTPException(status_code=502, detail=f"access rule revoke 실패 (rule_id={rule['id']}): {e}")

    await rec(
        token_info,
        conn,
        resource_type="library",
        action="unlink",
        resource_id=library_id,
        extra={"project_id": project_id},
    )
    return {
        "library_id": library_id,
        "share_id": storage.id,
        "project_id": project_id,
        "revoked_count": len(revoked_ids),
        "revoked_rule_ids": revoked_ids,
    }


@router.get("/{library_id}/project-access", dependencies=[Depends(require_admin)])
async def list_library_project_access(
    library_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
) -> dict:
    """NFS prebuilt 라이브러리에 grant된 프로젝트별 CIDR access rule 목록을 반환한다."""
    try:
        svc_conn = await asyncio.to_thread(get_service_project_connection)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"서비스 프로젝트 연결 실패: {e}")
    storage = await asyncio.to_thread(_get_nfs_share_for_library, svc_conn, library_id)

    try:
        access_rules = await asyncio.to_thread(manila.list_access_rules, svc_conn, storage.id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"access rule 목록 조회 실패: {e}")

    # union_grant_project metadata로 프로젝트별 grouping
    grants: dict[str, dict] = {}
    for rule in access_rules:
        if rule.get("access_type") != "ip":
            continue
        pid = rule.get("metadata", {}).get("union_grant_project", "__unknown__")
        if pid not in grants:
            grants[pid] = {"project_id": pid, "cidrs": [], "rule_ids": []}
        grants[pid]["cidrs"].append(rule.get("access_to", ""))
        grants[pid]["rule_ids"].append(rule["id"])

    return {
        "library_id": library_id,
        "share_id": storage.id,
        "grants": list(grants.values()),
    }


# ---------------------------------------------------------------------------
# 카탈로그 관리 (CRUD)
# ---------------------------------------------------------------------------


class CatalogCreateRequest(BaseModel):
    library_id: str
    name: str
    version: str
    packages: list[str] = []
    depends_on: list[str] = []
    share_proto: str = "CEPHFS"
    ubuntu_versions: list[str] = ["22.04", "24.04"]
    visibility: str = "public"
    license_type: str | None = None
    max_concurrent_mounts: int | None = None


class CatalogUpdateRequest(BaseModel):
    name: str | None = None
    version: str | None = None
    packages: list[str] | None = None
    depends_on: list[str] | None = None
    share_proto: str | None = None
    ubuntu_versions: list[str] | None = None
    visibility: str | None = None
    license_type: str | None = None
    max_concurrent_mounts: int | None = None


@router.post("/catalog", status_code=201, dependencies=[Depends(require_admin)])
async def create_catalog_entry(
    req: CatalogCreateRequest,
    session=Depends(get_session),
) -> dict:
    """카탈로그 항목 생성. 관리자 전용."""
    from app.models.db import LibraryCatalog

    existing = (
        await session.execute(select(LibraryCatalog).where(LibraryCatalog.library_id == req.library_id))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="이미 존재하는 라이브러리 ID")
    row = LibraryCatalog(**req.model_dump())
    session.add(row)
    await session.commit()
    await lib_svc.reload_catalog()
    return {"ok": True}


@router.patch("/catalog/{library_id}", dependencies=[Depends(require_admin)])
async def update_catalog_entry(
    library_id: str,
    req: CatalogUpdateRequest,
    session=Depends(get_session),
) -> dict:
    """카탈로그 항목 수정. 관리자 전용."""
    from app.models.db import LibraryCatalog

    row = (
        await session.execute(select(LibraryCatalog).where(LibraryCatalog.library_id == library_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="라이브러리를 찾을 수 없습니다")
    for field, val in req.model_dump(exclude_none=True).items():
        setattr(row, field, val)
    await session.commit()
    await lib_svc.reload_catalog()
    return {"ok": True}


@router.delete("/catalog/{library_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_catalog_entry(
    library_id: str,
    session=Depends(get_session),
) -> None:
    """카탈로그 항목 삭제. 관리자 전용."""
    from app.models.db import LibraryCatalog

    row = (
        await session.execute(select(LibraryCatalog).where(LibraryCatalog.library_id == library_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="라이브러리를 찾을 수 없습니다")
    await session.delete(row)
    await session.commit()
    await lib_svc.reload_catalog()
