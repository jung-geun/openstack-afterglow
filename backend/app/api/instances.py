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
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import openstack

from app.api.deps import get_os_conn
from app.config import get_settings
from app.models.compute import CreateInstanceRequest, InstanceInfo
from app.models.progress import ProgressMessage, ProgressStep
from app.services import nova, cinder, manila, cloudinit, libraries as lib_svc, neutron, keystone

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
    """동기식 인스턴스 생성 (기존 방식)."""
    settings = get_settings()
    resolved_libs = lib_svc.resolve_with_deps(req.libraries)

    # 수집된 리소스 (rollback 용)
    created_share_ids: list[str] = []
    created_access_ids: list[tuple[str, str]] = []   # (share_id, access_id)
    boot_volume_id: str | None = None
    upper_volume_id: str | None = None
    server_id: str | None = None
    floating_ip_id: str | None = None

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
            size_gb=req.boot_volume_size_gb or settings.boot_volume_size_gb,
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

        # Floating IP 자동 생성 (tenant 네트워크 선택 시)
        if req.network_id:
            all_nets = neutron.list_networks(conn)
            selected_net = next((n for n in all_nets if n.id == req.network_id), None)
            if selected_net and not selected_net.is_external:
                ext_net = next((n for n in all_nets if n.is_external), None)
                if ext_net:
                    fip = neutron.create_floating_ip(conn, ext_net.id)
                    floating_ip_id = fip.id
                    neutron.associate_floating_ip(conn, fip.id, server_id)

        return server

    except Exception as e:
        logger.error(f"인스턴스 생성 실패, rollback 시작: {e}")
        await _rollback(conn, server_id, boot_volume_id, upper_volume_id,
                        created_share_ids, created_access_ids, floating_ip_id)
        raise HTTPException(status_code=500, detail=f"인스턴스 생성 실패: {e}")


@router.post("/async")
async def create_instance_async(
    req: CreateInstanceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """SSE로 진행 상황을 스트리밍하는 비동기 인스턴스 생성."""
    settings = get_settings()
    resolved_libs = lib_svc.resolve_with_deps(req.libraries)

    async def progress_generator():
        # 수집된 리소스 (rollback 용)
        created_share_ids: list[str] = []
        created_access_ids: list[tuple[str, str]] = []
        boot_volume_id: str | None = None
        upper_volume_id: str | None = None
        server_id: str | None = None
        floating_ip_id: str | None = None

        def send_progress(step: ProgressStep, progress: int, message: str, **extra):
            msg = ProgressMessage(step=step, progress=progress, message=message, **extra)
            return f"data: {msg.model_dump_json()}\n\n"

        try:
            # Step 1: Manila shares (0-20%)
            yield send_progress(ProgressStep.MANILA_PREPARING, 0, "Manila shares 준비 중...")
            shares_info = []

            if req.strategy == "prebuilt":
                shares_info = await _prepare_prebuilt_shares(
                    conn, resolved_libs, req.name, created_access_ids
                )
            else:
                share_info = await _prepare_dynamic_share(
                    conn, req.name, resolved_libs, settings, created_share_ids, created_access_ids
                )
                shares_info = [share_info]
            yield send_progress(ProgressStep.MANILA_PREPARING, 20, "Manila shares 준비 완료")

            # Step 2: Boot volume (20-45%)
            yield send_progress(ProgressStep.BOOT_VOLUME_CREATING, 20, "부트 볼륨 생성 중...")
            boot_vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn,
                name=f"union-boot-{req.name}",
                image_id=req.image_id,
                size_gb=req.boot_volume_size_gb or settings.boot_volume_size_gb,
                availability_zone=req.availability_zone or settings.default_availability_zone,
            )
            boot_volume_id = boot_vol.id
            yield send_progress(ProgressStep.BOOT_VOLUME_CREATING, 45, "부트 볼륨 생성 완료")

            # Step 3: Upper volume (45-60%)
            yield send_progress(ProgressStep.UPPER_VOLUME_CREATING, 45, "Upper 볼륨 생성 중...")
            upper_vol = await asyncio.to_thread(
                cinder.create_empty_volume,
                conn,
                name=f"union-upper-{req.name}",
                size_gb=settings.upper_volume_size_gb,
                availability_zone=req.availability_zone or settings.default_availability_zone,
            )
            upper_volume_id = upper_vol.id
            yield send_progress(ProgressStep.UPPER_VOLUME_CREATING, 60, "Upper 볼륨 생성 완료")

            # Step 4: cloud-init (60-65%)
            yield send_progress(ProgressStep.USERDATA_GENERATING, 60, "cloud-init 생성 중...")
            flavors = await asyncio.to_thread(nova.list_flavors, conn)
            flavor = next((f for f in flavors if f.id == req.flavor_id), None)
            gpu_available = flavor.has_gpu if flavor else False

            userdata = cloudinit.generate_userdata(
                libraries=resolved_libs,
                strategy=req.strategy,
                shares=shares_info,
                upper_device="/dev/vdb",
                ceph_monitors=settings.ceph_monitors,
                gpu_available=gpu_available,
            )
            yield send_progress(ProgressStep.USERDATA_GENERATING, 65, "cloud-init 생성 완료")

            # Step 5: Nova server (65-95%)
            yield send_progress(ProgressStep.SERVER_CREATING, 65, "Nova 서버 생성 중...")
            meta = {
                "union_libraries": ",".join(resolved_libs),
                "union_strategy": req.strategy,
                "union_share_ids": ",".join([s.get("share_id", "") for s in shares_info]),
                "union_upper_volume_id": upper_volume_id,
            }

            server = await asyncio.to_thread(
                nova.create_server,
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
            yield send_progress(ProgressStep.SERVER_CREATING, 95, "Nova 서버 생성 완료")

            # Step 6: Attach volume (95-100%)
            yield send_progress(ProgressStep.ATTACHING_VOLUME, 95, "볼륨 연결 중...")
            await asyncio.to_thread(
                conn.compute.create_volume_attachment,
                server_id, volume_id=upper_volume_id
            )
            yield send_progress(ProgressStep.ATTACHING_VOLUME, 100, "볼륨 연결 완료")

            # Step 7: Floating IP (tenant 네트워크 선택 시)
            if req.network_id:
                all_nets = await asyncio.to_thread(neutron.list_networks, conn)
                selected_net = next((n for n in all_nets if n.id == req.network_id), None)
                if selected_net and not selected_net.is_external:
                    ext_net = next((n for n in all_nets if n.is_external), None)
                    if ext_net:
                        yield send_progress(ProgressStep.FLOATING_IP_CREATING, 100, "Floating IP 할당 중...")
                        fip = await asyncio.to_thread(neutron.create_floating_ip, conn, ext_net.id)
                        floating_ip_id = fip.id
                        await asyncio.to_thread(neutron.associate_floating_ip, conn, fip.id, server_id)
                        yield send_progress(ProgressStep.FLOATING_IP_CREATING, 100, "Floating IP 할당 완료")

            # Completed
            yield send_progress(
                ProgressStep.COMPLETED, 100, "인스턴스 생성 완료",
                instance_id=server_id
            )

        except Exception as e:
            logger.error(f"인스턴스 생성 실패, rollback 시작: {e}")
            yield send_progress(ProgressStep.FAILED, 0, f"인스턴스 생성 실패: {e}", error=str(e))
            await _rollback(conn, server_id, boot_volume_id, upper_volume_id,
                            created_share_ids, created_access_ids, floating_ip_id)

    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


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


@router.post("/{instance_id}/start", status_code=204)
async def start_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        nova.start_server(conn, instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/stop", status_code=204)
async def stop_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        nova.stop_server(conn, instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/reboot", status_code=204)
async def reboot_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        nova.reboot_server(conn, instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/{instance_id}/log")
async def get_console_log(
    instance_id: str,
    length: int = 100,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        output = nova.get_console_output(conn, instance_id, length)
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/interfaces")
async def list_interfaces(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return neutron.list_instance_ports(conn, instance_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/volumes")
async def list_instance_volumes(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        attachments = nova.list_volume_attachments(conn, instance_id)
        result = []
        for a in attachments:
            try:
                vol = cinder.get_volume(conn, a["volume_id"])
                result.append({**a, "name": vol.name, "size": vol.size, "status": vol.status})
            except Exception:
                result.append(a)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/volumes", status_code=201)
async def attach_volume_to_instance(
    instance_id: str,
    body: dict,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    volume_id = body.get("volume_id")
    if not volume_id:
        raise HTTPException(status_code=400, detail="volume_id 필요")
    try:
        return nova.attach_volume(conn, instance_id, volume_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}/volumes/{volume_id}", status_code=204)
async def detach_volume_from_instance(
    instance_id: str,
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        nova.detach_volume(conn, instance_id, volume_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/security-groups")
async def list_instance_security_groups(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        ports = neutron.list_instance_ports(conn, instance_id)
        all_sgs = neutron.list_security_groups(conn, project_id=conn._union_project_id)
        return {"ports": ports, "security_groups": all_sgs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{instance_id}/owner")
async def get_instance_owner(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        server = nova.get_server(conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")
    if not server.user_id:
        return {"display": "-"}
    try:
        user = keystone.get_user(conn, server.user_id)
        name = user["name"]
        email = user["email"]
        display = f"{name}({email})" if email else name
        return {"display": display, "name": name, "email": email}
    except Exception:
        return {"display": server.user_id}


@router.post("/{instance_id}/interfaces", status_code=201)
async def attach_interface(
    instance_id: str,
    body: dict,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    net_id = body.get("net_id")
    if not net_id:
        raise HTTPException(status_code=400, detail="net_id 필요")
    try:
        return nova.attach_interface(conn, instance_id, net_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{instance_id}/interfaces/{port_id}", status_code=204)
async def detach_interface(
    instance_id: str,
    port_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        nova.detach_interface(conn, instance_id, port_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{instance_id}/ports/{port_id}/security-groups")
async def update_port_security_groups(
    instance_id: str,
    port_id: str,
    body: dict,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    sg_ids = body.get("security_group_ids", [])
    try:
        return neutron.update_port_security_groups(conn, port_id, sg_ids)
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
    floating_ip_id: str | None = None,
):
    if floating_ip_id:
        try:
            neutron.delete_floating_ip(conn, floating_ip_id)
        except Exception as e:
            logger.error(f"Rollback - Floating IP 삭제 실패: {e}")

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
