"""System-admin compatibility proxy for Drover-owned cluster operations."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.api.deps import require_admin
from app.services.service_proxy import proxy

router = APIRouter(dependencies=[Depends(require_admin)])

_ADMIN_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


@router.api_route("/k3s-clusters", methods=_ADMIN_METHODS)
@router.api_route("/k3s-clusters/{path:path}", methods=_ADMIN_METHODS)
async def proxy_admin_clusters(request: Request, path: str = "") -> Response:
    upstream_path = "/v1/admin/clusters" if not path else f"/v1/admin/clusters/{path}"
    return await proxy("drover", request, upstream_path)


@router.api_route("/k3s-cluster-templates", methods=_ADMIN_METHODS)
async def proxy_admin_cluster_templates(request: Request) -> Response:
    return await proxy("drover", request, "/v1/admin/cluster-templates")
