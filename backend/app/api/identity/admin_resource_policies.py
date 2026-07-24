"""Administrator-managed discovered OpenStack resource policies."""

from __future__ import annotations

import openstack
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_os_conn, get_token_info, require_admin
from app.services import resource_policies
from app.services import resource_policy_store as store

router = APIRouter()


class ResourcePolicyUpdate(BaseModel):
    resource_id: str | None = Field(default=None, max_length=128)


@router.get("/resource-policies", dependencies=[Depends(require_admin)])
async def list_resource_policies():
    try:
        return await store.list_policies()
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="리소스 정책 저장소를 사용할 수 없습니다") from exc


@router.get("/resource-policies/catalog/{policy_key}", dependencies=[Depends(require_admin)])
async def discover_resource_policy_options(
    policy_key: str,
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        spec = resource_policies.get_spec(policy_key)
        return {
            "key": spec.key,
            "resource_kind": spec.resource_kind,
            "options": await resource_policies.discover_options(conn, policy_key),
        }
    except resource_policies.ResourcePolicyValidationError as exc:
        raise HTTPException(status_code=404, detail="알 수 없는 리소스 정책입니다") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="OpenStack 리소스 목록을 조회할 수 없습니다") from exc


@router.put("/resource-policies/{policy_key}", dependencies=[Depends(require_admin)])
async def update_resource_policy(
    policy_key: str,
    body: ResourcePolicyUpdate,
    token_info: dict = Depends(get_token_info),
    conn: openstack.connection.Connection = Depends(get_os_conn),
):
    try:
        return await store.set_policy(
            conn=conn,
            key=policy_key,
            resource_id=body.resource_id,
            updated_by_user_id=str(token_info.get("user_id") or ""),
        )
    except resource_policies.ResourcePolicyValidationError as exc:
        raise HTTPException(status_code=422, detail="선택한 리소스가 정책 조건을 만족하지 않습니다") from exc
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="리소스 정책 저장소를 사용할 수 없습니다") from exc
