from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.database import get_session_factory
from app.models.db import VmCloudInitSnippet
from app.services.k3s_crypto import decrypt_vm_cloud_init, encrypt_vm_cloud_init

_HISTORY_LIMIT = 20
_MAX_CONTENT_LENGTH = 65_536


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class CloudInitSnippetNotFound(Exception):
    pass


def _validate_content(content: str) -> str:
    value = content.strip()
    if not value:
        raise ValueError("cloud-init 내용은 비워둘 수 없습니다")
    if len(value) > _MAX_CONTENT_LENGTH:
        raise ValueError(f"cloud-init 내용은 {_MAX_CONTENT_LENGTH:,}자를 초과할 수 없습니다")
    return value


def _public(row: VmCloudInitSnippet) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "content": decrypt_vm_cloud_init(row.content_encrypted),
        "created_at": _isoformat(row.created_at),
        "updated_at": _isoformat(row.updated_at),
    }


async def list_snippets(user_id: str) -> dict[str, list[dict]]:
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("cloud-init 저장소를 사용할 수 없습니다")
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(VmCloudInitSnippet)
                    .where(VmCloudInitSnippet.user_id == user_id)
                    .order_by(VmCloudInitSnippet.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    snippets = [_public(row) for row in rows]
    return {
        "history": [snippet for snippet in snippets if snippet["kind"] == "history"],
        "presets": [snippet for snippet in snippets if snippet["kind"] == "preset"],
    }


async def create_preset(*, user_id: str, name: str, content: str) -> dict:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 100:
        raise ValueError("프리셋 이름은 1~100자여야 합니다")
    value = _validate_content(content)
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("cloud-init 저장소를 사용할 수 없습니다")
    async with factory() as session, session.begin():
        existing = await session.scalar(
            select(VmCloudInitSnippet).where(
                VmCloudInitSnippet.user_id == user_id,
                VmCloudInitSnippet.kind == "preset",
                VmCloudInitSnippet.name == normalized_name,
            )
        )
        if existing is None:
            existing = VmCloudInitSnippet(
                user_id=user_id,
                kind="preset",
                name=normalized_name,
                content_encrypted=encrypt_vm_cloud_init(value),
            )
            session.add(existing)
        else:
            existing.content_encrypted = encrypt_vm_cloud_init(value)
        await session.flush()
        return _public(existing)


async def record_history(*, user_id: str, content: str | None) -> None:
    if not content or not content.strip():
        return
    value = _validate_content(content)
    factory = get_session_factory()
    if factory is None:
        return
    async with factory() as session, session.begin():
        session.add(
            VmCloudInitSnippet(
                user_id=user_id,
                kind="history",
                name=None,
                content_encrypted=encrypt_vm_cloud_init(value),
            )
        )
        old_ids = list(
            (
                await session.execute(
                    select(VmCloudInitSnippet.id)
                    .where(
                        VmCloudInitSnippet.user_id == user_id,
                        VmCloudInitSnippet.kind == "history",
                    )
                    .order_by(VmCloudInitSnippet.created_at.desc())
                    .offset(_HISTORY_LIMIT)
                )
            ).scalars()
        )
        if old_ids:
            await session.execute(delete(VmCloudInitSnippet).where(VmCloudInitSnippet.id.in_(old_ids)))


async def delete_snippet(*, user_id: str, snippet_id: int) -> None:
    factory = get_session_factory()
    if factory is None:
        raise RuntimeError("cloud-init 저장소를 사용할 수 없습니다")
    async with factory() as session, session.begin():
        result = await session.execute(
            delete(VmCloudInitSnippet).where(
                VmCloudInitSnippet.id == snippet_id,
                VmCloudInitSnippet.user_id == user_id,
            )
        )
        if result.rowcount != 1:
            raise CloudInitSnippetNotFound
