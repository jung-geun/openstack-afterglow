"""k3s 서버 VM으로부터 kubeconfig/node-token 콜백 수신 (인증 불필요)."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request

from app.models.k3s import K3sCallbackRequest
from app.rate_limit import limiter
from app.services import k3s_cluster

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
        await k3s_cluster.update_cluster_status(
            project_id, cluster_id, "ERROR", f"서버 초기화 실패: {error_msg}"
        )
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
        await k3s_cluster.update_cluster_status(
            project_id, cluster_id, "ERROR", f"kubeconfig 저장 실패: {e}"
        )
        return {"ok": True}

    # 클러스터 레코드에 server_ip, node_token, api_address 업데이트
    api_address = f"https://{req.server_ip}:6443"
    await k3s_cluster.update_cluster_status(
        project_id, cluster_id, "PROVISIONING",
        server_ip=req.server_ip,
        api_address=api_address,
        node_token=req.node_token,
    )

    _logger.info("k3s cluster %s server ready, spawning agent VMs", cluster_id)

    # 에이전트 VM 생성은 백그라운드 태스크로 (콜백 응답을 빠르게 반환)
    asyncio.create_task(_provision_agents(project_id, cluster_id, req.server_ip, req.node_token))

    return {"ok": True}


async def _provision_agents(
    project_id: str,
    cluster_id: str,
    server_ip: str,
    node_token: str,
) -> None:
    """에이전트 VM 생성 백그라운드 태스크."""
    import asyncio
    from app.config import get_settings
    from app.services import k3s_cloudinit
    from app.services import cinder, nova, keystone

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
        await k3s_cluster.update_cluster_status(
            project_id, cluster_id, "ERROR", "에이전트 플레이버 미설정"
        )
        return
    network_id = cluster.get("network_id") or s.default_network_id
    key_name = cluster.get("key_name") or None
    cluster_name = cluster.get("name") or cluster_id
    k3s_version = cluster.get("k3s_version") or s.k3s_version
    image_id = s.k3s_server_image_id
    boot_volume_size = s.k3s_boot_volume_size_gb
    sg_id = cluster.get("security_group_id") or None

    # 관리자 OpenStack 연결로 VM 생성 (에이전트는 사용자 프로젝트에 생성)
    try:
        conn = keystone.get_admin_connection_for_project(project_id)
    except Exception as e:
        _logger.error("k3s agent provision: cannot get OpenStack connection: %s", e)
        await k3s_cluster.update_cluster_status(
            project_id, cluster_id, "ERROR", f"OpenStack 연결 실패: {e}"
        )
        return

    agent_vm_ids: list[str] = []
    failed_count = 0

    for i in range(agent_count):
        agent_name = f"{cluster_name}-agent-{i + 1}"
        try:
            # 에이전트 부트 볼륨 생성
            vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn, f"{agent_name}-boot", image_id, boot_volume_size
            )
            # 에이전트 cloud-init 생성
            userdata = k3s_cloudinit.generate_agent_userdata(
                cluster_name=cluster_name,
                k3s_version=k3s_version,
                server_ip=server_ip,
                node_token=node_token,
            )
            # 에이전트 VM 생성
            vm = await asyncio.to_thread(
                nova.create_server,
                conn, agent_name, agent_flavor_id, network_id, vol.id,
                userdata=userdata,
                key_name=key_name,
                metadata={"union_role": "k3s_agent", "union_cluster_id": cluster_id},
                delete_boot_volume_on_termination=True,
                security_groups=[sg_id] if sg_id else None,
            )
            agent_vm_ids.append(vm.id)
            _logger.info("k3s agent %s created: %s", agent_name, vm.id)
        except Exception as e:
            _logger.error("k3s agent %s creation failed: %s", agent_name, e)
            failed_count += 1

    # 클러스터 상태 업데이트
    reason = f"에이전트 {failed_count}개 생성 실패" if failed_count else ""
    await k3s_cluster.update_cluster_status(
        project_id, cluster_id, "ACTIVE", reason,
        agent_vm_ids=agent_vm_ids,
    )
    _logger.info(
        "k3s cluster %s ACTIVE: %d agents created, %d failed",
        cluster_id, len(agent_vm_ids), failed_count,
    )
