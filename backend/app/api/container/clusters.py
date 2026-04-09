import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
import openstack
from keystoneauth1 import exceptions as ks_exc
from openstack import exceptions as os_exc

from app.api.deps import get_os_conn

logger = logging.getLogger(__name__)
from app.models.containers import ClusterInfo, ClusterTemplateInfo, CreateClusterRequest, StackResourceInfo, StackEventInfo
from app.services import magnum
from app.services import heat
from app.services.heat import HeatServiceUnavailable

router = APIRouter()

_MAGNUM_TIMEOUT = 15  # seconds


def _is_service_unavailable(e: Exception) -> bool:
    """Magnum 서비스 연결 불가 여부 판별."""
    if isinstance(e, (ks_exc.ConnectTimeout, ks_exc.ConnectFailure, ks_exc.ConnectionError)):
        return True
    if isinstance(e, os_exc.HttpException) and getattr(e, 'status_code', 0) == 503:
        return True
    return False


@router.get("", response_model=list[ClusterInfo])
async def list_clusters(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(magnum.list_clusters, conn),
            timeout=_MAGNUM_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as e:
        if isinstance(e, asyncio.TimeoutError) or _is_service_unavailable(e):
            logger.warning("Magnum 서비스 응답 없음 (clusters): %s", e)
            raise HTTPException(status_code=503, detail="Magnum 서비스에 연결할 수 없습니다")
        logger.exception("클러스터 목록 조회 실패: %s", e)
        raise HTTPException(status_code=500, detail="클러스터 목록 조회 실패")


@router.get("/templates", response_model=list[ClusterTemplateInfo])
async def list_templates(conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(magnum.list_cluster_templates, conn),
            timeout=_MAGNUM_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as e:
        if isinstance(e, asyncio.TimeoutError) or _is_service_unavailable(e):
            logger.warning("Magnum 서비스 응답 없음 (templates): %s", e)
            raise HTTPException(status_code=503, detail="Magnum 서비스에 연결할 수 없습니다")
        logger.exception("클러스터 템플릿 조회 실패: %s", e)
        raise HTTPException(status_code=500, detail="클러스터 템플릿 조회 실패")


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
        raise HTTPException(status_code=500, detail="클러스터 생성 실패")


@router.delete("/{cluster_id}", status_code=204)
async def delete_cluster(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    try:
        await asyncio.to_thread(magnum.delete_cluster, conn, cluster_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail="클러스터 삭제 실패")


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
        raise HTTPException(status_code=503, detail="작업 실패")


@router.get("/{cluster_id}/stack/resources", response_model=list[StackResourceInfo])
async def get_cluster_stack_resources(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    stack_id = await _get_stack_id(conn, cluster_id)
    try:
        return await asyncio.to_thread(heat.list_stack_resources, conn, stack_id)
    except HeatServiceUnavailable as e:
        raise HTTPException(status_code=503, detail="작업 실패")


@router.get("/{cluster_id}/stack/events", response_model=list[StackEventInfo])
async def get_cluster_stack_events(cluster_id: str, conn: openstack.connection.Connection = Depends(get_os_conn)):
    stack_id = await _get_stack_id(conn, cluster_id)
    try:
        return await asyncio.to_thread(heat.list_stack_events, conn, stack_id)
    except HeatServiceUnavailable as e:
        raise HTTPException(status_code=503, detail="작업 실패")
