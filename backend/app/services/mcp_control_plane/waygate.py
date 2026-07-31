"""Project-owned, redacted Waygate server adapter for consumer MCP."""

from __future__ import annotations

from typing import Any

from app.database import is_db_available
from app.services import waygate_db


class McpWaygateError(ValueError):
    """Waygate metadata is unavailable or current-project scope cannot be proven."""


def _safe_server(server: dict[str, Any], *, project_id: str) -> dict[str, str | None]:
    if server.get("project_id") != project_id:
        raise McpWaygateError("Waygate server ownership cannot be proven")

    server_id = server.get("id")
    if not server_id:
        raise McpWaygateError("Waygate server id is missing")

    return {
        "id": str(server_id),
        "name": str(server.get("name") or ""),
        "status": str(server.get("status") or ""),
        "created_at": str(server.get("created_at")) if server.get("created_at") else None,
        "updated_at": str(server.get("updated_at")) if server.get("updated_at") else None,
    }


async def list_project_waygate_servers(project_id: str, *, limit: int) -> list[dict[str, str | None]]:
    """Return bounded, exact-project Waygate server metadata without connection details."""
    if not is_db_available():
        raise McpWaygateError("Waygate database is unavailable")

    try:
        servers = await waygate_db.list_servers(project_id, limit=limit)
        return [_safe_server(server, project_id=project_id) for server in servers]
    except McpWaygateError:
        raise
    except Exception as exc:
        raise McpWaygateError("Waygate server list query failed") from exc


async def get_project_waygate_server(project_id: str, server_id: str) -> dict[str, str | None]:
    """Return one exact-project Waygate server or fail closed when it is absent."""
    if not is_db_available():
        raise McpWaygateError("Waygate database is unavailable")

    try:
        server = await waygate_db.get_server(project_id, server_id)
        if server is None:
            raise McpWaygateError("Waygate server not found")
        return _safe_server(server, project_id=project_id)
    except McpWaygateError:
        raise
    except Exception as exc:
        raise McpWaygateError("Waygate server query failed") from exc
