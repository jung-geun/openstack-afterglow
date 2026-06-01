"""k3s Stampede 노드그룹 VM 프로비저닝 서비스.

clusters.py의 _scale_agents 로직을 노드그룹 단위로 일반화·추출.
Stampede Reconciler(k3s_stampede.py)와 수동 스케일 핸들러(clusters.py) 양쪽에서 호출.
"""

import asyncio
import logging
import random
import string

from app.config import get_settings

_logger = logging.getLogger(__name__)


def _rand_suffix(n: int = 5) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


async def provision_nodegroup_vms(
    project_id: str,
    cluster_id: str,
    nodegroup_id: str,
    add_count: int,
    *,
    flavor_id: str,
    image_id: str | None = None,
    labels: dict | None = None,
    taints: list | None = None,
) -> list[dict]:
    """노드그룹에 agent VM을 add_count개 생성해 k3s 클러스터에 join시킨다.

    labels/taints는 cloud-init extra_agent_args로 주입.
    생성된 VM 목록 {vm_id, name}을 반환한다 (실패한 것은 포함하지 않음).
    """
    from app.services import (
        cinder,
        k3s_cloudinit,
        k3s_db,
        k3s_nodegroup,
        k3s_plugins,
        keystone,
        nova,
    )
    from app.services import k3s_cluster as k3s_cluster_svc

    s = get_settings()

    # 클러스터 기본 정보 조회 (admin: project_id 필터 없음)
    cluster = await k3s_db.get_cluster_admin(cluster_id)
    if not cluster:
        _logger.error("provision_nodegroup_vms: cluster %s 없음", cluster_id)
        return []

    node_token = await k3s_cluster_svc.get_cluster_node_token(project_id, cluster_id)
    server_ip = cluster.get("server_ip") or ""
    cluster_name = cluster.get("name") or cluster_id
    k3s_version = cluster.get("k3s_version") or s.k3s_version
    os_type = cluster.get("os_type") or "ubuntu"
    network_id = cluster.get("network_id") or s.default_network_id
    ssh_public_key = cluster.get("ssh_public_key") or None
    sg_id = cluster.get("security_group_id") or None
    boot_volume_size = s.k3s_boot_volume_size_gb

    # 이미지: 노드그룹 지정 → 클러스터 기본 → 설정값
    if not image_id:
        image_id = s.k3s_fcos_image_id if os_type == "fcos" else s.k3s_server_image_id

    # OpenStack 연결
    try:
        conn = keystone.get_admin_connection_for_project(project_id)
    except Exception as e:
        _logger.error("provision_nodegroup_vms: OpenStack 연결 실패: %s", e)
        return []

    # network_id 폴백
    if not network_id:
        if s.default_network_enabled:
            try:
                from app.services.default_network import ensure_default_network as _ensure_net
                _net = await _ensure_net(conn, project_id,
                                         external_network_id=s.default_network_external_id or None,
                                         cidr=s.default_network_cidr)
                network_id = _net.id
            except Exception:
                _logger.warning("provision_nodegroup_vms: default network 조회 실패", exc_info=True)
                network_id = s.default_network_id
        else:
            network_id = s.default_network_id

    # extra_agent_args 구성 (플러그인 + labels/taints + nodegroup 식별 라벨)
    _agent_args = k3s_plugins.aggregate_agent_args(s)
    if not _agent_args and cluster.get("occm_enabled"):
        _agent_args = ["--kubelet-arg=cloud-provider=external"]

    # 노드그룹 labels → --node-label
    for k, v in (labels or {}).items():
        _agent_args.append(f"--node-label={k}={v}")

    # nodegroup 식별 라벨 (Stampede 내부 추적용)
    _agent_args.append(f"--node-label=afterglow.io/nodegroup={nodegroup_id}")
    _agent_args.append("--node-label=afterglow.io/stampede=true")

    # 노드그룹 taints → --node-taint
    for taint in (taints or []):
        # taint 형식: {"key": "k", "value": "v", "effect": "NoSchedule"}
        # 또는 단순 문자열 "k=v:Effect"
        if isinstance(taint, dict):
            key = taint.get("key", "")
            value = taint.get("value", "")
            effect = taint.get("effect", "NoSchedule")
            if value:
                _agent_args.append(f"--node-taint={key}={value}:{effect}")
            else:
                _agent_args.append(f"--node-taint={key}:{effect}")
        elif isinstance(taint, str):
            _agent_args.append(f"--node-taint={taint}")

    new_entries: list[dict] = []
    for _i in range(add_count):
        agent_name = f"{cluster_name}-{_rand_suffix()}"
        try:
            vol = await asyncio.to_thread(
                cinder.create_volume_from_image,
                conn,
                f"{agent_name}-boot",
                image_id,
                boot_volume_size,
            )
            userdata = k3s_cloudinit.generate_agent_userdata(
                cluster_name=cluster_name,
                k3s_version=k3s_version,
                server_ip=server_ip,
                node_token=node_token or "",
                ssh_public_key=ssh_public_key,
                extra_agent_args=_agent_args,
                os_type=os_type,
            )
            vm = await asyncio.to_thread(
                nova.create_server,
                conn,
                agent_name,
                flavor_id,
                network_id,
                vol.id,
                userdata=userdata.data,
                metadata={
                    "k3s_horse_generator_role": "k3s_agent",
                    "k3s_horse_generator_cluster_id": cluster_id,
                    "k3s_horse_generator_nodegroup_id": nodegroup_id,
                },
                delete_boot_volume_on_termination=True,
                security_groups=[sg_id] if sg_id else None,
                config_drive=userdata.config_drive,
            )
            new_entries.append({"vm_id": vm.id, "name": agent_name})
            _logger.info("stampede: nodegroup %s — agent %s (%s) 생성됨", nodegroup_id, agent_name, vm.id)
        except Exception as e:
            _logger.error("stampede: nodegroup %s — agent %s 생성 실패: %s", nodegroup_id, agent_name, e)

    # DB에 VM 추적 레코드 추가
    if new_entries:
        await k3s_nodegroup.add_nodegroup_vms(nodegroup_id, cluster_id, new_entries)

    return new_entries


async def delete_nodegroup_vms(
    project_id: str,
    cluster_id: str,
    nodegroup_id: str,
    vm_entries: list[dict],
) -> None:
    """노드그룹 VM을 cordon→drain→삭제한다.

    vm_entries: [{"vm_id": ..., "name": ...}, ...]
    """
    from app.services import k3s_kube, k3s_nodegroup, keystone, nova

    # cordon + drain
    node_names = [e["name"] for e in vm_entries if e.get("name")]
    for node_name in node_names:
        cordon_ok = await k3s_kube.cordon_node(cluster_id, node_name)
        if cordon_ok:
            drain_ok = await k3s_kube.drain_node(cluster_id, node_name)
            if not drain_ok:
                _logger.warning("stampede: drain %s timeout/실패, 강제 삭제 진행", node_name)

    # K8s 노드 오브젝트 삭제
    if node_names:
        await k3s_kube.delete_k8s_nodes(cluster_id, node_names)

    # Nova VM 삭제
    try:
        conn = keystone.get_admin_connection_for_project(project_id)
    except Exception as e:
        _logger.error("delete_nodegroup_vms: OpenStack 연결 실패: %s", e)
        return

    vm_ids = [e["vm_id"] for e in vm_entries if e.get("vm_id")]
    for vm_id in vm_ids:
        try:
            await asyncio.to_thread(nova.delete_server, conn, vm_id)
            _logger.info("stampede: VM %s 삭제됨", vm_id)
        except Exception as e:
            _logger.warning("stampede: VM %s 삭제 실패: %s", vm_id, e)

    # DB 레코드 제거
    await k3s_nodegroup.remove_nodegroup_vms(nodegroup_id, vm_ids)
