"""k3s 클러스터 CRUD + SSE 생성 엔드포인트."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import openstack
import asyncio
import logging
import random
import string
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.requests import Request

from app.api.deps import get_os_conn, get_token_info
from app.config import get_settings
from app.database import mark_db_unhealthy
from app.models.k3s import (
    CreateK3sClusterRequest,
    K3sClusterInfo,
    K3sProgressMessage,
    K3sProgressStep,
    ScaleK3sClusterRequest,
)
from app.services import cinder, k3s_cloudinit, k3s_kube, keystone, neutron, nova, octavia
from app.services import k3s_db as k3s_cluster

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_logger = logging.getLogger(__name__)


def _rand_suffix(length: int = 5) -> str:
    """K8s 스타일 랜덤 suffix (소문자+숫자). 매 생성마다 고유한 리소스 이름 보장."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _cluster_to_info(c: dict) -> K3sClusterInfo:
    agent_vm_ids = c.get("agent_vm_ids") or []
    if isinstance(agent_vm_ids, str):
        import json

        try:
            agent_vm_ids = json.loads(agent_vm_ids)
        except Exception:
            agent_vm_ids = []
    return K3sClusterInfo(
        id=c.get("id", ""),
        name=c.get("name", ""),
        status=c.get("status", ""),
        status_reason=c.get("status_reason") or None,
        server_vm_id=c.get("server_vm_id") or None,
        agent_vm_ids=agent_vm_ids,
        agent_count=int(c.get("agent_count") or 0),
        api_address=c.get("api_address") or None,
        server_ip=c.get("server_ip") or None,
        network_id=c.get("network_id") or None,
        key_name=c.get("key_name") or None,
        k3s_version=c.get("k3s_version") or None,
        created_at=c.get("created_at") or None,
        updated_at=c.get("updated_at") or None,
        deleted_at=c.get("deleted_at") or None,
        deleted_by_user_id=c.get("deleted_by_user_id") or None,
        deleted_reason=c.get("deleted_reason") or None,
        occm_enabled=bool(c.get("occm_enabled", False)),
        plugins_enabled=c.get("plugins_enabled") or {},
        api_lb_id=c.get("api_lb_id") or None,
        api_fip_id=c.get("api_fip_id") or None,
        api_fip_address=c.get("api_fip_address") or None,
    )


@router.get("", response_model=list[K3sClusterInfo])
async def list_k3s_clusters(
    token_info: dict = Depends(get_token_info),
    include_deleted: bool = Query(default=False),
):
    project_id = token_info["project_id"]
    try:
        clusters = await k3s_cluster.list_clusters(project_id, include_deleted=include_deleted)
    except (OperationalError, InterfaceError):
        _logger.warning("k3s 클러스터 목록 DB 조회 실패 — 빈 목록 반환", exc_info=True)
        mark_db_unhealthy()
        return []
    return [_cluster_to_info(c) for c in clusters]


@router.get("/{cluster_id}", response_model=K3sClusterInfo)
async def get_k3s_cluster(cluster_id: str, token_info: dict = Depends(get_token_info)):
    project_id = token_info["project_id"]
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    return _cluster_to_info(cluster)


@router.api_route("/{cluster_id}/kubeconfig", methods=["GET", "HEAD"])
async def download_kubeconfig(cluster_id: str, token_info: dict = Depends(get_token_info)):
    """kubeconfig YAML 파일 다운로드. 아직 준비되지 않으면 404."""
    project_id = token_info["project_id"]
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    try:
        kubeconfig = await k3s_cluster.get_kubeconfig(project_id, cluster_id)
    except Exception as e:
        _logger.error("kubeconfig 복호화 실패: %s", e)
        raise HTTPException(status_code=500, detail="kubeconfig 복호화에 실패했습니다. 관리자에게 문의하세요.")
    if not kubeconfig:
        raise HTTPException(
            status_code=404, detail="kubeconfig가 아직 준비되지 않았습니다. 클러스터가 초기화 중입니다."
        )

    cluster_name = cluster.get("name", cluster_id)
    return Response(
        content=kubeconfig,
        media_type="application/yaml",
        headers={"Content-Disposition": f'attachment; filename="kubeconfig-{cluster_name}.yaml"'},
    )


@router.post("/async")
@limiter.limit("5/minute")
async def create_k3s_cluster_async(
    request: Request,
    req: CreateK3sClusterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    """k3s 클러스터 생성 — SSE 스트리밍 진행률 반환."""
    token_info_obj = getattr(request.state, "token_info", None)
    project_id = conn._afterglow_project_id
    s = get_settings()

    # 설정 검증
    os_type = req.os_type  # "ubuntu" | "fcos"
    if os_type == "fcos":
        server_image_id = s.k3s_fcos_image_id
        if not server_image_id:
            raise HTTPException(
                status_code=503, detail="FCOS 이미지가 설정되지 않았습니다 (k3s_fcos_image_id). 관리자에게 문의하세요."
            )
    else:
        server_image_id = s.k3s_server_image_id
    server_flavor_id = s.k3s_server_flavor_id
    if not server_image_id or not server_flavor_id:
        raise HTTPException(
            status_code=503, detail="k3s 서버 이미지 또는 플레이버가 설정되지 않았습니다. 관리자에게 문의하세요."
        )

    agent_flavor_id = req.agent_flavor_id or s.k3s_default_agent_flavor_id
    if req.agent_count > 0 and not agent_flavor_id:
        raise HTTPException(status_code=503, detail="에이전트 플레이버가 설정되지 않았습니다. 관리자에게 문의하세요.")

    # Default 네트워크 결정
    network_id = req.network_id
    if not network_id:
        if s.default_network_enabled:
            try:
                from app.services.default_network import ensure_default_network as _ensure_net

                default_net = await _ensure_net(
                    conn,
                    project_id,
                    external_network_id=s.default_network_external_id or None,
                    cidr=s.default_network_cidr,
                )
                network_id = default_net.id
            except Exception:
                import logging as _log

                _log.getLogger(__name__).warning("Default 네트워크 조회 실패, 설정값 폴백", exc_info=True)
                network_id = s.default_network_id
        else:
            network_id = s.default_network_id

    k3s_version = s.k3s_version
    boot_volume_size = s.k3s_boot_volume_size_gb
    cluster_id = str(uuid.uuid4())

    # flavor 이름 → ID 해석 (이름으로 설정된 경우)
    def _resolve_flavor(conn_obj, flavor_ref: str) -> str:
        if not flavor_ref:
            return flavor_ref
        try:
            f = conn_obj.compute.find_flavor(flavor_ref)
            return f.id if f else flavor_ref
        except Exception:
            return flavor_ref

    server_flavor_id = _resolve_flavor(conn, server_flavor_id)
    if agent_flavor_id:
        agent_flavor_id = _resolve_flavor(conn, agent_flavor_id)

    async def progress_generator() -> AsyncGenerator[str, None]:
        _start_time = time.monotonic()

        def event(step: K3sProgressStep, progress: int, message: str, **kw) -> str:
            elapsed = round(time.monotonic() - _start_time, 1)
            msg = K3sProgressMessage(step=step, progress=progress, message=message, elapsed_seconds=elapsed, **kw)
            return f"data: {msg.model_dump_json()}\n\n"

        # 프록시/CDN 버퍼 우회: 첫 chunk를 즉시 flush하기 위한 SSE 주석 패딩
        yield ": " + " " * 2048 + "\n\n"

        # 롤백 추적
        sg_id: str | None = None
        boot_volume_id: str | None = None
        server_vm_id: str | None = None

        try:
            # --- Step 1: 보안 그룹 생성 ---
            yield event(K3sProgressStep.SECURITY_GROUP, 5, "k3s 보안 그룹 생성 중...")
            sg_name = f"k3s-{req.name}-{cluster_id[:8]}"
            sg = await asyncio.to_thread(
                neutron.create_security_group, conn, sg_name, f"k3s cluster {req.name} security group"
            )
            sg_id = sg["id"]

            # 보안 그룹 규칙 추가
            # SSH/K3s API는 allowed_cidrs가 있으면 해당 CIDR만, 없으면 0.0.0.0/0 허용
            mgmt_cidrs = req.allowed_cidrs or ["0.0.0.0/0"]
            rules = []
            for cidr in mgmt_cidrs:
                # SSH
                rules.append(
                    dict(
                        direction="ingress", protocol="tcp", port_range_min=22, port_range_max=22, remote_ip_prefix=cidr
                    )
                )
                # k3s API server
                rules.append(
                    dict(
                        direction="ingress",
                        protocol="tcp",
                        port_range_min=6443,
                        port_range_max=6443,
                        remote_ip_prefix=cidr,
                    )
                )
            rules += [
                # Kubelet (SG 내부)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=10250,
                    port_range_max=10250,
                    remote_group_id=sg_id,
                ),
                # VXLAN (SG 내부)
                dict(
                    direction="ingress", protocol="udp", port_range_min=8472, port_range_max=8472, remote_group_id=sg_id
                ),
                # WireGuard (SG 내부)
                dict(
                    direction="ingress",
                    protocol="udp",
                    port_range_min=51820,
                    port_range_max=51820,
                    remote_group_id=sg_id,
                ),
                # HTTP (Traefik)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=80,
                    port_range_max=80,
                    remote_ip_prefix="0.0.0.0/0",
                ),
                # HTTPS (Traefik)
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=443,
                    port_range_max=443,
                    remote_ip_prefix="0.0.0.0/0",
                ),
                # NodePort
                dict(
                    direction="ingress",
                    protocol="tcp",
                    port_range_min=30000,
                    port_range_max=32767,
                    remote_ip_prefix="0.0.0.0/0",
                ),
            ]
            for rule_kwargs in rules:
                await asyncio.to_thread(neutron.create_security_group_rule, conn, sg_id, **rule_kwargs)
            yield event(K3sProgressStep.SECURITY_GROUP, 10, "보안 그룹 생성 완료")

            extra_tls_sans: list[str] = []

            # --- Step 2: 서버 부트 볼륨 생성 ---
            # K8s 스타일: 매 생성마다 고유한 suffix로 이름 충돌 방지
            server_suffix = _rand_suffix()
            server_vm_name = f"{req.name}-{server_suffix}"
            yield event(K3sProgressStep.SERVER_VOLUME, 28, "서버 노드 부트 볼륨 생성 중...")
            boot_vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn,
                f"{server_vm_name}-boot",
                server_image_id,
                boot_volume_size,
            )
            boot_volume_id = boot_vol.id
            yield event(K3sProgressStep.SERVER_VOLUME, 35, "서버 부트 볼륨 생성 완료")

            # --- Step 3: 콜백 토큰 + cloud-init 생성 ---
            yield event(K3sProgressStep.SERVER_CREATING, 40, "서버 VM cloud-init 생성 중...")
            # 공개키 미리 조회 (에이전트 VM은 admin conn으로 생성하므로 cloud-init에 직접 주입)
            ssh_public_key = ""
            if req.key_name:
                try:
                    kp = await asyncio.to_thread(conn.compute.find_keypair, req.key_name)
                    if kp:
                        ssh_public_key = kp.public_key or ""
                except Exception:
                    pass
            callback_token = await k3s_cluster.create_callback_token(project_id, cluster_id)
            callback_url = s.k3s_callback_base_url.rstrip("/")

            # 플러그인 레지스트리로 활성 플러그인 집계
            from app.services import k3s_plugins

            cloud_conf = k3s_plugins.aggregate_cloud_conf(project_id, s)
            plugin_manifests, manifest_failures = k3s_plugins.aggregate_manifests(req.name, project_id, s)
            if manifest_failures:
                err_msg = f"플러그인 매니페스트 생성 실패: {', '.join(manifest_failures)}"
                _logger.error("k3s cluster %s: %s", cluster_id, err_msg)
                yield event(K3sProgressStep.FAILED, 0, err_msg, cluster_id=cluster_id)
                return
            extra_server_args = k3s_plugins.aggregate_server_args(s)
            extra_write_files = k3s_plugins.aggregate_extra_write_files(project_id, req.name, s)
            active_plugins = k3s_plugins.get_active_plugin_names(s)
            occm_active = active_plugins.get("occm", False)

            userdata_result = k3s_cloudinit.generate_server_userdata(
                cluster_name=req.name,
                k3s_version=k3s_version,
                callback_url=callback_url,
                callback_token=callback_token,
                cloud_conf=cloud_conf,
                plugin_manifests=plugin_manifests,
                extra_server_args=extra_server_args,
                extra_write_files=extra_write_files,
                extra_tls_sans=extra_tls_sans,
                needs_external_cloud_provider=k3s_plugins.needs_external_cloud_provider(s),
                os_type=os_type,
                server_node_name=server_vm_name,
            )

            # --- Step 4: 서버 VM 생성 ---
            yield event(K3sProgressStep.SERVER_CREATING, 48, "서버 VM 생성 중 (완료까지 수 분 소요)...")
            server_vm = await asyncio.to_thread(
                nova.create_server,
                conn,
                server_vm_name,
                server_flavor_id,
                network_id,
                boot_volume_id,
                userdata=userdata_result.data,
                key_name=req.key_name,
                metadata={
                    "k3s_horse_generator_role": "k3s_server",
                    "k3s_horse_generator_cluster_id": cluster_id,
                    "k3s_horse_generator_cluster_name": req.name,
                },
                delete_boot_volume_on_termination=True,
                security_groups=[sg_id],
                config_drive=userdata_result.config_drive,
            )
            server_vm_id = server_vm.id
            yield event(K3sProgressStep.SERVER_CREATING, 60, f"서버 VM 생성 완료: {server_vm_id}")

            # --- Step 5: Redis에 클러스터 레코드 저장 ---
            yield event(K3sProgressStep.WAITING_CALLBACK, 65, "k3s 초기화 대기 중 (서버 VM에서 k3s 설치 중)...")
            now = datetime.now(UTC).isoformat()
            # 생성자 정보 추출
            _creator_user_id = conn._afterglow_user_id if hasattr(conn, "_afterglow_user_id") else None
            _creator_username = None
            if token_info_obj and isinstance(token_info_obj, dict):
                _creator_user_id = _creator_user_id or token_info_obj.get("user_id")
                _creator_username = token_info_obj.get("username")
            await k3s_cluster.create_cluster_record(
                project_id,
                cluster_id,
                {
                    "name": req.name,
                    "status": "CREATING",
                    "status_reason": "",
                    "server_vm_id": server_vm_id,
                    "agent_vm_ids": [],
                    "agent_count": req.agent_count,
                    "server_flavor_id": server_flavor_id,
                    "agent_flavor_id": agent_flavor_id,
                    "network_id": network_id,
                    "security_group_id": sg_id,
                    "server_ip": "",
                    "api_address": "",
                    "key_name": req.key_name or "",
                    "ssh_public_key": ssh_public_key,
                    "k3s_version": k3s_version,
                    "occm_enabled": occm_active,
                    "plugins_enabled": active_plugins,
                    "created_by_user_id": _creator_user_id or "",
                    "created_by_username": _creator_username or "",
                    "created_at": now,
                    "updated_at": now,
                    "api_lb_id": "",
                    "api_lb_pool_id": "",
                    "api_fip_id": "",
                    "api_fip_address": "",
                    "os_type": os_type,
                    "server_vm_name": server_vm_name,
                },
            )

            yield event(
                K3sProgressStep.COMPLETED,
                100,
                f"클러스터 생성 요청 완료. 서버 VM이 k3s를 설치한 후 에이전트 {req.agent_count}개가 자동으로 생성됩니다.",
                cluster_id=cluster_id,
            )

        except Exception as e:
            _logger.error("k3s cluster creation failed: %s", e, exc_info=True)
            yield event(K3sProgressStep.FAILED, 0, f"클러스터 생성 실패: {e}", error=str(e))
            # 롤백
            await _rollback(conn, server_vm_id, boot_volume_id, sg_id)

    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Encoding": "identity",
        },
    )


async def _rollback(
    conn: openstack.connection.Connection,
    server_vm_id: str | None,
    boot_volume_id: str | None,
    sg_id: str | None,
) -> None:
    """생성 실패 시 리소스 역순 삭제."""
    if server_vm_id:
        try:
            await asyncio.to_thread(nova.delete_server, conn, server_vm_id)
        except Exception as e:
            _logger.warning("Rollback: delete server %s failed: %s", server_vm_id, e)
    if boot_volume_id:
        try:
            await asyncio.sleep(3)
            await asyncio.to_thread(cinder.delete_volume, conn, boot_volume_id)
        except Exception as e:
            _logger.warning("Rollback: delete volume %s failed: %s", boot_volume_id, e)
    if sg_id:
        try:
            await asyncio.to_thread(neutron.delete_security_group, conn, sg_id)
        except Exception as e:
            _logger.warning("Rollback: delete SG %s failed: %s", sg_id, e)


@router.patch("/{cluster_id}/scale")
async def scale_k3s_cluster(
    cluster_id: str,
    req: ScaleK3sClusterRequest,
    token_info: dict = Depends(get_token_info),
):
    """에이전트 수 변경. 현재 ACTIVE 상태에서만 허용."""
    project_id = token_info["project_id"]
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    if cluster["status"] != "ACTIVE":
        raise HTTPException(status_code=409, detail="ACTIVE 상태의 클러스터만 스케일링할 수 있습니다")

    current_agent_ids: list[str] = cluster.get("agent_vm_ids") or []
    if isinstance(current_agent_ids, str):
        import json as _json

        try:
            current_agent_ids = _json.loads(current_agent_ids)
        except Exception:
            current_agent_ids = []

    desired = req.agent_count
    current = len(current_agent_ids)

    if desired == current:
        return {"message": "변경 없음", "agent_count": current}

    await k3s_cluster.update_cluster_status(project_id, cluster_id, "SCALING")
    asyncio.create_task(_scale_agents(project_id, cluster_id, current_agent_ids, desired))
    return {"message": f"스케일링 시작: {current} → {desired}", "agent_count": desired}


async def _scale_agents(
    project_id: str,
    cluster_id: str,
    current_agent_ids: list[str],
    desired_count: int,
) -> None:
    """에이전트 스케일링 백그라운드 태스크."""
    from app.config import get_settings
    from app.services import k3s_plugins

    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        return

    node_token = await k3s_cluster.get_cluster_node_token(project_id, cluster_id)
    server_ip = cluster.get("server_ip") or ""
    s = get_settings()

    current_count = len(current_agent_ids)

    if desired_count > current_count:
        # 스케일 업
        add_count = desired_count - current_count
        agent_flavor_id = cluster.get("agent_flavor_id") or s.k3s_default_agent_flavor_id
        network_id = cluster.get("network_id") or ""
        ssh_public_key = cluster.get("ssh_public_key") or None
        cluster_name = cluster.get("name") or cluster_id
        k3s_version = cluster.get("k3s_version") or s.k3s_version
        scale_os_type = cluster.get("os_type") or "ubuntu"
        image_id = s.k3s_fcos_image_id if scale_os_type == "fcos" else s.k3s_server_image_id
        boot_volume_size = s.k3s_boot_volume_size_gb
        sg_id = cluster.get("security_group_id") or None

        try:
            conn = keystone.get_admin_connection_for_project(project_id)
        except Exception as e:
            _logger.error("k3s scale up: cannot get OpenStack connection: %s", e)
            await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", f"스케일 업 실패: {e}")
            return

        # network_id 폴백: DB → 설정값
        if not network_id:
            if s.default_network_enabled:
                try:
                    from app.services.default_network import ensure_default_network as _ensure_net

                    _default_net = await _ensure_net(
                        conn,
                        project_id,
                        external_network_id=s.default_network_external_id or None,
                        cidr=s.default_network_cidr,
                    )
                    network_id = _default_net.id
                except Exception:
                    _logger.warning("스케일 업: Default 네트워크 조회 실패, 설정값 폴백", exc_info=True)
                    network_id = s.default_network_id
            else:
                network_id = s.default_network_id

        new_entries: list[dict] = []
        for _i in range(add_count):
            agent_name = f"{cluster_name}-{_rand_suffix()}"
            try:
                vol = await asyncio.to_thread(
                    cinder.create_volume_from_image, conn, f"{agent_name}-boot", image_id, boot_volume_size
                )
                _agent_args = k3s_plugins.aggregate_agent_args(s)
                if not _agent_args and cluster.get("occm_enabled"):
                    _agent_args = ["--kubelet-arg=cloud-provider=external"]
                scale_userdata = k3s_cloudinit.generate_agent_userdata(
                    cluster_name=cluster_name,
                    k3s_version=k3s_version,
                    server_ip=server_ip,
                    node_token=node_token or "",
                    ssh_public_key=ssh_public_key,
                    extra_agent_args=_agent_args,
                    os_type=scale_os_type,
                )
                vm = await asyncio.to_thread(
                    nova.create_server,
                    conn,
                    agent_name,
                    agent_flavor_id,
                    network_id,
                    vol.id,
                    userdata=scale_userdata.data,
                    metadata={"k3s_horse_generator_role": "k3s_agent", "k3s_horse_generator_cluster_id": cluster_id},
                    delete_boot_volume_on_termination=True,
                    security_groups=[sg_id] if sg_id else None,
                    config_drive=scale_userdata.config_drive,
                )
                new_entries.append({"vm_id": vm.id, "name": agent_name})
                _logger.info("k3s scale up: agent %s created: %s", agent_name, vm.id)
            except Exception as e:
                _logger.error("k3s scale up: agent %s failed: %s", agent_name, e)

        if new_entries:
            await k3s_cluster.add_agent_vms(cluster_id, new_entries)

    else:
        # 스케일 다운: K8s 노드 제거 후 VM 삭제
        remove_ids = current_agent_ids[desired_count:]

        # K8s 노드 삭제 (VM 삭제 전 먼저 수행, best-effort)
        vm_name_map = await k3s_cluster.get_agent_vm_names(cluster_id, remove_ids)
        node_names = [name for name in vm_name_map.values() if name]
        if node_names:
            _logger.info("k3s scale down: K8s 노드 삭제 시작: %s", node_names)
            await k3s_kube.delete_k8s_nodes(cluster_id, node_names)

        try:
            conn = keystone.get_admin_connection_for_project(project_id)
        except Exception as e:
            _logger.error("k3s scale down: cannot get OpenStack connection: %s", e)
            await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", f"스케일 다운 실패: {e}")
            return

        for vm_id in remove_ids:
            try:
                await asyncio.to_thread(nova.delete_server, conn, vm_id)
                _logger.info("k3s scale down: agent VM %s deleted", vm_id)
            except Exception as e:
                _logger.warning("k3s scale down: delete VM %s failed: %s", vm_id, e)

        await k3s_cluster.remove_agent_vms(cluster_id, remove_ids)

    await k3s_cluster.update_agent_count(project_id, cluster_id, desired_count)
    await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", "")
    _logger.info("k3s cluster %s scaled to %d agents", cluster_id, desired_count)


@router.delete("/{cluster_id}", status_code=204)
async def delete_k3s_cluster(
    cluster_id: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
    token_info: dict = Depends(get_token_info),
):
    """k3s 클러스터 삭제: VM → SG 정리 후 soft-delete 처리."""
    project_id = conn._afterglow_project_id
    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")

    # 이미 삭제된 클러스터는 멱등 처리
    if cluster.get("deleted_at"):
        return

    await k3s_cluster.update_cluster_status(project_id, cluster_id, "DELETING")

    # API LB + FIP 정리 (VM 삭제 전에 먼저 처리)
    _api_lb_id = cluster.get("api_lb_id") or ""
    _api_fip_id = cluster.get("api_fip_id") or ""
    if _api_lb_id:
        try:
            await asyncio.to_thread(octavia.delete_load_balancer, conn, _api_lb_id, cascade=True)
            _logger.info("Deleted API LB %s for cluster %s", _api_lb_id, cluster_id)
        except Exception as e:
            _logger.warning("Delete API LB %s failed: %s", _api_lb_id, e)
    if _api_fip_id:
        try:
            await asyncio.to_thread(neutron.delete_floating_ip, conn, _api_fip_id)
            _logger.info("Deleted API FIP %s for cluster %s", _api_fip_id, cluster_id)
        except Exception as e:
            _logger.warning("Delete API FIP %s failed: %s", _api_fip_id, e)

    # OCCM이 생성한 Octavia LB 정리 (VM 삭제 전에 먼저 처리)
    if cluster.get("occm_enabled"):
        cluster_name = cluster.get("name") or ""
        prefix = f"kube_service_{cluster_name}_"
        try:
            all_lbs = await asyncio.to_thread(octavia.list_load_balancers, conn)
            for lb in all_lbs:
                if lb.get("name", "").startswith(prefix):
                    try:
                        await asyncio.to_thread(octavia.delete_load_balancer, conn, lb["id"], cascade=True)
                        _logger.info("Deleted OCCM LB %s (%s)", lb["id"], lb["name"])
                    except Exception as e:
                        _logger.warning("Delete OCCM LB %s failed: %s", lb["id"], e)
        except Exception as e:
            _logger.warning("Failed to list/delete OCCM LBs for cluster %s: %s", cluster_id, e)

    # 에이전트 VM 병렬 삭제
    agent_vm_ids = cluster.get("agent_vm_ids") or []
    if isinstance(agent_vm_ids, str):
        import json

        try:
            agent_vm_ids = json.loads(agent_vm_ids)
        except Exception:
            agent_vm_ids = []

    # K8s 노드 삭제 (VM 삭제 전 먼저 수행, best-effort)
    all_node_names: list[str] = []
    if agent_vm_ids:
        vm_name_map = await k3s_cluster.get_agent_vm_names(cluster_id, agent_vm_ids)
        all_node_names.extend([name for name in vm_name_map.values() if name])
    server_node_name = cluster.get("server_vm_name") or ""
    if server_node_name:
        all_node_names.append(server_node_name)
    if all_node_names:
        _logger.info("k3s delete: K8s 노드 삭제 시작: %s", all_node_names)
        try:
            await k3s_kube.delete_k8s_nodes(cluster_id, all_node_names)
        except Exception as e:
            _logger.warning("k3s delete: K8s 노드 삭제 중 오류 (무시): %s", e)

    async def _del_vm_and_wait(vm_id: str) -> None:
        try:
            await asyncio.to_thread(nova.delete_server, conn, vm_id)
        except Exception as e:
            _logger.warning("Delete agent VM %s failed: %s", vm_id, e)
            return
        try:
            await asyncio.to_thread(nova.wait_server_deleted, conn, vm_id)
            _logger.info("k3s delete: VM %s fully deleted", vm_id)
        except TimeoutError as e:
            _logger.warning("k3s delete: VM %s 삭제 대기 타임아웃 (계속 진행): %s", vm_id, e)
        except Exception as e:
            _logger.warning("k3s delete: VM %s 대기 중 오류 (계속 진행): %s", vm_id, e)

    await asyncio.gather(*[_del_vm_and_wait(vid) for vid in agent_vm_ids], return_exceptions=True)

    # 서버 VM 삭제 + 완료 대기
    server_vm_id = cluster.get("server_vm_id")
    if server_vm_id:
        try:
            await asyncio.to_thread(nova.delete_server, conn, server_vm_id)
        except Exception as e:
            _logger.warning("Delete server VM %s failed: %s", server_vm_id, e)
        else:
            try:
                await asyncio.to_thread(nova.wait_server_deleted, conn, server_vm_id)
                _logger.info("k3s delete: server VM %s fully deleted", server_vm_id)
            except TimeoutError as e:
                _logger.warning("k3s delete: server VM %s 삭제 대기 타임아웃 (계속 진행): %s", server_vm_id, e)
            except Exception as e:
                _logger.warning("k3s delete: server VM %s 대기 중 오류 (계속 진행): %s", server_vm_id, e)

    # 보안 그룹 삭제 (VM 삭제 완료 후, 재시도 포함)
    sg_id = cluster.get("security_group_id")
    if sg_id:
        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(5)
                await asyncio.to_thread(neutron.delete_security_group, conn, sg_id)
                _logger.info("k3s delete: SG %s deleted", sg_id)
                break
            except Exception as e:
                _logger.warning("Delete SG %s attempt %d failed: %s", sg_id, attempt + 1, e)

    # soft-delete: 상태를 DELETED로 기록 (물리 삭제 안 함)
    user_id = token_info.get("user_id") if isinstance(token_info, dict) else None
    await k3s_cluster.delete_cluster_record(project_id, cluster_id, user_id=user_id, reason="사용자 삭제 요청")
