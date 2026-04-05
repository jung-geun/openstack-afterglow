import asyncio
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.models.containers import ClusterInfo, ClusterTemplateInfo, CreateClusterRequest, StackResourceInfo, StackEventInfo
from app.services import magnum
from app.services import heat
from app.services.heat import HeatServiceUnavailable

router = APIRouter()


@router.get("", response_model=list[ClusterInfo])
async def list_clusters(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(magnum.list_clusters, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"클러스터 목록 조회 실패: {e}")


@router.get("/templates", response_model=list[ClusterTemplateInfo])
async def list_templates(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(magnum.list_cluster_templates, conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"클러스터 템플릿 조회 실패: {e}")


@router.get("/{cluster_id}", response_model=ClusterInfo)
async def get_cluster(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.to_thread(magnum.get_cluster, conn, cluster_id)
    except Exception:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")


@router.post("", response_model=ClusterInfo, status_code=201)
async def create_cluster(
    req: CreateClusterRequest,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await asyncio.to_thread(
            magnum.create_cluster, conn,
            req.name, req.cluster_template_id,
            req.node_count, req.master_count,
            req.keypair, req.create_timeout,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"클러스터 생성 실패: {e}")


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(magnum.delete_cluster, conn, cluster_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"클러스터 삭제 실패: {e}")


async def _get_stack_id(conn, cluster_id: str) -> str:
    """클러스터에서 stack_id를 조회."""
    try:
        cluster = await asyncio.to_thread(magnum.get_cluster, conn, cluster_id)
    except Exception:
        raise HTTPException(status_code=404, detail="클러스터를 찾을 수 없습니다")
    if not cluster.stack_id:
        raise HTTPException(status_code=404, detail="이 클러스터에는 Heat 스택이 없습니다")
    return cluster.stack_id


@router.get("/{cluster_id}/stack")
async def get_cluster_stack(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    stack_id = await _get_stack_id(conn, cluster_id)
    try:
        return await asyncio.to_thread(heat.get_stack_detail, conn, stack_id)
    except HeatServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{cluster_id}/stack/resources", response_model=list[StackResourceInfo])
async def get_cluster_stack_resources(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    stack_id = await _get_stack_id(conn, cluster_id)
    try:
        return await asyncio.to_thread(heat.list_stack_resources, conn, stack_id)
    except HeatServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{cluster_id}/stack/events", response_model=list[StackEventInfo])
async def get_cluster_stack_events(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    stack_id = await _get_stack_id(conn, cluster_id)
    try:
        return await asyncio.to_thread(heat.list_stack_events, conn, stack_id)
    except HeatServiceUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
