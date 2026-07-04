"""k3s 노드그룹 API — /api/k3s/clusters/{cluster_id}/nodegroups"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_token_info
from app.models.k3s import CreateK3sNodegroupRequest, K3sNodegroupInfo, UpdateK3sNodegroupRequest
from app.services import k3s_db
from app.services import k3s_nodegroup as _svc

router = APIRouter()
_logger = logging.getLogger(__name__)


async def _assert_cluster_access(cluster_id: str, token_info: dict) -> None:
    """클러스터가 현재 프로젝트에 속하는지 확인."""
    project_id = token_info.get("project_id") or ""
    cluster = await k3s_db.get_cluster(project_id, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다.")


async def _provision_nodegroup_and_reconcile(project_id: str, cluster_id: str, ng: dict, add_count: int) -> None:
    from app.services import k3s_autoscale

    created = await k3s_autoscale.provision_nodegroup_vms(
        project_id=project_id,
        cluster_id=cluster_id,
        nodegroup_id=ng["id"],
        add_count=add_count,
        flavor_id=ng["flavor_id"],
        image_id=ng.get("image_id"),
        labels=ng.get("labels"),
        taints=ng.get("taints"),
    )
    if len(created) != add_count:
        latest = await _svc.get_nodegroup(cluster_id, ng["id"])
        actual = len((latest or {}).get("vms") or [])
        await _svc.set_nodegroup_count(cluster_id, ng["id"], actual)
        _logger.warning(
            "nodegroup %s provisioning reconciled desired %d to actual %d",
            ng["id"],
            add_count,
            actual,
        )


async def _delete_nodegroup_and_reconcile(
    project_id: str, cluster_id: str, ng: dict, remove_entries: list[dict]
) -> None:
    from app.services import k3s_autoscale

    await k3s_autoscale.delete_nodegroup_vms(
        project_id=project_id,
        cluster_id=cluster_id,
        nodegroup_id=ng["id"],
        vm_entries=remove_entries,
    )
    latest = await _svc.get_nodegroup(cluster_id, ng["id"])
    actual = len((latest or {}).get("vms") or [])
    await _svc.set_nodegroup_count(cluster_id, ng["id"], actual)


@router.get("/{cluster_id}/nodegroups", response_model=list[K3sNodegroupInfo])
async def list_nodegroups(cluster_id: str, token_info: dict = Depends(get_token_info)):
    """클러스터의 노드그룹 목록 조회."""
    await _assert_cluster_access(cluster_id, token_info)
    return await _svc.list_nodegroups(cluster_id)


@router.get("/{cluster_id}/nodegroups/{nodegroup_id}", response_model=K3sNodegroupInfo)
async def get_nodegroup(cluster_id: str, nodegroup_id: str, token_info: dict = Depends(get_token_info)):
    """노드그룹 단건 조회."""
    await _assert_cluster_access(cluster_id, token_info)
    ng = await _svc.get_nodegroup(cluster_id, nodegroup_id)
    if not ng:
        raise HTTPException(status_code=404, detail="노드그룹을 찾을 수 없습니다.")
    return ng


@router.post("/{cluster_id}/nodegroups", response_model=K3sNodegroupInfo, status_code=201)
async def create_nodegroup(
    cluster_id: str,
    req: CreateK3sNodegroupRequest,
    token_info: dict = Depends(get_token_info),
):
    """노드그룹 생성. agent 그룹은 node_count > 0이면 VM 프로비저닝을 시작한다."""
    await _assert_cluster_access(cluster_id, token_info)
    try:
        ng = await _svc.create_nodegroup(cluster_id, req.model_dump())
        if ng["role"] == "agent" and ng.get("node_count", 0) > 0:
            asyncio.create_task(
                _provision_nodegroup_and_reconcile(
                    token_info.get("project_id") or "",
                    cluster_id,
                    ng,
                    int(ng.get("node_count", 0)),
                )
            )
        return ng
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.patch("/{cluster_id}/nodegroups/{nodegroup_id}", response_model=K3sNodegroupInfo)
async def update_nodegroup(
    cluster_id: str,
    nodegroup_id: str,
    req: UpdateK3sNodegroupRequest,
    token_info: dict = Depends(get_token_info),
):
    """노드그룹 수정. agent node_count 변경은 VM 프로비저닝/삭제를 시작한다."""
    await _assert_cluster_access(cluster_id, token_info)
    before = await _svc.get_nodegroup(cluster_id, nodegroup_id)
    if not before:
        raise HTTPException(status_code=404, detail="노드그룹을 찾을 수 없습니다.")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if before.get("role") == "server" and "node_count" in updates and updates["node_count"] != before.get("node_count"):
        raise HTTPException(status_code=422, detail="server 노드그룹 node_count 변경은 아직 지원되지 않습니다.")
    try:
        ng = await _svc.update_nodegroup(cluster_id, nodegroup_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not ng:
        raise HTTPException(status_code=404, detail="노드그룹을 찾을 수 없습니다.")
    if ng["role"] == "agent" and "node_count" in updates:
        desired = int(ng.get("node_count", 0))
        current = len(before.get("vms") or [])
        project_id = token_info.get("project_id") or ""
        if desired > current:
            asyncio.create_task(_provision_nodegroup_and_reconcile(project_id, cluster_id, ng, desired - current))
        elif desired < current:
            remove_entries = list(reversed(before.get("vms") or []))[: current - desired]
            asyncio.create_task(_delete_nodegroup_and_reconcile(project_id, cluster_id, ng, remove_entries))
    return ng


@router.delete("/{cluster_id}/nodegroups/{nodegroup_id}", status_code=204)
async def delete_nodegroup(
    cluster_id: str,
    nodegroup_id: str,
    token_info: dict = Depends(get_token_info),
):
    """노드그룹 삭제 (soft-delete). 기본 그룹은 삭제 불가."""
    await _assert_cluster_access(cluster_id, token_info)
    try:
        deleted = await _svc.delete_nodegroup(cluster_id, nodegroup_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="노드그룹을 찾을 수 없습니다.")
