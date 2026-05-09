"""라우터에서 호출하는 짧은 wrapper. token_info + conn 으로부터 식별자 자동 추출."""

from __future__ import annotations

from typing import Any

from app.services.activity import record


async def rec(
    token_info: dict,
    conn: Any | None,
    *,
    resource_type: str,
    action: str,
    status: str = "success",
    resource_id: str | None = None,
    resource_name: str | None = None,
    error_message: str | None = None,
    extra: dict | None = None,
) -> None:
    """활동 기록 단축 함수. project_id/user_id 없으면 silently skip."""
    project_id = token_info.get("project_id") or (getattr(conn, "_afterglow_project_id", "") if conn else "")
    user_id = token_info.get("user_id") or (getattr(conn, "_afterglow_user_id", "") if conn else "")
    username = token_info.get("username", "")
    if not project_id or not user_id:
        return
    await record(
        project_id=project_id,
        user_id=user_id,
        username=username,
        resource_type=resource_type,
        action=action,
        status=status,  # type: ignore[arg-type]
        resource_id=resource_id,
        resource_name=resource_name,
        error_message=error_message,
        extra=extra,
    )
