"""Administrator-managed discovered-resource policies and runtime settings."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Annotated

import openstack
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StrictBool, StringConstraints

from app.api.deps import get_token_info, require_admin
from app.services import resource_policies
from app.services import resource_policy_store as store
from app.services.keystone import get_admin_project_connection

router = APIRouter()


class ResourcePolicyUpdate(BaseModel):
    resource_id: str | None = Field(default=None, max_length=128)


class RuntimeSettingUpdate(BaseModel):
    value: StrictBool | Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]


async def get_admin_os_conn() -> AsyncIterator[openstack.connection.Connection]:
    """Use the backend administrative scope, never the browser user's project."""
    try:
        conn = await asyncio.to_thread(get_admin_project_connection)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="관리자 OpenStack 연결을 만들 수 없습니다") from exc
    try:
        yield conn
    finally:
        with suppress(Exception):
            await asyncio.to_thread(conn.close)


@router.get("/resource-policies", dependencies=[Depends(require_admin)])
async def list_resource_policies(conn: openstack.connection.Connection = Depends(get_admin_os_conn)):
    try:
        return await store.inspect_policies(conn)
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="리소스 정책 저장소를 사용할 수 없습니다") from exc


@router.get("/resource-policies/catalog/{policy_key}", dependencies=[Depends(require_admin)])
async def discover_resource_policy_options(
    policy_key: str,
    conn: openstack.connection.Connection = Depends(get_admin_os_conn),
):
    try:
        spec = resource_policies.get_spec(policy_key)
        return {
            "key": spec.key,
            "resource_kind": spec.resource_kind,
            "group": spec.group,
            "execution_scope": spec.execution_scope,
            "dependency": spec.dependency,
            "constraints": {"external_only": spec.external_only, "shared_only": spec.shared_only},
            "options": await resource_policies.discover_options(conn, policy_key),
        }
    except resource_policies.ResourcePolicyValidationError as exc:
        raise HTTPException(status_code=404, detail="알 수 없는 리소스 정책입니다") from exc
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="리소스 정책 저장소를 사용할 수 없습니다") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="OpenStack 리소스 목록을 조회할 수 없습니다") from exc


@router.put("/resource-policies/{policy_key}", dependencies=[Depends(require_admin)])
async def update_resource_policy(
    policy_key: str,
    body: ResourcePolicyUpdate,
    token_info: dict = Depends(get_token_info),
    conn: openstack.connection.Connection = Depends(get_admin_os_conn),
):
    try:
        return await store.set_policy(
            conn=conn,
            key=policy_key,
            resource_id=body.resource_id,
            updated_by_user_id=str(token_info.get("user_id") or ""),
        )
    except resource_policies.ResourcePolicyValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="리소스 정책 저장소를 사용할 수 없습니다") from exc


@router.get("/runtime-settings", dependencies=[Depends(require_admin)])
async def list_runtime_settings():
    try:
        return await store.list_runtime_settings()
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="런타임 설정 저장소를 사용할 수 없습니다") from exc


@router.put("/runtime-settings/{setting_key}", dependencies=[Depends(require_admin)])
async def update_runtime_setting(
    setting_key: str,
    body: RuntimeSettingUpdate,
    token_info: dict = Depends(get_token_info),
):
    try:
        return await store.set_runtime_setting(
            key=setting_key,
            value=body.value,
            updated_by_user_id=str(token_info.get("user_id") or ""),
        )
    except store.RuntimeSettingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except store.ResourcePolicyStorageUnavailable as exc:
        raise HTTPException(status_code=503, detail="런타임 설정 저장소를 사용할 수 없습니다") from exc
