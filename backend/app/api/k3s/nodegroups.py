"""k3s 노드그룹 API — /api/k3s/clusters/{cluster_id}/nodegroups"""

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
    """노드그룹 생성 (메타데이터만; VM 프로비저닝 없음)."""
    await _assert_cluster_access(cluster_id, token_info)
    try:
        return await _svc.create_nodegroup(cluster_id, req.model_dump())
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
    """노드그룹 수정 (node_count, flavor_id, labels, taints)."""
    await _assert_cluster_access(cluster_id, token_info)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    ng = await _svc.update_nodegroup(cluster_id, nodegroup_id, updates)
    if not ng:
        raise HTTPException(status_code=404, detail="노드그룹을 찾을 수 없습니다.")
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
