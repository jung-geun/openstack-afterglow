"""k3s 서버 VM으로부터 kubeconfig/node-token 콜백 수신 (인증 불필요)."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from app.models.k3s import K3sCallbackRequest
from app.rate_limit import limiter
from app.services import k3s_db as k3s_cluster

router = APIRouter()
_logger = logging.getLogger(__name__)


@router.post("/callback")
@limiter.limit("10/minute")
async def k3s_callback(request: Request, req: K3sCallbackRequest):
    """k3s 서버 VM의 cloud-init에서 kubeconfig + node-token 수신.

    일회성 토큰으로 보안 보장. 토큰 소비 후 에이전트 VM 생성은 백그라운드로 처리.
    """
    # 일회성 토큰 검증 (atomic GET+DELETE)
    token_data = await k3s_cluster.consume_callback_token(req.token)
    if not token_data:
        _logger.warning("k3s callback received with invalid/expired token")
        raise HTTPException(status_code=403, detail="Forbidden")

    project_id = token_data["project_id"]
    cluster_id = token_data["cluster_id"]

    if not req.success:
        error_msg = req.error or "서버 VM에서 알 수 없는 오류 발생"
        _logger.error("k3s cluster %s server init failed: %s", cluster_id, error_msg)
        await k3s_cluster.update_cluster_status(project_id, cluster_id, "ERROR", f"서버 초기화 실패: {error_msg}")
        return {"ok": True}

    if not req.kubeconfig or not req.node_token or not req.server_ip:
        _logger.error("k3s cluster %s callback missing fields", cluster_id)
        await k3s_cluster.update_cluster_status(
            project_id, cluster_id, "ERROR", "콜백 데이터 누락 (kubeconfig/node_token/server_ip)"
        )
        return {"ok": True}

    # kubeconfig 암호화 저장
    try:
        await k3s_cluster.store_kubeconfig(project_id, cluster_id, req.kubeconfig)
    except Exception as e:
        _logger.error("k3s cluster %s kubeconfig encryption failed: %s", cluster_id, e)
        await k3s_cluster.update_cluster_status(project_id, cluster_id, "ERROR", f"kubeconfig 저장 실패: {e}")
        return {"ok": True}

    # 클러스터 레코드에 server_ip, node_token, api_address 업데이트
    api_address = f"https://{req.server_ip}:6443"
    await k3s_cluster.update_cluster_status(
        project_id,
        cluster_id,
        "PROVISIONING",
        server_ip=req.server_ip,
        api_address=api_address,
        node_token=req.node_token,
    )

    if req.occm_status:
        _logger.info("k3s cluster %s OCCM status: %s", cluster_id, req.occm_status)
    if req.plugin_status:
        _logger.info("k3s cluster %s plugin status: %s", cluster_id, req.plugin_status)

    _logger.info("k3s cluster %s server ready, spawning agent VMs", cluster_id)

    # 에이전트 VM 생성은 백그라운드 태스크로 (콜백 응답을 빠르게 반환)
    asyncio.create_task(_provision_agents(project_id, cluster_id, req.server_ip, req.node_token))

    return {"ok": True}


async def _finalize_api_lb(
    project_id: str,
    cluster_id: str,
    cluster: dict,
    server_ip: str,
    conn,
) -> None:
    """API LB 설정 완료: member 추가 + health monitor + kubeconfig 패치.

    LB-first 전략: clusters.py에서 이미 LB(listener+pool)를 완전히 생성했으므로,
    서버 VM의 private IP를 pool에 member로 추가하고 health monitor를 생성한 후
    kubeconfig의 server URL을 LB 주소(FIP 또는 provider VIP)로 패치한다.
    """
    from app.services import k3s_db as _k3s_db
    from app.services import octavia

    api_lb_id = cluster.get("api_lb_id") or ""
    api_lb_pool_id = cluster.get("api_lb_pool_id") or ""
    api_fip_id = cluster.get("api_fip_id") or ""
    api_fip_address = cluster.get("api_fip_address") or ""
    cluster_name = cluster.get("name") or cluster_id

    if not api_lb_id or not api_lb_pool_id or not api_fip_address:
        return

    try:
        # LB ACTIVE 대기 (최대 5분)
        lb = await asyncio.to_thread(octavia.wait_for_load_balancer, conn, api_lb_id)
        vip_subnet_id = lb.get("vip_subnet_id")

        # Member 서브넷: 클러스터 네트워크의 서브넷 우선 사용 (LB가 다른 네트워크에 있을 수 있음)
        cluster_network_id = cluster.get("network_id")
        member_subnet_id = vip_subnet_id  # 기본값: LB VIP 서브넷
        if cluster_network_id:
            try:
                cluster_net = await asyncio.to_thread(conn.network.get_network, cluster_network_id)
                cluster_subnet_ids = getattr(cluster_net, "subnet_ids", None) or []
                if cluster_subnet_ids:
                    member_subnet_id = cluster_subnet_ids[0]
            except Exception:
                _logger.warning("k3s cluster %s: 클러스터 네트워크 서브넷 조회 실패, VIP 서브넷 사용", cluster_id)

        # Member 추가 (server private IP:6443, 클러스터 서브넷으로)
        await asyncio.to_thread(
            octavia.add_member,
            conn,
            api_lb_pool_id,
            server_ip,
            6443,
            subnet_id=member_subnet_id,
            name=f"{cluster_name}-server",
        )
        await asyncio.to_thread(octavia.wait_for_load_balancer, conn, api_lb_id)

        # Health Monitor 생성 (TCP)
        await asyncio.to_thread(
            octavia.create_health_monitor,
            conn,
            api_lb_pool_id,
            type="TCP",
            delay=10,
            timeout=5,
            max_retries=3,
            name=f"k3s-api-{cluster_name}",
        )
        await asyncio.to_thread(octavia.wait_for_load_balancer, conn, api_lb_id)

        # FIP 모드: FIP → LB VIP port 연결 (provider 직접 VIP 모드에서는 이미 연결됨)
        if api_fip_id:
            lb_refreshed = await asyncio.to_thread(octavia.get_load_balancer, conn, api_lb_id)
            vip_port_id = lb_refreshed.get("vip_port_id")
            if vip_port_id:
                await asyncio.to_thread(conn.network.update_ip, api_fip_id, port_id=vip_port_id)

        # api_address를 외부 주소(FIP 또는 provider VIP)로 업데이트
        new_api_address = f"https://{api_fip_address}:6443"
        await _k3s_db.update_cluster_status(project_id, cluster_id, "PROVISIONING", api_address=new_api_address)

        # kubeconfig의 server URL을 외부 주소로 패치
        kubeconfig = await _k3s_db.get_kubeconfig(project_id, cluster_id)
        if kubeconfig:
            old_url = f"https://{server_ip}:6443"
            patched = kubeconfig.replace(old_url, new_api_address)
            await _k3s_db.store_kubeconfig(project_id, cluster_id, patched)

        _logger.info("k3s cluster %s: API LB 설정 완료 → %s", cluster_id, new_api_address)
    except Exception:
        _logger.error(
            "k3s cluster %s: API LB 설정 실패 (클러스터는 private IP로 계속 동작)",
            cluster_id,
            exc_info=True,
        )


async def _provision_agents(
    project_id: str,
    cluster_id: str,
    server_ip: str,
    node_token: str,
) -> None:
    """에이전트 VM 생성 백그라운드 태스크."""
    import asyncio

    from app.config import get_settings
    from app.services import cinder, k3s_cloudinit, keystone, nova

    cluster = await k3s_cluster.get_cluster(project_id, cluster_id)
    if not cluster:
        _logger.error("k3s agent provision: cluster %s not found", cluster_id)
        return

    agent_count = int(cluster.get("agent_count") or 0)
    if agent_count == 0:
        await k3s_cluster.update_cluster_status(project_id, cluster_id, "ACTIVE", "")
        return

    s = get_settings()
    agent_flavor_id = cluster.get("agent_flavor_id") or s.k3s_default_agent_flavor_id
    if not agent_flavor_id:
        _logger.error("k3s agent provision: agent_flavor_id not configured")
        await k3s_cluster.update_cluster_status(project_id, cluster_id, "ERROR", "에이전트 플레이버 미설정")
        return
    network_id = cluster.get("network_id") or s.default_network_id
    ssh_public_key = cluster.get("ssh_public_key") or None
    cluster_name = cluster.get("name") or cluster_id
    k3s_version = cluster.get("k3s_version") or s.k3s_version
    os_type = cluster.get("os_type") or "ubuntu"
    image_id = s.k3s_fcos_image_id if os_type == "fcos" else s.k3s_server_image_id
    boot_volume_size = s.k3s_boot_volume_size_gb
    sg_id = cluster.get("security_group_id") or None

    # 관리자 OpenStack 연결로 VM 생성 (에이전트는 사용자 프로젝트에 생성)
    try:
        conn = keystone.get_admin_connection_for_project(project_id)
    except Exception as e:
        _logger.error("k3s agent provision: cannot get OpenStack connection: %s", e)
        await k3s_cluster.update_cluster_status(project_id, cluster_id, "ERROR", f"OpenStack 연결 실패: {e}")
        return

    # API LB 설정 완료 (listener/pool/member/FIP 연결) — agent 생성 전에 처리
    await _finalize_api_lb(project_id, cluster_id, cluster, server_ip, conn)

    agent_vm_ids: list[str] = []
    failed_count = 0

    new_agent_entries: list[dict] = []
    for i in range(agent_count):
        agent_name = f"{cluster_name}-agent-{i + 1}"
        try:
            # 에이전트 부트 볼륨 생성
            vol = await asyncio.to_thread(
                cinder.create_volume_from_image, conn, f"{agent_name}-boot", image_id, boot_volume_size
            )
            # 에이전트 cloud-init 생성 (활성 플러그인 인자 반영)
            from app.services import k3s_plugins

            _agent_args = k3s_plugins.aggregate_agent_args(s)
            if not _agent_args and cluster.get("occm_enabled"):
                # 레거시 클러스터 (plugins_enabled 없음): occm_enabled로 폴백
                _agent_args = ["--kubelet-arg=cloud-provider=external"]
            agent_userdata = k3s_cloudinit.generate_agent_userdata(
                cluster_name=cluster_name,
                k3s_version=k3s_version,
                server_ip=server_ip,
                node_token=node_token,
                ssh_public_key=ssh_public_key,
                extra_agent_args=_agent_args,
                os_type=os_type,
            )
            # 에이전트 VM 생성 (admin conn이므로 key_name 대신 cloud-init으로 공개키 주입)
            vm = await asyncio.to_thread(
                nova.create_server,
                conn,
                agent_name,
                agent_flavor_id,
                network_id,
                vol.id,
                userdata=agent_userdata.data,
                metadata={"k3s_horse_generator_role": "k3s_agent", "k3s_horse_generator_cluster_id": cluster_id},
                delete_boot_volume_on_termination=True,
                security_groups=[sg_id] if sg_id else None,
                config_drive=agent_userdata.config_drive,
            )
            agent_vm_ids.append(vm.id)
            new_agent_entries.append({"vm_id": vm.id, "name": agent_name})
            _logger.info("k3s agent %s created: %s", agent_name, vm.id)
        except Exception as e:
            _logger.error("k3s agent %s creation failed: %s", agent_name, e)
            failed_count += 1

    # 에이전트 VM DB 저장
    if new_agent_entries:
        await k3s_cluster.add_agent_vms(cluster_id, new_agent_entries)

    # 클러스터 상태 업데이트
    reason = f"에이전트 {failed_count}개 생성 실패" if failed_count else ""
    await k3s_cluster.update_cluster_status(
        project_id,
        cluster_id,
        "ACTIVE",
        reason,
        agent_vm_ids=agent_vm_ids,
    )
    _logger.info(
        "k3s cluster %s ACTIVE: %d agents created, %d failed",
        cluster_id,
        len(agent_vm_ids),
        failed_count,
    )
