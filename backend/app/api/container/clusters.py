import asyncio
from fastapi import APIRouter, Depends, HTTPException
import openstack

from app.api.deps import get_os_conn
from app.models.containers import ClusterInfo, ClusterTemplateInfo, CreateClusterRequest
from app.services import magnum

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
