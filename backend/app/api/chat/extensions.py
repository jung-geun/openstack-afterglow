"""빌트인 AI 채팅 확장 API — MCP 서버 / 커스텀 HTTP 툴 관리.

- 관리자 라우터(require_admin): scope='global' 확장 CRUD (전체 적용).
- 사용자 라우터(get_token_info): 본인 scope='user' 확장 CRUD (본인 적용) + 활성 global 열람.

⚠️ MCP 서버는 등록·관리 전용(실행은 langchain-mcp-adapters 핀 이동 후). 커스텀 툴 실행은 후속 슬라이스.
소유권/스코프 검증은 extensions_store 가 강제하고, 예외를 HTTP 상태로 매핑한다.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_token_info, require_admin
from app.services.chat import extensions_store as es

admin_router = APIRouter(dependencies=[Depends(require_admin)])
user_router = APIRouter()


# --- 요청 모델 ---
class McpServerBody(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    transport: str | None = Field(default=None, max_length=20)
    url: str | None = Field(default=None, max_length=500)
    command: str | None = Field(default=None, max_length=500)
    headers: dict | None = None
    is_active: bool | None = None


class CustomToolBody(BaseModel):
    name: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=500)
    method: str | None = Field(default=None, max_length=10)
    url: str | None = Field(default=None, max_length=500)
    params_schema: dict | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=60)
    is_active: bool | None = None

    model_config = {"protected_namespaces": ()}


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, es.ExtensionNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, es.ExtensionForbidden):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, es.ExtensionValidationError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


_EXC = (es.ExtensionNotFound, es.ExtensionForbidden, es.ExtensionValidationError, es.ChatStorageUnavailable)


# ---------------------------------------------------------------------------
# 관리자 (global)
# ---------------------------------------------------------------------------
@admin_router.get("/admin/mcp-servers")
async def admin_list_mcp():
    try:
        return await es.list_global("mcp")
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.post("/admin/mcp-servers", status_code=201)
async def admin_create_mcp(body: McpServerBody):
    try:
        return await es.create("mcp", body.model_dump(exclude_unset=True), scope="global")
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.patch("/admin/mcp-servers/{item_id}")
async def admin_update_mcp(item_id: int, body: McpServerBody):
    try:
        return await es.update("mcp", item_id, body.model_dump(exclude_unset=True), admin=True)
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.delete("/admin/mcp-servers/{item_id}", status_code=204)
async def admin_delete_mcp(item_id: int):
    try:
        await es.delete("mcp", item_id, admin=True)
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.get("/admin/custom-tools")
async def admin_list_tools():
    try:
        return await es.list_global("tool")
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.post("/admin/custom-tools", status_code=201)
async def admin_create_tool(body: CustomToolBody):
    try:
        return await es.create("tool", body.model_dump(exclude_unset=True), scope="global")
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.patch("/admin/custom-tools/{item_id}")
async def admin_update_tool(item_id: int, body: CustomToolBody):
    try:
        return await es.update("tool", item_id, body.model_dump(exclude_unset=True), admin=True)
    except _EXC as exc:
        raise _http(exc) from exc


@admin_router.delete("/admin/custom-tools/{item_id}", status_code=204)
async def admin_delete_tool(item_id: int):
    try:
        await es.delete("tool", item_id, admin=True)
    except _EXC as exc:
        raise _http(exc) from exc


# ---------------------------------------------------------------------------
# 사용자 (본인 스코프 + 활성 global 열람)
# ---------------------------------------------------------------------------
def _owner(token_info: dict) -> tuple[str, str]:
    return token_info["user_id"], token_info["project_id"]


@user_router.get("/mcp-servers")
async def user_list_mcp(token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    # 선택적 기능 목록: 저장소 미가용/데이터 없음은 빈 목록으로 graceful 처리(503 아님).
    try:
        return await es.list_for_user("mcp", user_id=uid, project_id=pid)
    except es.ChatStorageUnavailable:
        return []
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.post("/mcp-servers", status_code=201)
async def user_create_mcp(body: McpServerBody, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        return await es.create(
            "mcp", body.model_dump(exclude_unset=True), scope="user", owner_user_id=uid, owner_project_id=pid
        )
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.patch("/mcp-servers/{item_id}")
async def user_update_mcp(item_id: int, body: McpServerBody, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        return await es.update(
            "mcp", item_id, body.model_dump(exclude_unset=True), requester_user_id=uid, requester_project_id=pid
        )
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.delete("/mcp-servers/{item_id}", status_code=204)
async def user_delete_mcp(item_id: int, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        await es.delete("mcp", item_id, requester_user_id=uid, requester_project_id=pid)
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.get("/custom-tools")
async def user_list_tools(token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    # 선택적 기능 목록: 저장소 미가용/데이터 없음은 빈 목록으로 graceful 처리(503 아님).
    try:
        return await es.list_for_user("tool", user_id=uid, project_id=pid)
    except es.ChatStorageUnavailable:
        return []
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.post("/custom-tools", status_code=201)
async def user_create_tool(body: CustomToolBody, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        return await es.create(
            "tool", body.model_dump(exclude_unset=True), scope="user", owner_user_id=uid, owner_project_id=pid
        )
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.patch("/custom-tools/{item_id}")
async def user_update_tool(item_id: int, body: CustomToolBody, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        return await es.update(
            "tool", item_id, body.model_dump(exclude_unset=True), requester_user_id=uid, requester_project_id=pid
        )
    except _EXC as exc:
        raise _http(exc) from exc


@user_router.delete("/custom-tools/{item_id}", status_code=204)
async def user_delete_tool(item_id: int, token_info: dict = Depends(get_token_info)):
    uid, pid = _owner(token_info)
    try:
        await es.delete("tool", item_id, requester_user_id=uid, requester_project_id=pid)
    except _EXC as exc:
        raise _http(exc) from exc
