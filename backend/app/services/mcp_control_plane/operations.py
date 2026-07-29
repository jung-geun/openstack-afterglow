"""Owner-scoped safe views over durable MCP invocation state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.database import get_session_factory
from app.models.chat_db import McpToolInvocation
from app.services.mcp_control_plane.authentication import McpPrincipal


class McpOperationError(RuntimeError):
    """The operation ledger cannot safely answer the caller."""


@dataclass(frozen=True)
class McpOperationView:
    invocation_id: str
    status: str
    tool_name: str
    created_at: datetime
    resource_ref: str | None
    operation_ref: str | None


async def get_operation(principal: McpPrincipal, *, invocation_id: str) -> McpOperationView:
    """Return metadata only for the exact grant that created an invocation."""
    factory = get_session_factory()
    if factory is None:
        raise McpOperationError("MCP invocation storage is unavailable")
    try:
        async with factory() as session:
            row = await session.scalar(
                select(McpToolInvocation).where(
                    McpToolInvocation.id == invocation_id,
                    McpToolInvocation.grant_id == principal.grant_id,
                    McpToolInvocation.source == "mcp",
                )
            )
    except Exception as exc:
        raise McpOperationError("MCP invocation storage is unavailable") from exc
    if row is None:
        raise McpOperationError("MCP operation was not found")
    return McpOperationView(
        invocation_id=row.id,
        status=row.status,
        tool_name=row.tool_name,
        created_at=row.created_at,
        resource_ref=row.resource_ref,
        operation_ref=row.operation_ref,
    )
