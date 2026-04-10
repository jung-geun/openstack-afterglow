"""
인스턴스 오케스트레이션 엔드포인트.

생성 순서:
  1. Manila access rule(A) 또는 신규 파일 스토리지(B)
  2. Cinder 부트 볼륨
  3. Cinder upper 볼륨
  4. cloud-init userdata 생성
  5. Nova 서버 생성

실패 시 역순 rollback.
"""
import logging
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
import openstack

from app.api.deps import get_os_conn
from app.rate_limit import limiter
from app.config import get_settings
from app.models.compute import (
    CreateInstanceRequest, InstanceInfo,
    AttachVolumeRequest, AttachInterfaceRequest, UpdateSecurityGroupsRequest,
)
from app.models.progress import ProgressMessage, ProgressStep
from app.services import nova, cinder, manila, cloudinit, libraries as lib_svc, neutron, keystone, glance
from app.services.cache import cached_call, ttl_fast, ttl_normal, ttl_slow, ttl_static, invalidate

logger = logging.getLogger(__name__)
router = APIRouter()


def _resolve_names(servers: list, conn) -> list[dict]:
    """서버 목록에 flavor_name / image_name 을 resolve해서 반환."""
    flavors_by_id = {f.id: f.name for f in nova.list_flavors(conn)}
    images: dict = {}
    try:
        images = {img.id: img.name for img in glance.list_images(conn)}
    except Exception:
        pass
    result = []
    for s in servers:
        d = s.model_dump()
        # flavor_name: _server_to_info에서 original_name으로 이미 설정된 경우 유지,
        # 없으면 flavor_id로 lookup (구형 마이크로버전)
        if not d.get("flavor_name") and s.flavor_id:
            d["flavor_name"] = flavors_by_id.get(s.flavor_id)
        if s.image_id:
            d["image_name"] = images.get(s.image_id)
        else:
            image_name = None
            try:
                attachments = nova.list_volume_attachments(conn, s.id)
                boot_att = next((a for a in attachments if a.get("device") == "/dev/vda"), None)
                if boot_att:
                    meta = cinder.get_volume_image_metadata(conn, boot_att["volume_id"])
                    if meta:
                        image_name = meta.get("image_name")
            except Exception:
                pass
            d["image_name"] = image_name or "볼륨에서 부팅"
        result.append(d)
    return result


@router.get("", response_model=list[InstanceInfo])
async def list_instances(conn: openstack.connection.Connection = Depends(get_os_conn), refresh: bool = Query(False)):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:nova:{pid}:instances", ttl_fast(),
            lambda: _resolve_names(nova.list_servers(conn), conn),
            refresh=refresh,
        )
    except Exception as e:
        logger.error(f"인스턴스 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="인스턴스 목록 조회 실패")


@router.get("/{instance_id}", response_model=InstanceInfo)
async def get_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:nova:{pid}:instance:{instance_id}", ttl_fast(),
            lambda: _resolve_names([nova.get_server(conn, instance_id)], conn)[0]
        )
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")


@router.post("", response_model=InstanceInfo, status_code=201)
@limiter.limit("5/minute")
async def create_instance(
    request: Request,
    req: CreateInstanceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """동기식 인스턴스 생성 (기존 방식)."""
    settings = get_settings()
    resolved_libs = lib_svc.resolve_with_deps(req.libraries)

    # 수집된 리소스 (rollback 용)
    created_file_storage_ids: list[str] = []
    created_access_ids: list[tuple[str, str]] = []   # (file_storage_id, access_id)
    boot_volume_id: str | None = None
    upper_volume_id: str | None = None
    server_id: str | None = None
    floating_ip_id: str | None = None

    try:
        # ------------------------------------------------------------------
        # 1. Manila: 파일 스토리지 및 access rule 준비
        # ------------------------------------------------------------------
        file_storages_info = []  # cloud-init 에 전달할 파일 스토리지 정보 목록

        if req.strategy == "prebuilt":
            file_storages_info = await _prepare_prebuilt_file_storages(
                conn, resolved_libs, req.name, created_access_ids
            )
        else:
            file_storage_info = await _prepare_dynamic_file_storage(
                conn, req.name, resolved_libs, settings, created_file_storage_ids, created_access_ids
            )
            file_storages_info = [file_storage_info]

        # ------------------------------------------------------------------
        # 2. Cinder: 부트 볼륨 생성
        # ------------------------------------------------------------------
        boot_vol = await asyncio.to_thread(
            cinder.create_volume_from_image,
            conn,
            f"{req.name}-boot",
            req.image_id,
            req.boot_volume_size_gb or settings.boot_volume_size_gb,
            req.availability_zone or settings.default_availability_zone,
        )
        boot_volume_id = boot_vol.id
        await asyncio.to_thread(
            cinder.rename_volume, conn, boot_volume_id,
            f"{req.name}-boot-{boot_volume_id[:8]}"
        )

        # ------------------------------------------------------------------
        # 3. Cinder: upper 볼륨 생성 (OverlayFS upperdir)
        # ------------------------------------------------------------------
        upper_vol = await asyncio.to_thread(
            cinder.create_empty_volume,
            conn,
            f"union-upper-{req.name}",
            settings.upper_volume_size_gb,
            req.availability_zone or settings.default_availability_zone,
        )
        upper_volume_id = upper_vol.id

        # ------------------------------------------------------------------
        # 4. cloud-init userdata 생성
        # ------------------------------------------------------------------
        # GPU 플레이버 여부 확인
        flavors = await asyncio.to_thread(nova.list_flavors, conn)
        flavor = next((f for f in flavors if f.id == req.flavor_id), None)
        gpu_available = flavor.is_gpu if flavor else False

        userdata = cloudinit.generate_userdata(
            libraries=resolved_libs,
            strategy=req.strategy,
            file_storages=file_storages_info,
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
                [s.get("file_storage_id", "") for s in file_storages_info]
            ),
            "union_upper_volume_id": upper_volume_id,
        }

        # upper 볼륨을 두 번째 블록 디바이스로 추가
        # (Nova block_device_mapping_v2 에 추가 볼륨 연결)
        server = await asyncio.to_thread(
            nova.create_server,
            conn,
            req.name,
            req.flavor_id,
            req.network_id or settings.default_network_id,
            boot_volume_id,
            userdata,
            req.key_name,
            req.admin_pass,
            req.availability_zone or settings.default_availability_zone,
            meta,
            req.delete_boot_volume_on_termination,
        )
        server_id = server.id

        # upper 볼륨 attach (서버 생성 후)
        await asyncio.to_thread(
            conn.compute.create_volume_attachment,
            server_id, volume_id=upper_volume_id,
        )

        # Floating IP 자동 생성 (tenant 네트워크 선택 시)
        if req.network_id:
            all_nets = await asyncio.to_thread(neutron.list_networks, conn)
            selected_net = next((n for n in all_nets if n.id == req.network_id), None)
            if selected_net and not selected_net.is_external:
                ext_net = next((n for n in all_nets if n.is_external), None)
                if ext_net:
                    fip = await asyncio.to_thread(neutron.create_floating_ip, conn, ext_net.id)
                    floating_ip_id = fip.id
                    await asyncio.to_thread(neutron.associate_floating_ip, conn, fip.id, server_id)

        return server

    except Exception as e:
        logger.error(f"인스턴스 생성 실패, rollback 시작: {e}")
        await _rollback(conn, server_id, boot_volume_id, upper_volume_id,
                        created_file_storage_ids, created_access_ids, floating_ip_id)
        raise HTTPException(status_code=500, detail="인스턴스 생성 실패")


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
        created_file_storage_ids: list[str] = []
        created_access_ids: list[tuple[str, str]] = []
        boot_volume_id: str | None = None
        upper_volume_id: str | None = None
        server_id: str | None = None
        floating_ip_id: str | None = None

        def send_progress(step: ProgressStep, progress: int, message: str, **extra):
            msg = ProgressMessage(step=step, progress=progress, message=message, **extra)
            return f"data: {msg.model_dump_json()}\n\n"

        try:
            file_storages_info = []
            userdata = None

            if resolved_libs:
                # Step 1: Manila 파일 스토리지 (0-20%)
                yield send_progress(ProgressStep.MANILA_PREPARING, 0, "파일 스토리지 준비 중...")
                if req.strategy == "prebuilt":
                    file_storages_info = await _prepare_prebuilt_file_storages(
                        conn, resolved_libs, req.name, created_access_ids
                    )
                else:
                    file_storage_info = await _prepare_dynamic_file_storage(
                        conn, req.name, resolved_libs, settings, created_file_storage_ids, created_access_ids
                    )
                    file_storages_info = [file_storage_info]
                yield send_progress(ProgressStep.MANILA_PREPARING, 20, "파일 스토리지 준비 완료")

            # Step 2: Boot volume (20-45%)
            yield send_progress(ProgressStep.BOOT_VOLUME_CREATING, 20, "부트 볼륨 생성 중...")
            boot_vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn,
                name=f"{req.name}-boot",
                image_id=req.image_id,
                size_gb=req.boot_volume_size_gb or settings.boot_volume_size_gb,
                availability_zone=req.availability_zone or settings.default_availability_zone,
            )
            boot_volume_id = boot_vol.id
            await asyncio.to_thread(
                cinder.rename_volume, conn, boot_volume_id,
                f"{req.name}-boot-{boot_volume_id[:8]}"
            )
            yield send_progress(ProgressStep.BOOT_VOLUME_CREATING, 45, "부트 볼륨 생성 완료")

            if resolved_libs:
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
                gpu_available = flavor.is_gpu if flavor else False

                userdata = cloudinit.generate_userdata(
                    libraries=resolved_libs,
                    strategy=req.strategy,
                    file_storages=file_storages_info,
                    upper_device="/dev/vdb",
                    ceph_monitors=settings.ceph_monitors,
                    gpu_available=gpu_available,
                )
                yield send_progress(ProgressStep.USERDATA_GENERATING, 65, "cloud-init 생성 완료")

            # Step 5: Nova server (65-95%)
            yield send_progress(ProgressStep.SERVER_CREATING, 65, "Nova 서버 생성 중...")
            meta = {
                "union_libraries": ",".join(resolved_libs) if resolved_libs else "none",
                "union_strategy": req.strategy or "none",
                "union_share_ids": ",".join([s.get("file_storage_id", "") for s in file_storages_info]) if file_storages_info else "none",
                "union_upper_volume_id": upper_volume_id or "none",
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
                admin_pass=req.admin_pass,
                availability_zone=req.availability_zone or settings.default_availability_zone,
                metadata=meta,
                delete_boot_volume_on_termination=req.delete_boot_volume_on_termination,
            )
            server_id = server.id
            yield send_progress(ProgressStep.SERVER_CREATING, 95, "Nova 서버 생성 완료")

            # Step 6: Attach volumes (95-100%)
            yield send_progress(ProgressStep.ATTACHING_VOLUME, 95, "볼륨 연결 중...")
            if upper_volume_id:
                await asyncio.to_thread(
                    conn.compute.create_volume_attachment,
                    server_id, volume_id=upper_volume_id
                )
            # 새 볼륨 생성 후 연결
            for nv in (req.new_volumes or []):
                nv_name = nv.name
                nv_size = nv.size_gb
                if not nv_name:
                    continue
                new_vol = await asyncio.to_thread(
                    cinder.create_empty_volume, conn, nv_name, nv_size
                )
                await asyncio.to_thread(
                    conn.compute.create_volume_attachment,
                    server_id, volume_id=new_vol.id
                )
            # 추가 볼륨 연결
            for vol_id in (req.additional_volume_ids or []):
                await asyncio.to_thread(
                    conn.compute.create_volume_attachment,
                    server_id, volume_id=vol_id
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
            yield send_progress(ProgressStep.FAILED, 0, "인스턴스 생성에 실패했습니다. 잠시 후 다시 시도해 주세요.", error="인스턴스 생성 실패")
            await _rollback(conn, server_id, boot_volume_id, upper_volume_id,
                            created_file_storage_ids, created_access_ids, floating_ip_id)

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
    pid = conn._union_project_id
    try:
        server = await asyncio.to_thread(nova.get_server, conn, instance_id)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")

    upper_volume_id = server.union_upper_volume_id
    file_storage_ids = server.union_share_ids
    strategy = server.union_strategy

    # Nova 서버 삭제
    await asyncio.to_thread(nova.delete_server, conn, instance_id)
    await invalidate(f"union:nova:{pid}:instances")
    await invalidate(f"union:nova:{pid}:instance:{instance_id}")

    # Strategy B: 전용 파일 스토리지 삭제
    if strategy == "dynamic":
        for file_storage_id in file_storage_ids:
            if file_storage_id:
                try:
                    await asyncio.to_thread(manila.delete_file_storage, conn, file_storage_id)
                except Exception as ex:
                    logger.warning(f"파일 스토리지 삭제 실패 {file_storage_id}: {ex}")

    # upper 볼륨 삭제
    if upper_volume_id:
        try:
            await asyncio.to_thread(cinder.delete_volume, conn, upper_volume_id)
        except Exception as ex:
            logger.warning(f"Upper 볼륨 삭제 실패: {ex}")


@router.post("/{instance_id}/start", status_code=204)
async def start_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.start_server, conn, instance_id)
        await invalidate(f"union:nova:{pid}:instance:{instance_id}")
        await invalidate(f"union:nova:{pid}:instances")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/stop", status_code=204)
async def stop_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.stop_server, conn, instance_id)
        await invalidate(f"union:nova:{pid}:instance:{instance_id}")
        await invalidate(f"union:nova:{pid}:instances")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/reboot", status_code=204)
async def reboot_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.reboot_server, conn, instance_id)
        await invalidate(f"union:nova:{pid}:instance:{instance_id}")
        await invalidate(f"union:nova:{pid}:instances")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/shelve", status_code=204)
async def shelve_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.shelve_server, conn, instance_id)
        await invalidate(f"union:nova:{pid}:instance:{instance_id}")
        await invalidate(f"union:nova:{pid}:instances")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/unshelve", status_code=204)
async def unshelve_instance(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.unshelve_server, conn, instance_id)
        await invalidate(f"union:nova:{pid}:instance:{instance_id}")
        await invalidate(f"union:nova:{pid}:instances")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/console")
async def get_console(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        url = await asyncio.to_thread(nova.get_console_url, conn, instance_id)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/log")
async def get_console_log(
    instance_id: str,
    length: int = Query(default=100, ge=1, le=10000),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        output = await asyncio.to_thread(nova.get_console_output, conn, instance_id, length)
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/interfaces")
async def list_interfaces(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        return await cached_call(
            f"union:neutron:{pid}:ports:{instance_id}", ttl_normal(),
            lambda: neutron.list_instance_ports(conn, instance_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/volumes")
async def list_instance_volumes(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id

    def _fetch():
        attachments = nova.list_volume_attachments(conn, instance_id)
        result = []
        for a in attachments:
            try:
                vol = cinder.get_volume(conn, a["volume_id"])
                result.append({**a, "name": vol.name, "size": vol.size, "status": vol.status})
            except Exception:
                result.append(a)
        return result

    try:
        return await cached_call(f"union:cinder:{pid}:vol_attach:{instance_id}", ttl_normal(), _fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/volumes", status_code=201)
async def attach_volume_to_instance(
    instance_id: str,
    body: AttachVolumeRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    volume_id = body.volume_id
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(nova.attach_volume, conn, instance_id, volume_id)
        await invalidate(f"union:cinder:{pid}:vol_attach:{instance_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.delete("/{instance_id}/volumes/{volume_id}", status_code=204)
async def detach_volume_from_instance(
    instance_id: str,
    volume_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.detach_volume, conn, instance_id, volume_id)
        await invalidate(f"union:cinder:{pid}:vol_attach:{instance_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/security-groups")
async def list_instance_security_groups(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id

    def _fetch():
        ports = neutron.list_instance_ports(conn, instance_id)
        all_sgs = neutron.list_security_groups(conn, project_id=pid)
        return {"ports": ports, "security_groups": all_sgs}

    try:
        return await cached_call(f"union:neutron:{pid}:sgs:{instance_id}", ttl_slow(), _fetch)
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.get("/{instance_id}/owner")
async def get_instance_owner(
    instance_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id

    def _fetch():
        server = nova.get_server(conn, instance_id)
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

    try:
        return await cached_call(f"union:keystone:{pid}:owner:{instance_id}", ttl_static(), _fetch)
    except Exception:
        raise HTTPException(status_code=404, detail="인스턴스를 찾을 수 없습니다")


@router.post("/{instance_id}/interfaces", status_code=201)
async def attach_interface(
    instance_id: str,
    body: AttachInterfaceRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    net_id = body.net_id
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(nova.attach_interface, conn, instance_id, net_id)
        await invalidate(f"union:neutron:{pid}:ports:{instance_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.delete("/{instance_id}/interfaces/{port_id}", status_code=204)
async def detach_interface(
    instance_id: str,
    port_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    pid = conn._union_project_id
    try:
        await asyncio.to_thread(nova.detach_interface, conn, instance_id, port_id)
        await invalidate(f"union:neutron:{pid}:ports:{instance_id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


@router.post("/{instance_id}/ports/{port_id}/security-groups")
async def update_port_security_groups(
    instance_id: str,
    port_id: str,
    body: UpdateSecurityGroupsRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    sg_ids = body.security_group_ids
    pid = conn._union_project_id
    try:
        result = await asyncio.to_thread(neutron.update_port_security_groups, conn, port_id, sg_ids)
        await invalidate(f"union:neutron:{pid}:sgs:{instance_id}")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail="작업 실패")


# ---------------------------------------------------------------------------
# 내부 헬퍼
# ---------------------------------------------------------------------------

async def _prepare_prebuilt_file_storages(
    conn, resolved_libs: list[str], instance_name: str,
    created_access_ids: list
) -> list[dict]:
    """Strategy A: 사전 빌드된 read-only 파일 스토리지에 access rule 추가."""
    prebuilt_file_storages = await asyncio.to_thread(
        manila.list_file_storages, conn, {"union_type": "prebuilt"}
    )
    prebuilt_map = {s.library_name: s for s in prebuilt_file_storages}

    file_storages_info = []
    for lib_id in list(reversed(resolved_libs)):
        file_storage = prebuilt_map.get(lib_id)
        if not file_storage:
            raise RuntimeError(f"사전 빌드 파일 스토리지 없음: {lib_id}. Strategy B를 사용하거나 관리자에게 문의하세요.")

        cephx_id = f"union-ro-{instance_name}-{lib_id}"
        rule = await asyncio.to_thread(manila.create_access_rule, conn, file_storage.id, cephx_id, "ro")
        created_access_ids.append((file_storage.id, rule["access_id"]))

        export_paths = await asyncio.to_thread(manila.get_export_locations, conn, file_storage.id)
        file_storages_info.append({
            "file_storage_id": file_storage.id,
            "name": lib_id,
            "export_path": export_paths[0] if export_paths else "",
            "cephx_id": cephx_id,
            "cephx_key": rule["access_key"],
        })
    return file_storages_info


async def _prepare_dynamic_file_storage(
    conn, instance_name: str, resolved_libs: list[str],
    settings, created_file_storage_ids: list, created_access_ids: list,
    share_proto: str = "CEPHFS", vm_ip_address: str = "",
) -> dict:
    """Strategy B: VM 전용 read-write 파일 스토리지 신규 생성.
    
    share_proto에 따라 CephFS 또는 NFS share를 생성한다.
    """
    # 프로토콜에 따른 share type 선택
    if share_proto.upper() == "NFS":
        share_type = settings.os_manila_nfs_share_type
    else:
        share_type = settings.os_manila_share_type

    file_storage = await asyncio.to_thread(
        manila.create_file_storage,
        conn,
        f"union-dyn-{instance_name}",
        settings.upper_volume_size_gb,
        settings.os_manila_share_network_id,
        share_type,
        share_proto,
        {
            "union_type": "dynamic",
            "union_instance": instance_name,
            "union_libraries": ",".join(resolved_libs),
            "union_share_proto": share_proto.upper(),
        },
    )
    created_file_storage_ids.append(file_storage.id)

    if share_proto.upper() == "NFS":
        # NFS: IP 기반 access rule
        access_to = vm_ip_address if vm_ip_address else "0.0.0.0/0"
        rule = await asyncio.to_thread(
            manila.ensure_nfs_access_rule,
            conn, file_storage.id, access_to, "rw",
        )
        created_access_ids.append((file_storage.id, rule["access_id"]))

        nfs_export = file_storage.nfs_export_location
        if not nfs_export:
            export_paths = await asyncio.to_thread(manila.get_export_locations, conn, file_storage.id)
            nfs_export = export_paths[0] if export_paths else ""

        return {
            "file_storage_id": file_storage.id,
            "name": "dynamic",
            "share_proto": "NFS",
            "export_path": "",
            "cephx_id": "",
            "cephx_key": "",
            "nfs_export_location": nfs_export,
            "mount_options": "hard,intr,noatime,_netdev,timeo=10,retrans=3",
        }
    else:
        # CephFS: CephX access rule (기존 로직)
        cephx_id = f"union-rw-{instance_name}"
        rule = await asyncio.to_thread(manila.create_access_rule, conn, file_storage.id, cephx_id, "rw")
        created_access_ids.append((file_storage.id, rule["access_id"]))

        export_paths = await asyncio.to_thread(manila.get_export_locations, conn, file_storage.id)
        return {
            "file_storage_id": file_storage.id,
            "name": "dynamic",
            "share_proto": "CEPHFS",
            "export_path": export_paths[0] if export_paths else "",
            "cephx_id": cephx_id,
            "cephx_key": rule["access_key"],
            "nfs_export_location": "",
            "mount_options": "",
        }


async def _rollback(
    conn,
    server_id: str | None,
    boot_volume_id: str | None,
    upper_volume_id: str | None,
    file_storage_ids: list[str],
    access_ids: list[tuple[str, str]],
    floating_ip_id: str | None = None,
):
    if floating_ip_id:
        try:
            await asyncio.to_thread(neutron.delete_floating_ip, conn, floating_ip_id)
        except Exception as e:
            logger.error(f"Rollback - Floating IP 삭제 실패: {e}")

    if server_id:
        try:
            await asyncio.to_thread(nova.delete_server, conn, server_id)
        except Exception as e:
            logger.error(f"Rollback - 서버 삭제 실패: {e}")

    for vol_id in [boot_volume_id, upper_volume_id]:
        if vol_id:
            try:
                await asyncio.to_thread(cinder.delete_volume, conn, vol_id)
            except Exception as e:
                logger.error(f"Rollback - 볼륨 삭제 실패 {vol_id}: {e}")

    for file_storage_id, access_id in access_ids:
        try:
            await asyncio.to_thread(manila.revoke_access_rule, conn, file_storage_id, access_id)
        except Exception as e:
            logger.error(f"Rollback - access rule 삭제 실패: {e}")

    for file_storage_id in file_storage_ids:
        try:
            await asyncio.to_thread(manila.delete_file_storage, conn, file_storage_id)
        except Exception as e:
            logger.error(f"Rollback - 파일 스토리지 삭제 실패 {file_storage_id}: {e}")
