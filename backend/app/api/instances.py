"""
인스턴스 오케스트레이션 엔드포인트.

생성 순서:
  1. Manila access rule(A) 또는 신규 share(B)
  2. Cinder 부트 볼륨
  3. Cinder upper 볼륨
  4. cloud-init userdata 생성
  5. Nova 서버 생성

실패 시 역순 rollback.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.config import get_settings
from app.models.compute import CreateInstanceRequest, InstanceInfo
from app.services import nova, cinder, manila, cloudinit, libraries as lib_svc

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=list[InstanceInfo])
async def list_instances(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return nova.list_servers(conn)
    except Exception as e:
        logger.error(f"인스턴스 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"인스턴스 목록 조회 실패: {e}")


@router.get("/{instance_id}", response_model=InstanceInfo)
async def get_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return nova.get_server(conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")


@router.post("", response_model=InstanceInfo, status_code=201)
async def create_instance(
    req: CreateInstanceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    settings = get_settings()
    resolved_libs = lib_svc.resolve_with_deps(req.libraries)

    # 수집된 리소스 (rollback 용)
    created_share_ids: list[str] = []
    created_access_ids: list[tuple[str, str]] = []   # (share_id, access_id)
    boot_volume_id: str | None = None
    upper_volume_id: str | None = None
    server_id: str | None = None

    try:
        # ------------------------------------------------------------------
        # 1. Manila: share 및 access rule 준비
        # ------------------------------------------------------------------
        shares_info = []  # cloud-init 에 전달할 share 정보 목록

        if req.strategy == "prebuilt":
            shares_info = await _prepare_prebuilt_shares(
                conn, resolved_libs, req.name, created_access_ids
            )
        else:
            share_info = await _prepare_dynamic_share(
                conn, req.name, resolved_libs, settings, created_share_ids, created_access_ids
            )
            shares_info = [share_info]

        # ------------------------------------------------------------------
        # 2. Cinder: 부트 볼륨 생성
        # ------------------------------------------------------------------
        boot_vol = cinder.create_volume_from_image(
            conn,
            name=f"union-boot-{req.name}",
            image_id=req.image_id,
            size_gb=settings.boot_volume_size_gb,
            availability_zone=req.availability_zone or settings.default_availability_zone,
        )
        boot_volume_id = boot_vol.id

        # ------------------------------------------------------------------
        # 3. Cinder: upper 볼륨 생성 (OverlayFS upperdir)
        # ------------------------------------------------------------------
        upper_vol = cinder.create_empty_volume(
            conn,
            name=f"union-upper-{req.name}",
            size_gb=settings.upper_volume_size_gb,
            availability_zone=req.availability_zone or settings.default_availability_zone,
        )
        upper_volume_id = upper_vol.id

        # ------------------------------------------------------------------
        # 4. cloud-init userdata 생성
        # ------------------------------------------------------------------
        # GPU 플레이버 여부 확인
        flavors = nova.list_flavors(conn)
        flavor = next((f for f in flavors if f.id == req.flavor_id), None)
        gpu_available = flavor.has_gpu if flavor else False

        userdata = cloudinit.generate_userdata(
            libraries=resolved_libs,
            strategy=req.strategy,
            shares=shares_info,
            upper_device="/dev/vdb",    # Nova가 두 번째 블록으로 붙임
            ceph_monitors=settings.ceph_monitors,
            gpu_available=gpu_available,
        )

        # ------------------------------------------------------------------
        # 5. Nova: 서버 생성
        # ------------------------------------------------------------------
        meta = {
            "union_libraries": ",".join(resolved_libs),
            "union_strategy": req.strategy,
            "union_share_ids": ",".join(
                [s.get("share_id", "") for s in shares_info]
            ),
            "union_upper_volume_id": upper_volume_id,
        }

        # upper 볼륨을 두 번째 블록 디바이스로 추가
        # (Nova block_device_mapping_v2 에 추가 볼륨 연결)
        server = nova.create_server(
            conn,
            name=req.name,
            flavor_id=req.flavor_id,
            network_id=req.network_id or settings.default_network_id,
            boot_volume_id=boot_volume_id,
            userdata=userdata,
            key_name=req.key_name,
            availability_zone=req.availability_zone or settings.default_availability_zone,
            metadata=meta,
        )
        server_id = server.id

        # upper 볼륨 attach (서버 생성 후)
        conn.compute.create_volume_attachment(
            server_id, volume_id=upper_volume_id
        )

        return server

    except Exception as e:
        logger.error(f"인스턴스 생성 실패, rollback 시작: {e}")
        await _rollback(conn, server_id, boot_volume_id, upper_volume_id,
                        created_share_ids, created_access_ids)
        raise HTTPException(status_code=500, detail=f"인스턴스 생성 실패: {e}")


@router.delete("/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        server = nova.get_server(conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")

    upper_volume_id = server.union_upper_volume_id
    share_ids = server.union_share_ids
    strategy = server.union_strategy

    # Nova 서버 삭제
    nova.delete_server(conn, instance_id)

    # Strategy B: 전용 share 삭제
    if strategy == "dynamic":
        for share_id in share_ids:
            if share_id:
                try:
                    manila.delete_share(conn, share_id)
                except Exception as ex:
                    logger.warning(f"Share 삭제 실패 {share_id}: {ex}")

    # upper 볼륨 삭제
    if upper_volume_id:
        try:
            cinder.delete_volume(conn, upper_volume_id)
        except Exception as ex:
            logger.warning(f"Upper 볼륨 삭제 실패: {ex}")


@router.get("/{instance_id}/console")
async def get_console(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        url = nova.get_console_url(conn, instance_id)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

async def _prepare_prebuilt_shares(
    conn, resolved_libs: list[str], instance_name: str,
    created_access_ids: list
) -> list[dict]:
    """Strategy A: 사전 빌드된 read-only share에 access rule 추가."""
    prebuilt_shares = manila.list_shares(conn, metadata_filter={"union_type": "prebuilt"})
    prebuilt_map = {s.library_name: s for s in prebuilt_shares}

    shares_info = []
    for lib_id in list(reversed(resolved_libs)):
        lib = lib_svc.get_by_id(lib_id)
        share = prebuilt_map.get(lib_id)
        if not share:
            raise RuntimeError(f"사전 빌드 share 없음: {lib_id}. Strategy B를 사용하거나 관리자에게 문의하세요.")

        cephx_id = f"union-ro-{instance_name}-{lib_id}"
        rule = manila.create_access_rule(conn, share.id, cephx_id, access_level="ro")
        created_access_ids.append((share.id, rule["access_id"]))

        export_paths = manila.get_export_locations(conn, share.id)
        shares_info.append({
            "share_id": share.id,
            "name": lib_id,
            "export_path": export_paths[0] if export_paths else "",
            "cephx_id": cephx_id,
            "cephx_key": rule["access_key"],
        })
    return shares_info


async def _prepare_dynamic_share(
    conn, instance_name: str, resolved_libs: list[str],
    settings, created_share_ids: list, created_access_ids: list
) -> dict:
    """Strategy B: VM 전용 read-write share 신규 생성."""
    share = manila.create_share(
        conn,
        name=f"union-dyn-{instance_name}",
        size_gb=settings.upper_volume_size_gb,
        share_network_id=settings.os_manila_share_network_id,
        share_type=settings.os_manila_share_type,
        metadata={
            "union_type": "dynamic",
            "union_instance": instance_name,
            "union_libraries": ",".join(resolved_libs),
        },
    )
    created_share_ids.append(share.id)

    cephx_id = f"union-rw-{instance_name}"
    rule = manila.create_access_rule(conn, share.id, cephx_id, access_level="rw")
    created_access_ids.append((share.id, rule["access_id"]))

    export_paths = manila.get_export_locations(conn, share.id)
    return {
        "share_id": share.id,
        "name": "dynamic",
        "export_path": export_paths[0] if export_paths else "",
        "cephx_id": cephx_id,
        "cephx_key": rule["access_key"],
    }


async def _rollback(
    conn,
    server_id: str | None,
    boot_volume_id: str | None,
    upper_volume_id: str | None,
    share_ids: list[str],
    access_ids: list[tuple[str, str]],
):
    if server_id:
        try:
            nova.delete_server(conn, server_id)
        except Exception as e:
            logger.error(f"Rollback - 서버 삭제 실패: {e}")

    for vol_id in [boot_volume_id, upper_volume_id]:
        if vol_id:
            try:
                cinder.delete_volume(conn, vol_id)
            except Exception as e:
                logger.error(f"Rollback - 볼륨 삭제 실패 {vol_id}: {e}")

    for share_id, access_id in access_ids:
        try:
            manila.revoke_access_rule(conn, share_id, access_id)
        except Exception as e:
            logger.error(f"Rollback - access rule 삭제 실패: {e}")

    for share_id in share_ids:
        try:
            manila.delete_share(conn, share_id)
        except Exception as e:
            logger.error(f"Rollback - share 삭제 실패 {share_id}: {e}")
